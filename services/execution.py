import os

from providers.base import ExecutionResult
from providers.docker import DockerExecutionProvider
from providers.http import HttpExecutionProvider
from services.safety import validate_code_safety


class NodeCoordinator:
    """
    Central registry for pluggable and scalable verification nodes.
    Future versions will query a database of registered nodes to route compute 
    based on the lowest latency, cost, or node reputation.
    """
    @classmethod
    def get_provider_for_language(cls, language: str):
        if language == "javascript":
            js_url = os.getenv("JS_SANDBOX_URL")
            if js_url:
                return HttpExecutionProvider(js_url)

        if language == "python3":
            py_url = os.getenv("PYTHON_SANDBOX_URL")
            if py_url:
                return HttpExecutionProvider(py_url)

        # Default to Docker (Local/Dev)
        return DockerExecutionProvider()


def execute_submission_sync(solution_code: str, evaluation_spec: str, language: str = "python3") -> ExecutionResult:
    """
    Dispatcher for code execution. Validates safety and routes to the Verification Network.
    """
    # 0. Safety Checks
    for code, label in [(solution_code, ""), (evaluation_spec, "Evaluation Spec Error: ")]:
        err = validate_code_safety(code, language)
        if err:
            return ExecutionResult(status="rejected", stderr=f"{label}{err}")

    # 1. Provider Routing via Coordinator
    provider = NodeCoordinator.get_provider_for_language(language)
    return provider.execute(solution_code, evaluation_spec, language)
