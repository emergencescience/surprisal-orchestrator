import os
import sys
import unittest
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Adjust path to import api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_session
from core.models import Bounty, User
from main import app


class TestBountySearch(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.user = User(username="searcher", api_key="search-key", provider_id="search-provider")
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)

        app.dependency_overrides[get_session] = lambda: self.session
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.session.close()

    @patch("routes.bounties.select")
    def test_search_bounties_mocked(self, mock_select):
        # We need to mock the behavior because SQLite doesn't support l2_distance
        # Actually, it's easier to mock the whole session.exec call in the route if we can.
        # But let's try to mock what we can.

        bounty = Bounty(
            id=uuid.uuid4(),
            title="Vector Bounty",
            description="Test",
            owner_id=self.user.id,
            idempotency_key=uuid.uuid4(),
            micro_reward=1000,
            status="open",
            created_at=datetime.now(UTC),
            embedding=[0.1] * 1536,
        )

        # Mocking session.exec to return our bounty
        mock_session = MagicMock(spec=Session)
        mock_session.exec.return_value.all.return_value = [bounty]

        app.dependency_overrides[get_session] = lambda: mock_session

        resp = self.client.post("/bounties/search", json={"query_embedding": [0.1] * 1536, "limit": 5})

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Vector Bounty")


if __name__ == "__main__":
    unittest.main()
