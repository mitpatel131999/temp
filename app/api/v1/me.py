# app/api/v1/me.py
from fastapi import APIRouter, Depends
from app.auth.deps import get_current_user
from app.db.models_user import User

router = APIRouter()

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "displayName": user.display_name,
        "createdAt": user.created_at,
    }
