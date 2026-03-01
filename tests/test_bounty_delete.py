import os
import sys
import unittest

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

# Adjust path to import api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid

from core.database import get_session
from core.models import Bounty, Transaction, User
from core.security import get_current_user
from main import app
from services.credit_service import CreditService


class TestBountyDelete(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        # Owner
        self.owner = User(username="owner", api_key="owner-key", provider_id="owner-provider", micro_credits=100_000_000)
        self.session.add(self.owner)
        self.session.commit()
        self.session.refresh(self.owner)

        # Disable rate limiting
        app.state.limiter.enabled = False

        self.client = TestClient(app)

    def tearDown(self):
        app.state.limiter.enabled = True
        app.dependency_overrides.clear()
        self.session.close()

    def override_auth(self, user):
        app.dependency_overrides[get_session] = lambda: self.session
        app.dependency_overrides[get_current_user] = lambda: user

    def test_delete_refunds_credits(self):
        # 1. Create Bounty (Owner)
        self.override_auth(self.owner)

        reward_micro = 500_000  # 0.5 Credits
        res = self.client.post(
            "/bounties",
            json={
                "title": "Refund Test",
                "description": "Delete Me",
                "micro_reward": reward_micro,
                "idempotency_key": str(uuid.uuid4()),
                "evaluation_spec": "pass",
                "solution_template": "pass",
            },
        )
        self.assertEqual(res.status_code, 200)
        # create_bounty returns 201? No, 200 in current router.
        # Wait, check router... line 20 of routes/bounties.py: def create_bounty(...) returns BountyRead (no status_code specified, so 200).
        # Actually in test_bounty_lifecycle it was 200.
        self.assertEqual(res.status_code, 200)
        bounty_id = uuid.UUID(res.json()["id"])

        # Verify credits deducted (Reward + Fee)
        self.session.refresh(self.owner)
        expected_micro = 100_000_000 - reward_micro - CreditService.LISTING_FEE
        self.assertEqual(self.owner.micro_credits, expected_micro)

        # 2. Delete Bounty
        res = self.client.delete(f"/bounties/{bounty_id}")
        self.assertEqual(res.status_code, 204)

        # 3. Verify Credits Refunded (Only reward)
        self.session.refresh(self.owner)
        self.assertEqual(self.owner.micro_credits, 100_000_000 - CreditService.LISTING_FEE)

        # 4. Verify Bounty Status
        bounty = self.session.get(Bounty, bounty_id)
        self.assertEqual(bounty.status, "deleted")

        # 5. Verify Transaction
        txns = self.session.exec(select(Transaction).where(Transaction.bounty_id == bounty_id)).all()
        # Should have at least one transaction for refund?
        # Actually create_bounty doesn't seem to create a Transaction for deduction in current code (based on my read).
        # create_bounty lines 353-354 just deducts credits.
        # But our delete_bounty implementation plan involves creating a Transaction.
        refund_txns = [t for t in txns if t.type == "refund"]
        self.assertEqual(len(refund_txns), 1)
        self.assertEqual(refund_txns[0].amount, reward_micro)


if __name__ == "__main__":
    unittest.main()
