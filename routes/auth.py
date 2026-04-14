import os
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from core.database import get_session
from core.models import User, UserRead
from core.security import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, get_current_user

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://www.emergence.science")

router = APIRouter(tags=["Authentication"])

# Programmatic registration disabled for v1.0.0 due to missing verification logic.
# Use GitHub OAuth for onboarding.


@router.get("/auth/github/login")
def github_login():
    # Construct redirect URL for GitHub to send the code to the FRONTEND
    callback_url = f"{FRONTEND_URL}/auth/github/callback"
    return RedirectResponse(f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={callback_url}&scope=read:user")


@router.get("/auth/github/callback")
async def github_callback(code: str, session: Session = Depends(get_session)):
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
        )
        token_data = token_res.json()

    if "error" in token_data:
        raise HTTPException(status_code=400, detail=f"GitHub Error: {token_data.get('error_description')}")

    access_token = token_data["access_token"]

    async with httpx.AsyncClient() as client:
        user_res = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        github_user = user_res.json()

    provider_id = str(github_user["id"])
    github_login = github_user["login"]

    user = session.exec(select(User).where(User.provider_id == provider_id)).first()
    api_key = f"sk-surp-{secrets.token_hex(16)}"

    if user:
        user.api_key = api_key
        session.add(user)
        session.commit()
        session.refresh(user)
        message = "Welcome back!"
    else:
        username = github_login
        if session.exec(select(User).where(User.username == username)).first():
            username = f"{github_login}_gh_{secrets.token_hex(2)}"
        user = User(username=username, api_key=api_key, provider="github", provider_id=provider_id)
        session.add(user)
        session.commit()
        session.refresh(user)
        message = "Account created successfully!"

    return {"api_key": api_key, "username": user.username, "message": message}


@router.get("/users/me", response_model=UserRead)
def read_users_me(current_user: User = Depends(get_current_user)):
    return UserRead(id=current_user.id, username=current_user.username, micro_credits=current_user.micro_credits, created_at=current_user.created_at)
