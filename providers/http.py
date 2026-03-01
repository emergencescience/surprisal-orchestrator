from .base import ExecutionProvider, ExecutionResult


class HttpExecutionProvider(ExecutionProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url

    def execute(self, solution: str, spec: str, language: str) -> ExecutionResult:
        import httpx

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{self.base_url}/execute",
                    json={"solution": solution, "test": spec, "language": language}
                )
                data = resp.json()
                return ExecutionResult(
                    status=data.get("status", "failed"),
                    stdout=data.get("stdout"),
                    stderr=data.get("stderr"),
                    error=data.get("error")
                )
        except Exception as e:
            return ExecutionResult(status="failed", stderr=f"[SYSTEM]: Failed to connect to Sandbox Service: {str(e)}")
