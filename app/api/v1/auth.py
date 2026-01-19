# app/api/v1/auth.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models_user import User
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.deps import get_current_user  # make sure this exists in your project

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    displayName: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordIn(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=8)


@router.post("/register")
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()

    q = await db.execute(select(User).where(User.email == email))
    if q.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.displayName,
    )
    db.add(user)
    await db.commit()

    token = create_access_token(user.id)
    return {
        "user": {"id": user.id, "email": user.email, "displayName": user.display_name},
        "accessToken": token,
    }


@router.post("/login")
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()

    q = await db.execute(select(User).where(User.email == email))
    user = q.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user.last_login_at = datetime.utcnow()
    await db.commit()

    token = create_access_token(user.id)
    return {
        "user": {"id": user.id, "email": user.email, "displayName": user.display_name},
        "accessToken": token,
    }


@router.post("/logout")
async def logout(user=Depends(get_current_user)):
    # JWT is stateless; real invalidation needs a token blacklist table.
    # So: frontend deletes token and user is effectively logged out.
    return {"ok": True}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = await db.execute(select(User).where(User.id == user.id))
    db_user = q.scalar_one()

    if not verify_password(payload.currentPassword, db_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    db_user.password_hash = hash_password(payload.newPassword)
    await db.commit()

    # optional: issue fresh token so app can immediately continue
    new_token = create_access_token(db_user.id)
    return {"ok": True, "accessToken": new_token}
