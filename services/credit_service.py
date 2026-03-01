import uuid

from sqlmodel import Session, select

from core.models import Transaction, User


class CreditService:
    SCALE = 1_000_000  # 1,000,000 Micro-credits = 1 Credit
    VERIFICATION_FEE = 1_000  # 0.001 Credit = 1,000 Micro-credits
    LISTING_FEE = 0           # Waived to protect requester agents ($1 shield is now a reward limit)

    @staticmethod
    def to_micro(credits: float) -> int:
        return int(round(credits * CreditService.SCALE))

    @staticmethod
    def from_micro(micro_credits: int) -> float:
        return micro_credits / CreditService.SCALE

    @staticmethod
    def get_balance(user: User) -> dict:
        credits = CreditService.from_micro(user.micro_credits)
        return {
            "credits": credits,
            "micro_credits": user.micro_credits
        }

    @staticmethod
    def get_transactions(session: Session, user_id: uuid.UUID, limit: int = 10, skip: int = 0) -> list[dict]:
        """
        Returns the transaction history for a user, scaled to human-readable credits.
        """
        statement = select(Transaction).where(
            (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
        ).order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
        
        txns = session.exec(statement).all()
        return [
            {
                "id": str(t.id),
                "from_user_id": t.from_user_id,
                "to_user_id": t.to_user_id,
                "amount": CreditService.from_micro(t.amount),
                "bounty_id": t.bounty_id,
                "submission_id": t.submission_id,
                "type": t.type,
                "created_at": t.created_at
            }
            for t in txns
        ]

    @staticmethod
    def apply_verification_fee(session: Session, user: User, bounty_id: uuid.UUID | None = None):
        """
        Deducts a small fee for referee verification services.
        """
        if user.micro_credits < CreditService.VERIFICATION_FEE:
             raise Exception("Insufficient credits for verification fee.")
             
        user.micro_credits -= CreditService.VERIFICATION_FEE
        session.add(user)
        
        txn = Transaction(
            from_user_id=user.id,
            amount=CreditService.VERIFICATION_FEE,
            bounty_id=bounty_id,
            type="fee"
        )
        session.add(txn)
