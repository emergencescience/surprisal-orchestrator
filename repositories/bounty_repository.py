from sqlmodel import Session, select

from core.models import Bounty, BountyStatus, Submission


class BountyRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, bounty_id: int) -> Bounty | None:
        return self.session.get(Bounty, bounty_id)

    def get_active(self) -> list[Bounty]:
        statement = select(Bounty).where(Bounty.status == BountyStatus.OPEN)
        return self.session.exec(statement).all()

    def create(self, bounty: Bounty) -> Bounty:
        self.session.add(bounty)
        self.session.commit()
        self.session.refresh(bounty)
        return bounty

    def update(self, bounty: Bounty) -> Bounty:
        self.session.add(bounty)
        self.session.commit()
        self.session.refresh(bounty)
        return bounty


class SubmissionRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, submission: Submission) -> Submission:
        self.session.add(submission)
        self.session.commit()
        self.session.refresh(submission)
        return submission

    def get_by_bounty_id(self, bounty_id: int) -> list[Submission]:
        statement = select(Submission).where(Submission.bounty_id == bounty_id)
        return self.session.exec(statement).all()
