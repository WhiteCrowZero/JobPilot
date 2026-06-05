from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from job_pilot.modules.auth.utils.phone import normalize_phone
from job_pilot.modules.users.schemas import UserRead


class PasswordRegisterBase(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


class EmailRegisterRequest(PasswordRegisterBase):
    email: EmailStr


class PhoneRegisterRequest(PasswordRegisterBase):
    phone: str = Field(min_length=8, max_length=16)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PhoneLoginRequest(BaseModel):
    phone: str = Field(min_length=8, max_length=16)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutResponse(BaseModel):
    status: str = "ok"


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
