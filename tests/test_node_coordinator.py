import os
import sys
import unittest
from unittest.mock import patch

# Adjust path to import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from providers.docker import DockerExecutionProvider
from providers.http import HttpExecutionProvider
from services.execution import NodeCoordinator


class TestNodeCoordinator(unittest.TestCase):
    @patch.dict(os.environ, {"JS_SANDBOX_URL": "http://js-sandbox", "PYTHON_SANDBOX_URL": "http://py-sandbox"})
    def test_get_provider_javascript(self):
        provider = NodeCoordinator.get_provider_for_language("javascript")
        self.assertIsInstance(provider, HttpExecutionProvider)
        self.assertEqual(provider.base_url, "http://js-sandbox")

    @patch.dict(os.environ, {"JS_SANDBOX_URL": "http://js-sandbox", "PYTHON_SANDBOX_URL": "http://py-sandbox"})
    def test_get_provider_python3(self):
        provider = NodeCoordinator.get_provider_for_language("python3")
        self.assertIsInstance(provider, HttpExecutionProvider)
        self.assertEqual(provider.base_url, "http://py-sandbox")

    @patch.dict(os.environ, {})
    @patch.dict(os.environ, {"JS_SANDBOX_URL": "", "PYTHON_SANDBOX_URL": ""}, clear=True)
    def test_get_provider_default_docker(self):
        # Ensure env vars are missing
        with patch.dict(os.environ, {}, clear=True):
            provider = NodeCoordinator.get_provider_for_language("python3")
            self.assertIsInstance(provider, DockerExecutionProvider)

            provider = NodeCoordinator.get_provider_for_language("javascript")
            self.assertIsInstance(provider, DockerExecutionProvider)

    def test_get_provider_unsupported_language(self):
        provider = NodeCoordinator.get_provider_for_language("rust")
        self.assertIsInstance(provider, DockerExecutionProvider)


if __name__ == "__main__":
    unittest.main()
