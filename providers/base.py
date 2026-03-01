from abc import ABC, abstractmethod

from pydantic import BaseModel


class ExecutionResult(BaseModel):
    status: str  # "accepted", "rejected", "failed"
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None


class ExecutionProvider(ABC):
    @abstractmethod
    def execute(self, solution: str, spec: str, language: str) -> ExecutionResult:
        pass
