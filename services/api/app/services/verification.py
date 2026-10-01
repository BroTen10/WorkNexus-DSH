"""邮箱验证码：哈希存储、一次性消费、节流与错误次数限制。"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any, Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import EmailVerificationCode, User
from app.models.identity import as_utc, utcnow
from app.services.audit import write_audit


class EmailSender(Protocol):
    def send_code(self, email: str, code: str) -> None: ...


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
        return secrets.compare_digest(digest, bytes.fromhex(digest_hex))
    except Exception:
        return False


def issue_code(session: Session, email: str, settings: Settings, sender: EmailSender) -> None:
    latest = session.scalar(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.email == email)
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    now = utcnow()
    if latest and (now - as_utc(latest.created_at)).total_seconds() < settings.email_code_resend_seconds:
        raise HTTPException(status_code=429, detail="验证码发送过于频繁，请稍后再试")

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(secrets.token_urlsafe(32)), status="active")
        session.add(user)
        session.flush()
    row = EmailVerificationCode(
        user_id=user.id if user else None,
        email=email,
        code_hash=hash_code(code),
        expires_at=now + timedelta(minutes=settings.email_code_ttl_minutes),
    )
    session.add(row)
    session.flush()
    sender.send_code(email, code)
    write_audit(
        session,
        user_id=user.id,
        action="auth.code_requested",
        resource_type="email",
        resource_id=email,
        summary="验证码请求",
    )
    session.commit()


def consume_code(session: Session, email: str, code: str, settings: Settings) -> EmailVerificationCode:
    row = session.scalar(
        select(EmailVerificationCode)
        .where(EmailVerificationCode.email == email)
        .where(EmailVerificationCode.consumed_at.is_(None))
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    if as_utc(row.expires_at) < utcnow():
        raise HTTPException(status_code=400, detail="验证码已过期")
    if row.attempt_count >= settings.email_code_max_attempts:
        raise HTTPException(status_code=429, detail="验证码错误次数过多，请重新申请")
    if not secrets.compare_digest(row.code_hash, hash_code(code)):
        row.attempt_count += 1
        session.commit()
        raise HTTPException(status_code=400, detail="验证码无效")
    row.consumed_at = utcnow()
    session.flush()
    return row
