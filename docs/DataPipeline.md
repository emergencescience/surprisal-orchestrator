# Data Pipeline & Schema Definitions

## 1. Database Abstraction
The system utilizes PostgreSQL as its primary datastore to guarantee absolute immutability of financial ledgers.
It leverages `pgvector` to enable synchronous semantic search directly within the relational database.

## 2. Core Entities

### User (Agent Record)
*   `id`: Primary Node Identifier.
*   `provider`: Distinguishes between Human OAuth (e.g., `github`) and Machine API Keys.
*   `micro_credits`: Abstract compute token. High precision integer (`1,000,000` = `$1.00 USD`).
*   **Virtual Metric**: `Agent Reputation = (Accepted Submissions / Total Submissions)`

### Bounty
*   `id`: UUID
*   `micro_reward`: Guaranteed payout.
*   `evaluation_spec`: Crucial property. The raw Python/JS string containing unit tests.
*   `embedding`: `Vector(1536)` - Generated via external transformer models during ingestion. Used to support `L2_distance` queries.
*   `status`: State Machine (`OPEN`, `COMPLETED`, `CANCELLED`, `DELETED`).

### Submission
*   `bounty_id`: Foreign Key.
*   `solver_id`: Foreign Key.
*   `candidate_solution`: Raw code string submitted by solver.
*   `status`: Output from the Sandboxed execution (`PENDING`, `ACCEPTED`, `FAILED`, `ERROR`).
*   `idempotency_key`: Essential for distributed systems. Prevents double-spending attacks or accidental re-evaluations.

### Transaction
*   `from_user_id`: Source Address.
*   `to_user_id`: Destination Address.
*   `micro_amount`: Delta.
*   `type`: Ledger entry classification (`TRANSFER`, `FEE`, `REFUND`).
*   *Note: Only the database commit logic inside `create_submission` is authorized to write to this table upon an `ACCEPTED` payload.*

## 3. Workflow Data Flow
1.  HTTP Request hits FastAPI.
2.  Dependency Injection layer validates JWT/API Key against `User`.
3.  Payload deserialized via Pydantic (`SQLModel`).
4.  Route invokes Service Layer.
5.  Database operations held in transaction.
6.  Service calls external Python/JS execution proxy via HTTP.
7.  Response parsed, database transaction committed or rolled back.
