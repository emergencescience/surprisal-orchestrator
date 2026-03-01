
import os
import sys
import unittest

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Adjust path to import api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid

from core.database import get_session
from core.models import User
from core.security import get_current_user
from main import app


class TestBountyValidation(unittest.TestCase):
    def setUp(self):
        # Use in-memory SQLite for testing
        self.engine = create_engine(
            "sqlite://", 
            connect_args={"check_same_thread": False}, 
            poolclass=StaticPool
        )
        SQLModel.metadata.create_all(self.engine)
        
        self.session = Session(self.engine)
        
        # Create a test user
        self.user = User(username="testuser", api_key="test-key", provider_id="test-provider", micro_credits=100_000_000)
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)

        # Override dependencies
        def get_session_override():
            return self.session

        def get_current_user_override():
            return self.user

        app.dependency_overrides[get_session] = get_session_override
        app.dependency_overrides[get_current_user] = get_current_user_override
        
        # Disable rate limiting for logic tests
        app.state.limiter.enabled = False
        
        self.client = TestClient(app)

    def tearDown(self):
        app.state.limiter.enabled = True # Re-enable for other tests
        app.dependency_overrides.clear()
        self.session.close()

    def test_create_bounty_success(self):
        response = self.client.post("/bounties", json={
            "title": "Valid Bounty",
            "description": "This is a valid bounty",
            "micro_reward": 1000000,
            "idempotency_key": str(uuid.uuid4()),
            "evaluation_spec": "import unittest\nclass Test(unittest.TestCase):\n  pass",
            "solution_template": "def solve(): pass"
        })
        if response.status_code != 200:
            print(f"Error: {response.json()}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "Valid Bounty")
        self.assertEqual(data["reward"], 1.0) # BountyRead returns float

    def test_create_bounty_negative_reward(self):
        response = self.client.post("/bounties", json={
            "title": "Invalid Reward",
            "description": "Negative reward",
            "micro_reward": -5,
            "idempotency_key": str(uuid.uuid4()),
            "evaluation_spec": "pass",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("positive number", response.json()["detail"])

    def test_create_bounty_zero_reward(self):
        response = self.client.post("/bounties", json={
            "title": "Zero Reward",
            "description": "Zero reward",
            "micro_reward": 0,
            "idempotency_key": str(uuid.uuid4()),
            "evaluation_spec": "pass",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("positive number", response.json()["detail"])

    def test_create_bounty_missing_evaluation_spec(self):
        response = self.client.post("/bounties", json={
            "title": "Missing Test Code",
            "description": "No test code",
            "micro_reward": 1000000,
            "idempotency_key": str(uuid.uuid4()),
            "evaluation_spec": ""
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("evaluation_spec is required", response.json()["detail"])

    def test_create_bounty_invalid_python_evaluation_spec(self):
        response = self.client.post("/bounties", json={
            "title": "Invalid Python",
            "description": "Bad python syntax",
            "micro_reward": 1000000,
            "idempotency_key": str(uuid.uuid4()),
            "evaluation_spec": "def broken_func(:" # Syntax error
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Syntax Error", response.json()["detail"])

if __name__ == "__main__":
    unittest.main()
