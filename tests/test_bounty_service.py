import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlmodel import Session

from core.models import (
    Bounty,
    BountyCreate,
    BountyStatus,
    SubmissionCreate,
    SubmissionStatus,
    User,
)
from services.bounty_service import BountyService


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def mock_user():
    return User(id=uuid.uuid4(), username="test_agent", micro_credits=100_000_000)


@pytest.fixture
def mock_bounty(mock_user):
    return Bounty(
        id=uuid.uuid4(),
        title="Test Bounty",
        description="Test Description",
        reward=500_000,  # 0.5 Credits
        evaluation_spec="def test(): pass",
        owner_id=mock_user.id,
        idempotency_key=uuid.uuid4(),
        status="open",
    )


def test_create_bounty_insufficient_credits(mock_session, mock_user):
    low_credit_user = User(id=uuid.uuid4(), username="poor_agent", micro_credits=0)
    bounty = BountyCreate(micro_reward=500_000, evaluation_spec="pass", title="T", description="D", idempotency_key=uuid.uuid4())

    # Ensure idempotency check returns None
    mock_session.exec.return_value.first.return_value = None

    with pytest.raises(HTTPException) as excinfo:
        BountyService.create_bounty(mock_session, bounty, low_credit_user)

    assert excinfo.value.status_code == 402
    assert "Insufficient credits" in excinfo.value.detail


def test_create_bounty_success(mock_session, mock_user):
    bounty = BountyCreate(micro_reward=1_000_000, evaluation_spec="print('hello')", title="T", description="D", idempotency_key=uuid.uuid4())

    # Ensure idempotency check returns None
    mock_session.exec.return_value.first.return_value = None

    # Mock result for sanity check
    mock_sanity = MagicMock()
    mock_sanity.status = "passed"

    # Mock safety check and moderation
    with (
        patch("services.bounty_service.validate_code_safety", return_value=None),
        patch("services.bounty_service.execute_submission_sync", return_value=mock_sanity),
    ):
        created_bounty = BountyService.create_bounty(mock_session, bounty, mock_user)

        # 100M - 1M (reward) = 99,000,000 (listing fee is 0)
        assert mock_user.micro_credits == 99_000_000
        assert created_bounty.owner_id == mock_user.id
        mock_session.add.assert_called()
        mock_session.commit.assert_called()


def test_create_submission_self_solve(mock_session, mock_user, mock_bounty):
    mock_session.get.return_value = mock_bounty
    # Ensure idempotency check returns None
    mock_session.exec.return_value.first.return_value = None

    submission_in = SubmissionCreate(candidate_solution="print('solve')", idempotency_key=uuid.uuid4())
    with pytest.raises(HTTPException) as excinfo:
        BountyService.create_submission(mock_session, mock_bounty.id, mock_user, submission_in)

    assert excinfo.value.status_code == 400
    assert "Cannot solve your own bounty" in excinfo.value.detail


@patch("services.bounty_service.CreditService.apply_verification_fee")
@patch("services.bounty_service.execute_submission_sync")
def test_create_submission_success(mock_execute, mock_fee, mock_session, mock_user, mock_bounty):
    solver = User(id=uuid.uuid4(), username="solver_agent", micro_credits=0)

    # Mock execution result
    mock_result = MagicMock()
    mock_result.status = "accepted"
    mock_result.stdout = "Success"
    mock_result.stderr = ""
    mock_execute.return_value = mock_result

    # Ensure idempotency check returns None
    mock_session.exec.return_value.first.return_value = None

    # Mock session.get side effects
    # 1. get bounty, 2. get solver
    mock_session.get.side_effect = [mock_bounty, solver]

    submission_in = SubmissionCreate(candidate_solution="print('code')", idempotency_key=uuid.uuid4())
    submission = BountyService.create_submission(mock_session, mock_bounty.id, solver, submission_in)

    assert submission.status == SubmissionStatus.ACCEPTED
    assert mock_bounty.status == BountyStatus.COMPLETED
    assert solver.micro_credits == 500_000
    mock_session.commit.assert_called()
