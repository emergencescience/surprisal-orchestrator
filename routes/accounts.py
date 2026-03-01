
from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from core.database import get_session
from core.models import TransactionRead, User, UserRead
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
    return UserRead(
        **current_user.model_dump(exclude={"micro_credits"}),
        micro_credits=CreditService.from_micro(current_user.micro_credits)
    )

@router.get("/transactions", response_model=list[TransactionRead])
def get_transactions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the transaction history for the current user.
    """
    txs = CreditService.get_history(session, current_user.id)
    return [
        TransactionRead(
            **t.model_dump(exclude={"amount"}),
            amount=CreditService.from_micro(t.amount),
            micro_amount=t.amount
        ) for t in txs
    ]
