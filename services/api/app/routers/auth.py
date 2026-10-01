from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.security.jwt import create_access_token, create_refresh_token, decode_refresh_token
from app.security.dependencies import get_current_user
from app.services.audit import write_audit
from app.services.verification import consume_code, hash_password, issue_code, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class EmailRequest(BaseModel):
    email: EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"userId": user.id, "email": user.email}


@router.post("/code")
def request_code(body: EmailRequest, request: Request, session: Session = Depends(get_session)) -> dict[str, str]:
    settings = get_settings()
    sender = getattr(request.app.state, "email_sender", None)
    if sender is None:
        raise HTTPException(status_code=503, detail="邮件发送通道不可用")
    issue_code(session, body.email, settings, sender)
    return {"status": "sent"}


@router.post("/register")
def register(
    body: RegisterRequest,
    session: Session = Depends(get_session),
) -> dict[str, str]:
    user = session.scalar(select(User).where(User.email == body.email))
    if user is None:
        raise HTTPException(status_code=400, detail="请先请求验证码")
    consume_code(session, body.email, body.code, get_settings())
    user.password_hash = hash_password(body.password)
    user.status = "active"
    session.add(user)
    session.flush()

    settings = get_settings()
    access = create_access_token(user.id, settings.jwt_secret, settings.access_token_expires_minutes)
    refresh = create_refresh_token(user.id, settings.jwt_secret, settings.refresh_token_expires_days)
    write_audit(session, user_id=user.id, action="auth.register", resource_type="user", resource_id=user.id, summary="邮箱注册")
    session.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "user_id": user.id}


@router.post("/login")
def login(body: LoginRequest, session: Session = Depends(get_session)) -> dict[str, str]:
    user = session.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        if user is not None:
            write_audit(session, user_id=user.id, action="auth.login", resource_type="user",
                        resource_id=user.id, result="failure", summary="密码错误")
            session.commit()
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    settings = get_settings()
    access = create_access_token(user.id, settings.jwt_secret, settings.access_token_expires_minutes)
    refresh = create_refresh_token(user.id, settings.jwt_secret, settings.refresh_token_expires_days)
    write_audit(session, user_id=user.id, action="auth.login", resource_type="user", resource_id=user.id, summary="邮箱登录")
    session.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "user_id": user.id}


@router.post("/refresh")
def refresh(body: RefreshRequest, session: Session = Depends(get_session)) -> dict[str, str]:
    settings = get_settings()
    try:
        payload = decode_refresh_token(body.refresh_token, settings.jwt_secret)
    except Exception:
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期") from None
    user = session.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    access = create_access_token(user.id, settings.jwt_secret, settings.access_token_expires_minutes)
    new_refresh = create_refresh_token(user.id, settings.jwt_secret, settings.refresh_token_expires_days)
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer", "user_id": user.id}
