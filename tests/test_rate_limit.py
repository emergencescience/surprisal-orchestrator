import os
import sys
import time
import unittest

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from core.database import get_session
from core.models import User
from main import app

# Use in-memory DB for tests
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def create_test_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_test_session():
    with Session(engine) as session:
        yield session


class TestRateLimit(unittest.TestCase):
    def setUp(self):
        create_test_db_and_tables()
        app.dependency_overrides[get_session] = get_test_session
        self.client = TestClient(app)

    def tearDown(self):
        SQLModel.metadata.drop_all(engine)
        app.dependency_overrides.clear()
        # Reset limiter state between tests
        if hasattr(app.state, "limiter"):
            app.state.limiter._storage.reset()
        time.sleep(0.1)

    def test_bounty_rate_limit(self):
        # Create a user manually in the test session
        api_key = "test-api-key"
        user = User(username="test_buyer", api_key=api_key, provider="github", provider_id="12345", micro_credits=100_000_000)
        # We need a shared session for both the mock and the setup
        with Session(engine) as session:
            session.add(user)
            session.commit()
            session.refresh(user)

        headers = {"Authorization": f"Bearer {api_key}"}

        # 1. Create Bounty - OK
        res1 = self.client.post(
            "/bounties",
            json={
                "title": "Bounty 1",
                "description": "Desc",
                "micro_reward": 100000,
                "idempotency_key": str(uuid.uuid4()),
                "evaluation_spec": "pass",
                "solution_template": "pass",
            },
            headers=headers,
        )
        self.assertEqual(res1.status_code, 200)

        # 2. Create Bounty Immediately - 429
        res2 = self.client.post(
            "/bounties",
            json={
                "title": "Bounty 2",
                "description": "Desc",
                "micro_reward": 100000,
                "idempotency_key": str(uuid.uuid4()),
                "evaluation_spec": "pass",
                "solution_template": "pass",
            },
            headers=headers,
        )
        self.assertEqual(res2.status_code, 429)


if __name__ == "__main__":
    unittest.main()
