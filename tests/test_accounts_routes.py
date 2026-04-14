import os
import sys
import unittest
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Adjust path to import api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_session
from core.models import Submission, SubmissionStatus, User
from main import app


class TestAccountsRoutes(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.user = User(username="testuser", api_key="test-key", provider_id="test-provider")
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)

        app.dependency_overrides[get_session] = lambda: self.session
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.session.close()

    def test_get_reputation_no_submissions(self):
        resp = self.client.get(f"/accounts/{self.user.id}/reputation")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["score"], 0.0)
        self.assertEqual(data["total_submissions"], 0)

    def test_get_reputation_mixed_submissions(self):
        # 2 accepted, 1 rejected, 1 pending
        s1 = Submission(
            bounty_id=uuid.uuid4(), solver_id=self.user.id, idempotency_key=uuid.uuid4(), status=SubmissionStatus.ACCEPTED, candidate_solution="pass"
        )
        s2 = Submission(
            bounty_id=uuid.uuid4(), solver_id=self.user.id, idempotency_key=uuid.uuid4(), status=SubmissionStatus.ACCEPTED, candidate_solution="pass"
        )
        s3 = Submission(
            bounty_id=uuid.uuid4(), solver_id=self.user.id, idempotency_key=uuid.uuid4(), status=SubmissionStatus.REJECTED, candidate_solution="pass"
        )
        s4 = Submission(
            bounty_id=uuid.uuid4(), solver_id=self.user.id, idempotency_key=uuid.uuid4(), status=SubmissionStatus.PENDING, candidate_solution="pass"
        )

        self.session.add_all([s1, s2, s3, s4])
        self.session.commit()

        resp = self.client.get(f"/accounts/{self.user.id}/reputation")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # total_submissions = 4
        # successful_submissions = 2
        # score = 2/4 = 0.5
        self.assertEqual(data["total_submissions"], 4)
        self.assertEqual(data["successful_submissions"], 2)
        self.assertEqual(data["score"], 0.5)


if __name__ == "__main__":
    unittest.main()
