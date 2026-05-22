import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import verify_password, hash_password, create_access_token
from app.database import get_db
from app.models.users import User
from app.schemas.auth import LoginRequest, RegisterRequest, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        logger.warning("auth.login_failed", extra={"email": body.email})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    logger.info("auth.login_success", extra={"email": user.username, "user_id": str(user.id)})
    return Token(access_token=create_access_token(user.username), token_type="bearer")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken")

    user = User(username=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("auth.register", extra={"username": user.username, "user_id": str(user.id)})
    return UserOut(id=str(user.id), username=user.username)
