import os
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class BountyStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    VERIFIED = "verified"
    FAILED = "failed"
    ERROR = "error"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TransactionType(StrEnum):
    TRANSFER = "transfer"
    FEE = "fee"
    REFUND = "refund"
    GRANT = "grant"


class ProgrammingLanguage(StrEnum):
    PYTHON3 = "python3"
    RUST = "rust"
    GOLANG = "golang"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    TEXT = "text"  # For non-code bounties (manual review)


class UserBase(SQLModel):
    username: str = Field(unique=True)


class User(UserBase, table=True):
    __table_args__ = (sa.UniqueConstraint("provider", "provider_id", name="unique_user_provider"), {"extend_existing": True})
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    api_key: str = Field(index=True, unique=True)
    provider: str = Field(default="github", index=True)
    provider_id: str = Field(index=True)
    micro_credits: int = Field(
        default_factory=lambda: int(os.getenv("INITIAL_GRANT_MICRO_CREDITS", "1000000")),
        sa_column=sa.Column(sa.BigInteger, default=lambda: int(os.getenv("INITIAL_GRANT_MICRO_CREDITS", "1000000"))),
    )
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class UserRead(SQLModel):
    id: uuid.UUID
    username: str
    micro_credits: int
    created_at: datetime


class Transaction(SQLModel, table=True):
    __table_args__ = (sa.CheckConstraint("micro_amount > 0", name="check_amount_positive"), {"extend_existing": True})
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    from_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    to_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id", index=True)
    micro_amount: int = Field(sa_column=sa.Column(sa.BigInteger))
    bounty_id: uuid.UUID | None = Field(default=None, foreign_key="bounty.id", index=True)
    submission_id: uuid.UUID | None = Field(default=None, foreign_key="submission.id", index=True)
    type: str = Field(default=TransactionType.TRANSFER, sa_column=sa.Column(sa.String, default=TransactionType.TRANSFER))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class TransactionRead(SQLModel):
    id: uuid.UUID
    from_user_id: uuid.UUID | None
    to_user_id: uuid.UUID | None
    micro_amount: int  # High-precision unit (1,000,000 = 1 Credit)
    bounty_id: uuid.UUID | None
    submission_id: uuid.UUID | None
    type: TransactionType
    created_at: datetime


class BountyBase(SQLModel):
    title: str
    description: str
    programming_language: ProgrammingLanguage = Field(default=ProgrammingLanguage.PYTHON3)
    runtime: str | None = Field(default="python:3.14", description="Specific runtime version (e.g., 'python:3.14', 'node:20')")
    bounty_metadata: dict = Field(default_factory=dict, sa_column=sa.Column(sa.JSON))


class Bounty(BountyBase, table=True):
    __table_args__ = (
        sa.CheckConstraint("micro_reward > 0", name="check_reward_positive"),
        sa.UniqueConstraint("owner_id", "idempotency_key", name="unique_bounty_idempotency"),
        {"extend_existing": True},
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    micro_reward: int = Field(sa_column=sa.Column(sa.BigInteger))
    solution_template: str | None = None
    evaluation_spec: str | None = None
    runtime: str | None = Field(default="python:3.14")
    bounty_metadata: dict = Field(default_factory=dict, sa_column=sa.Column(sa.JSON))
    status: str = Field(default=BountyStatus.OPEN, sa_column=sa.Column(sa.String, default=BountyStatus.OPEN))
    owner_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    idempotency_key: uuid.UUID = Field(index=True)
    accepted_submission_id: uuid.UUID | None = Field(
        default=None, sa_column=sa.Column(sa.UUID, sa.ForeignKey("submission.id", use_alter=True, name="fk_bounty_accepted_submission"))
    )
    deleted_at: datetime | None = Field(default=None, sa_column=sa.Column(sa.DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(days=7))


class BountyCreate(BountyBase):
    micro_reward: int = Field(description="Reward in micro-credits (1,000,000 = 1 Credit)")
    solution_template: str | None = None
    evaluation_spec: str | None = None
    idempotency_key: uuid.UUID


class BountyRead(BountyBase):
    id: uuid.UUID
    micro_reward: int  # Micro-credits (e.g. 1,000,000)
    status: BountyStatus
    owner_id: uuid.UUID
    created_at: datetime
    expires_at: datetime | None = None


class BountyDetailRead(BountyRead):
    solution_template: str | None = None
    evaluation_spec: str | None = None


class SubmissionBase(SQLModel):
    candidate_solution: str
    commentary: str | None = None  # Markdown commentary from seller
    submission_metadata: dict = Field(default_factory=dict)


class Submission(SubmissionBase, table=True):
    __table_args__ = (sa.UniqueConstraint("solver_id", "idempotency_key", name="unique_submission_idempotency"), {"extend_existing": True})
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    bounty_id: uuid.UUID = Field(sa_column=sa.Column(sa.UUID, sa.ForeignKey("bounty.id", name="fk_submission_bounty"), nullable=False, index=True))
    solver_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    idempotency_key: uuid.UUID = Field(index=True)
    submission_metadata: dict = Field(default_factory=dict, sa_column=sa.Column(sa.JSON))
    status: str = Field(default=SubmissionStatus.PENDING, sa_column=sa.Column(sa.String, default=SubmissionStatus.PENDING))
    stdout: str | None = None
    stderr: str | None = None
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class SubmissionCreate(SubmissionBase):
    idempotency_key: uuid.UUID
