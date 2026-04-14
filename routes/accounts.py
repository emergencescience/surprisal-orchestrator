import uuid
from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select
from sqlalchemy import func

from core.database import get_session
from core.models import TransactionRead, User, UserRead, Submission
from core.security import get_current_user
from services.credit_service import CreditService

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("/balance")
def get_balance(request: Request, current_user: User = Depends(get_current_user)):
    """
    Returns the current user's balance in credits.
    """
    return CreditService.get_balance(current_user)


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return UserRead(**current_user.model_dump())


@router.get("/{user_id}/reputation")
def get_reputation(user_id: uuid.UUID, session: Session = Depends(get_session)):
    """
    Returns the solver's Proof of Task Execution (PoTE) reputation score based on verifiable executions.
    """
    total = session.exec(select(func.count(Submission.id)).where(Submission.solver_id == user_id)).one()
    if total == 0:
        return {"user_id": user_id, "score": 0.0, "total_submissions": 0, "successful_submissions": 0}
        
    successful = session.exec(select(func.count(Submission.id)).where(Submission.solver_id == user_id, Submission.status == "accepted")).one()
    score = successful / total
    return {"user_id": user_id, "score": score, "total_submissions": total, "successful_submissions": successful}


@router.get("/transactions", response_model=list[TransactionRead])
def get_transactions(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    """
    Returns the transaction history for the current user.
    """
    txs = CreditService.get_transactions(session, current_user.id)
    return [TransactionRead(**t.model_dump()) for t in txs]
