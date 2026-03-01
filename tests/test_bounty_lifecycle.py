import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Adjust path to import api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid

from core.database import get_session
from core.models import Bounty, BountyStatus, SubmissionStatus, User
from core.security import get_current_user
from main import app


class TestBountyLifecycle(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        # Owner
        self.owner = User(username="owner", api_key="owner-key", provider_id="owner-provider", micro_credits=100_000_000)
        self.session.add(self.owner)

        # Solver
        self.solver = User(username="solver", api_key="solver-key", provider_id="solver-provider", micro_credits=100_000)  # Give solver some credits for fees
        self.session.add(self.solver)

        self.session.commit()
        self.session.refresh(self.owner)
        self.session.refresh(self.solver)

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

    @patch("services.bounty_service.execute_submission_sync")
    def test_lifecycle_success(self, mock_execute):
        # 1. Create Bounty (Owner)
        self.override_auth(self.owner)

        reward_micro = 1_000_000  # 1.0 Credit
        res = self.client.post(
            "/bounties",
            json={
                "title": "Test Bounty",
                "description": "Lifecycle Test",
                "micro_reward": reward_micro,
                "idempotency_key": str(uuid.uuid4()),
                "evaluation_spec": "pass",
                "solution_template": "pass",
            },
        )
        self.assertEqual(res.status_code, 200)
        bounty_id = uuid.UUID(res.json()["id"])

        # 2. Submit Submission (Solver)
        self.override_auth(self.solver)

        # Mock execution success
        mock_result = MagicMock()
        mock_result.status = "accepted"
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_execute.return_value = mock_result

        res = self.client.post(f"/bounties/{bounty_id}/submissions", json={"candidate_solution": "print('hello')", "idempotency_key": str(uuid.uuid4())})
        self.assertEqual(res.status_code, 200)
        submission_data = res.json()

        # 3. Verify Auto-Acceptance
        self.assertEqual(submission_data["status"], SubmissionStatus.ACCEPTED)

        # Check Bounty Status
        res = self.client.get(f"/bounties/{bounty_id}")
        self.assertEqual(res.json()["status"], BountyStatus.COMPLETED)

        # Check Credits
        self.session.refresh(self.owner)
        self.session.refresh(self.solver)

        # Owner: 100M - 1M reward - 0 fee = 99,000,000 micro-credits
        self.assertEqual(self.owner.micro_credits, 99_000_000)

        # Solver: 100k - 1k verification + 1M reward = 1,099,000 micro-credits
        self.assertEqual(self.solver.micro_credits, 1_099_000)

    def test_reward_limit_failure(self):
        """Test that rewards > 1.0 credit are rejected"""
        self.override_auth(self.owner)
        reward_too_high = 1_000_001  # 1.000001 Credit
        res = self.client.post(
            "/bounties",
            json={
                "title": "Expensive Bounty",
                "description": "Limit Test",
                "micro_reward": reward_too_high,
                "idempotency_key": str(uuid.uuid4()),
                "evaluation_spec": "pass",
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Reward limit exceeded", res.json()["detail"])

    @patch("services.bounty_service.execute_submission_sync")
    def test_race_condition(self, mock_execute):
        """Test that if bounty is completed while submission is running, submission is REJECTED"""
        # 1. Create Bounty
        self.override_auth(self.owner)
        reward_micro = 10_000
        res = self.client.post(
            "/bounties",
            json={
                "title": "Race Test",
                "description": "Race Condition",
                "micro_reward": reward_micro,
                "idempotency_key": str(uuid.uuid4()),
                "evaluation_spec": "pass",
                "solution_template": "pass",
            },
        )
        bounty_id = uuid.UUID(res.json()["id"])

        # 2. Define Side Effect to Simulate Race Condition
        def side_effect(*args, **kwargs):
            bounty = self.session.get(Bounty, bounty_id)
            bounty.status = BountyStatus.COMPLETED
            self.session.add(bounty)
            self.session.commit()

            mock_result = MagicMock()
            mock_result.status = "accepted"
            mock_result.stdout = "ok"
            mock_result.stderr = ""
            return mock_result

        mock_execute.side_effect = side_effect

        # 3. Submit Submission (Solver)
        self.override_auth(self.solver)
        res = self.client.post(f"/bounties/{bounty_id}/submissions", json={"candidate_solution": "pass", "idempotency_key": str(uuid.uuid4())})

        # 4. Verify Rejection
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], SubmissionStatus.REJECTED)
        self.assertIn("already COMPLETED", data["stderr"])
