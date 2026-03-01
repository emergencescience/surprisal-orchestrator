import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from core.database import get_session
from core.models import User

security = HTTPBearer()

ADMIN_SECRET = os.getenv("ADMIN_SECRET", "super-secret-admin-key")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "your_github_client_id")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "your_github_client_secret")

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    session: Session = Depends(get_session)
) -> User:
    token = credentials.credentials
    user = session.exec(select(User).where(User.api_key == token)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="User deleted")
    
    # Attach to request.state for rate limiting and other middleware
    request.state.user = user
    return user
