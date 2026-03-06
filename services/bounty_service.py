import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from core.models import (
    Bounty,
    BountyCreate,
    BountyStatus,
    Submission,
    SubmissionCreate,
    SubmissionStatus,
    Transaction,
    TransactionType,
    User,
)
from repositories.bounty_repository import BountyRepository, SubmissionRepository
from services.credit_service import CreditService
from services.execution import execute_submission_sync
from services.safety import validate_code_safety


class BountyService:
    @staticmethod
    def create_bounty(session: Session, bounty_in: BountyCreate, owner: User) -> Bounty:
        """
        Creates a new bounty, handles credit escrow and listing fees.
        Enforces a mandatory dry-run validation before creation.
        """
        repo = BountyRepository(session)

        # 1. Check for Idempotency
        existing_bounty = session.exec(select(Bounty).where(Bounty.owner_id == owner.id, Bounty.idempotency_key == bounty_in.idempotency_key)).first()
        if existing_bounty:
            return existing_bounty

        # reward_micro is already in micro-credits
        reward_micro = bounty_in.micro_reward

        # Validations
        if reward_micro <= 0:
            raise HTTPException(status_code=400, detail="Reward must be a positive number (in micro-credits).")

        if reward_micro > CreditService.SCALE:  # 1,000,000 micro-credits = 1 Credit ($1)
            raise HTTPException(
                status_code=400, detail=f"Reward limit exceeded for v1.0.0. Maximum reward is 1.0 Credit ({CreditService.SCALE} micro-credits)."
            )

        if not bounty_in.evaluation_spec:
            raise HTTPException(status_code=400, detail="evaluation_spec is required.")

        # 2. Syntax, Safety & Mandatory Dry-Run
        language = bounty_in.programming_language or "python3"
        try:
            # Static Safety Check
            test_safety_err = validate_code_safety(bounty_in.evaluation_spec, language)
            if test_safety_err:
                raise HTTPException(status_code=400, detail=f"Bounty Evaluation Spec Safety Error: {test_safety_err}")

            if bounty_in.solution_template:
                template_safety_err = validate_code_safety(bounty_in.solution_template, language)
                if template_safety_err:
                    raise HTTPException(status_code=400, detail=f"Bounty Solution Template Safety Error: {template_safety_err}")

            # Mandatory Dry-Run
            dry_run_solution = bounty_in.solution_template or ("pass" if language == "python3" else "// pass")
            dry_run_result = execute_submission_sync(dry_run_solution, bounty_in.evaluation_spec, language)

            if dry_run_result.status == "rejected" and "Security Error" in (dry_run_result.stderr or ""):
                raise HTTPException(status_code=400, detail=f"Bounty Dry-Run Security Violation: {dry_run_result.stderr}")

        except SyntaxError as e:
            raise HTTPException(status_code=400, detail=f"Invalid Python syntax: {str(e)}")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(status_code=400, detail=f"Bounty Validation Error: {str(e)}")

        # 3. Credit Check ($1 USD Shield + Reward)
        total_cost = reward_micro + CreditService.LISTING_FEE
        if owner.micro_credits < total_cost:
            raise HTTPException(
                status_code=402, detail=f"Insufficient credits. Total cost (Reward + Listing Fee) is {CreditService.from_micro(total_cost)} credits."
            )

        # Deduct credits
        owner.micro_credits -= total_cost
        session.add(owner)

        # Create Bounty object
        bounty = Bounty(
            title=bounty_in.title,
            description=bounty_in.description,
            micro_reward=reward_micro,
            solution_template=bounty_in.solution_template,
            evaluation_spec=bounty_in.evaluation_spec,
            owner_id=owner.id,
            idempotency_key=bounty_in.idempotency_key,
            programming_language=bounty_in.programming_language,
            runtime=bounty_in.runtime,
            bounty_metadata=bounty_in.bounty_metadata,
        )

        try:
            bounty = repo.create(bounty)
        except IntegrityError:
            session.rollback()
            return session.exec(select(Bounty).where(Bounty.owner_id == owner.id, Bounty.idempotency_key == bounty_in.idempotency_key)).one()

        # Listing Fee Transaction
        if CreditService.LISTING_FEE > 0:
            fee_txn = Transaction(from_user_id=owner.id, micro_amount=CreditService.LISTING_FEE, bounty_id=bounty.id, type=TransactionType.FEE)
            session.add(fee_txn)

        session.commit()
        session.refresh(bounty)
        return bounty

    @staticmethod
    def create_submission(session: Session, bounty_id: uuid.UUID, solver: User, submission_in: SubmissionCreate) -> Submission:
        """
        Submits a solution solution. Supports idempotency using solver_id + idempotency_key.
        """
        bounty_repo = BountyRepository(session)

        # 1. Check for Idempotency
        existing_submission = session.exec(
            select(Submission).where(Submission.solver_id == solver.id, Submission.idempotency_key == submission_in.idempotency_key)
        ).first()
        if existing_submission:
            return existing_submission

        # Verify bounty
        bounty = bounty_repo.get_by_id(bounty_id)
        if not bounty:
            raise HTTPException(status_code=404, detail="Bounty not found")
        if bounty.status != BountyStatus.OPEN:
            raise HTTPException(status_code=400, detail="Bounty is not open")

        # Prevent self-solving
        if bounty.owner_id == solver.id:
            raise HTTPException(status_code=400, detail="Cannot solve your own bounty")

        # Create Submission Record
        submission = Submission(
            bounty_id=bounty_id,
            solver_id=solver.id,
            candidate_solution=submission_in.candidate_solution,
            commentary=submission_in.commentary,
            idempotency_key=submission_in.idempotency_key,
            submission_metadata=submission_in.submission_metadata,
            status=SubmissionStatus.PENDING,
        )

        try:
            session.add(submission)
            session.flush() # Generate ID and check constraints without committing
        except IntegrityError:
            session.rollback()
            existing = session.exec(
                select(Submission).where(Submission.solver_id == solver.id, Submission.idempotency_key == submission_in.idempotency_key)
            ).first()
            if existing:
                return existing
            raise HTTPException(status_code=400, detail="Submission idempotency conflict or integrity error.")

        # Apply verification fee (Always charge for the attempt)
        CreditService.apply_verification_fee(session, solver, bounty_id)

        # Validation Logic (Synchronous for v1.0.0 Launch)
        result = execute_submission_sync(submission.candidate_solution, bounty.evaluation_spec, bounty.programming_language)
        submission.stdout = result.stdout
        submission.stderr = result.stderr

        if result.status == "accepted":
            session.refresh(bounty)
            if bounty.status == BountyStatus.OPEN:
                submission.status = SubmissionStatus.ACCEPTED
                bounty.status = BountyStatus.COMPLETED
                bounty.accepted_submission_id = submission.id

                solver.micro_credits += bounty.micro_reward
                session.add(solver)

                txn = Transaction(
                    from_user_id=bounty.owner_id, 
                    to_user_id=solver.id, 
                    micro_amount=bounty.micro_reward, 
                    bounty_id=bounty.id, 
                    submission_id=submission.id, 
                    type=TransactionType.TRANSFER
                )
                session.add(txn)
                # No need for bounty_repo.update if it's already in session
            else:
                submission.status = SubmissionStatus.REJECTED
                submission.stderr = (submission.stderr or "") + "\n[System]: Solution verified but Bounty was already COMPLETED."
        else:
            submission.status = SubmissionStatus.FAILED

        session.commit()
        session.refresh(submission)
        return submission

    @staticmethod
    def delete_bounty(session: Session, bounty_id: uuid.UUID, user: User):
        repo = BountyRepository(session)
        bounty = repo.get_by_id(bounty_id)
        if not bounty:
            raise HTTPException(status_code=404, detail="Bounty not found")

        if bounty.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        if bounty.locked_until and bounty.locked_until > datetime.now(UTC):
            raise HTTPException(status_code=400, detail="Bounty is currently locked and cannot be cancelled. This guarantees solver agent compute safety.")

        submissions = SubmissionRepository(session).get_by_bounty_id(bounty_id)
        if submissions:
            raise HTTPException(status_code=409, detail="Cannot delete bounty with existing submissions.")

        if bounty.status != BountyStatus.DELETED and bounty.micro_reward > 0:
            user.micro_credits += bounty.micro_reward
            session.add(user)

            txn = Transaction(to_user_id=user.id, micro_amount=bounty.micro_reward, bounty_id=bounty.id, type=TransactionType.REFUND)
            session.add(txn)

        bounty.status = BountyStatus.DELETED
        repo.update(bounty)
        session.commit()
