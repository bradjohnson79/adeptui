"""Pydantic schemas for project security — never include password hashes."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ProjectProtectionPolicy(BaseModel):
    hideThumbnailWhenLocked: bool = True
    hideDescriptionWhenLocked: bool = True
    hideAssetCountsWhenLocked: bool = True
    hideSceneCountsWhenLocked: bool = True
    allowSearchByName: bool = True


class SecurityStatusOut(BaseModel):
    projectId: str
    passwordProtected: bool
    unlocked: bool = False
    passwordHint: Optional[str] = None
    passwordVersion: int = 0
    protectionUpdatedAt: Optional[str] = None
    policy: ProjectProtectionPolicy = Field(default_factory=ProjectProtectionPolicy)
    mock: bool = False


class SetPasswordBody(BaseModel):
    password: str = Field(min_length=12, max_length=256)
    confirmPassword: str = Field(min_length=12, max_length=256)
    passwordHint: str = Field(default="", max_length=200)


class UnlockBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    rememberFor: Literal["session", "15m", "1h"] = "session"
    sessionId: str = Field(default="", max_length=64)


class ChangePasswordBody(BaseModel):
    currentPassword: str = Field(min_length=1, max_length=256)
    newPassword: str = Field(min_length=12, max_length=256)
    confirmPassword: str = Field(min_length=12, max_length=256)


class DisablePasswordBody(BaseModel):
    currentPassword: str = Field(min_length=1, max_length=256)
    confirm: bool = False


class ResetPasswordBody(BaseModel):
    """Owner reset after local account re-auth stub (local-first)."""

    accountConfirmation: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=12, max_length=256)
    confirmPassword: str = Field(min_length=12, max_length=256)


class UnlockSuccessOut(BaseModel):
    ok: bool = True
    projectId: str
    unlockToken: str
    expiresAt: str
    passwordProtected: bool = True
    mock: bool = False


class DuplicateProtectionBody(BaseModel):
    mode: Literal["same_password", "new_password", "none"] = "none"
    password: str = ""
    confirmPassword: str = ""


DEFAULT_POLICY = ProjectProtectionPolicy()
