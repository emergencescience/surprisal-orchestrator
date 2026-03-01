import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from core.database import get_session, limiter
from core.models import (
    Bounty,
    BountyCreate,
    BountyDetailRead,
    BountyRead,
    Submission,
    SubmissionCreate,
    User,
)
from core.security import get_current_user
from services.bounty_service import BountyService
from services.credit_service import CreditService

router = APIRouter(prefix="/bounties", tags=["Bounties"])


def user_id_rate_limit(request: Request):
    user = getattr(request.state, "user", None)
    if user:
        return str(user.id)
    return "anonymous"


@router.post("", response_model=BountyRead)
@limiter.limit("1/minute", key_func=user_id_rate_limit)
def create_bounty(request: Request, bounty: BountyCreate, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    bounty_obj = BountyService.create_bounty(session, bounty, current_user)
    return BountyRead(**bounty_obj.model_dump())


@router.get("", response_model=list[BountyRead])
def get_bounties(
    skip: int = 0,
    limit: int = 10,
    status: str | None = Query(None, description="Comma-separated list of statuses to filter by (e.g. 'open,completed'). Defaults to 'open'."),
    session: Session = Depends(get_session),
):
    query = select(Bounty)

    if status:
        status_list = [s.strip() for s in status.split(",")]
        query = query.where(Bounty.status.in_(status_list))
    else:
        query = query.where(Bounty.status == "open")

    bounties = session.exec(query.order_by(Bounty.created_at.desc()).offset(skip).limit(limit)).all()

    return [BountyRead(**b.model_dump()) for b in bounties]


@router.get("/{bounty_id}", response_model=BountyDetailRead)
def get_bounty(bounty_id: uuid.UUID, session: Session = Depends(get_session)):
    bounty = session.get(Bounty, bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")
    return BountyDetailRead(**bounty.model_dump())


@router.get("/{bounty_id}/solution")
def get_bounty_solution(bounty_id: uuid.UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Note: Original code had two versions of this. Merging to the one that requires ownership or completion."""
    bounty = session.get(Bounty, bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")

    if bounty.status != "completed":
        raise HTTPException(status_code=403, detail="Solution only available for completed bounties.")

    if bounty.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the bounty owner can view the solution.")

    statement = select(Submission).where(Submission.bounty_id == bounty_id, Submission.status == "accepted")
    submission = session.exec(statement).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Accepted solution not found.")

    return {"candidate_solution": submission.candidate_solution}


@router.post("/{bounty_id}/submissions", response_model=Submission)
def create_submission(
    request: Request,
    bounty_id: uuid.UUID,
    submission_in: SubmissionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return BountyService.create_submission(session, bounty_id, current_user, submission_in)


@router.get("/{bounty_id}/submissions", response_model=list[Submission])
def get_submissions(bounty_id: uuid.UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    bounty = session.get(Bounty, bounty_id)
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")
    if bounty.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the bounty owner can view submissions.")
    submissions = session.exec(select(Submission).where(Submission.bounty_id == bounty_id)).all()
    return submissions


@router.delete("/{bounty_id}", status_code=204)
def delete_bounty(bounty_id: uuid.UUID, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    BountyService.delete_bounty(session, bounty_id, current_user)
    return None


@router.post("/batch", response_model=list[BountyRead])
def get_bounties_batch(request: Request, bounty_ids: list[uuid.UUID], session: Session = Depends(get_session)):
    statement = select(Bounty).where(Bounty.id.in_(bounty_ids))
    bounties = session.exec(statement).all()
    return [BountyRead(**b.model_dump()) for b in bounties]
