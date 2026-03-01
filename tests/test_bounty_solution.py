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
from core.models import (
    Bounty,
    BountyStatus,
    Submission,
    SubmissionStatus,
    User,
)
from core.security import get_current_user
from main import app


class TestBountySolution(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        # Owner
        self.owner = User(username="owner", api_key="owner-key", provider_id="owner-provider", micro_credits=100_000_000)
        self.session.add(self.owner)

        # Solver
        self.solver = User(username="solver", api_key="solver-key", provider_id="solver-provider", micro_credits=10_000_000)
        self.session.add(self.solver)

        self.session.commit()

        # Override get_session globally for all tests
        app.dependency_overrides[get_session] = lambda: self.session

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

    def create_bounty(self, status="open"):
        self.override_auth(self.owner)  # Ensure owner is authenticated for the API call
        response = self.client.post(
            "/bounties",
            json={
                "title": "Test Bounty",
                "description": "Test Description",
                "micro_reward": 100000,  # Fixed reward magnitude: 0.1 Credit
                "idempotency_key": str(uuid.uuid4()),
                "evaluation_spec": "import unittest\nclass Test(unittest.TestCase):\n  pass",
                "solution_template": "def solve(): pass",
            },
            headers={"Authorization": "Bearer owner-key"},
        )  # Pass owner's key
        self.assertEqual(response.status_code, 200)
        bounty_data = response.json()

        # Fetch the bounty from the session to ensure it's a model instance
        bounty = self.session.exec(select(Bounty).where(Bounty.id == uuid.UUID(bounty_data["id"]))).first()

        # If status needs to be different from default "open", update it
        if status != "open":
            bounty.status = BountyStatus[status.upper()]
            self.session.add(bounty)
            self.session.commit()
            self.session.refresh(bounty)

        return bounty

    def test_get_bounties_filtering(self):
        # Create one open and one completed bounty
        open_bounty = self.create_bounty(status="open")
        completed_bounty = self.create_bounty(status="completed")

        # Test default (OPEN only)
        res = self.client.get("/bounties")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Note: order is desc by id.
        # Only open_bounty should be returned
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(open_bounty.id))

        # Test status=completed
        res = self.client.get("/bounties?status=completed")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(completed_bounty.id))

        # Test status=open,completed
        res = self.client.get("/bounties?status=open,completed")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data), 2)

    def test_get_solution_access(self):
        self.override_auth(self.owner)
        # 1. Create Bounty (Open)
        bounty = self.create_bounty(status="open")

        # 2. Try to get solution (Should fail - 403)
        res = self.client.get(f"/bounties/{bounty.id}/solution", headers={"Authorization": "Bearer owner-key"})
        self.assertEqual(res.status_code, 403)  # "Solution is only available for completed bounties"

        # 3. Create Submission (Accepted) and Complete Bounty manually
        submission = Submission(
            bounty_id=bounty.id, solver_id=self.solver.id, candidate_solution="print('winner')", idempotency_key=uuid.uuid4(), status=SubmissionStatus.ACCEPTED
        )
        self.session.add(submission)
        bounty.status = BountyStatus.COMPLETED
        self.session.add(bounty)
        self.session.commit()

        # 4. Get Solution (Should success)
        res = self.client.get(f"/bounties/{bounty.id}/solution", headers={"Authorization": "Bearer owner-key"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["candidate_solution"], "print('winner')")


if __name__ == "__main__":
    unittest.main()
