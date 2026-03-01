import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, SQLModel, create_engine

# Default to Docker service name 'db', fallback to localhost for local dev
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/surprisal_db")

# Rate Limiter Setup
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

engine = create_engine(DATABASE_URL)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    print("Database schema ensured.")

# Destructive reset removed for safety. 
# Use controlled migrations (Alembic) for schema changes in production.

def get_session():
    with Session(engine) as session:
        yield session
