from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.security.jwt import decode_access_token


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token, get_settings().jwt_secret)
    except Exception:
        raise HTTPException(status_code=401, detail="登录态无效或已过期") from None
    user = session.get(User, payload.get("sub"))
    if user is None or user.status != "active":
        raise HTTPException(status_code=401, detail="用户不可用")
    return user
