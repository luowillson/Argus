from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.config import Settings, get_settings
from app.db.session import get_db


@dataclass(frozen=True)
class CurrentUser:
    """Identity of the requester. M2 returns a hardcoded demo user;
    swap this dependency to verify a Clerk JWT later without changing callers."""

    id: str
    email: str


def get_current_user(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    return CurrentUser(id=settings.demo_user_id, email=settings.demo_user_email)


DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
