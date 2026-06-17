from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class EmailRegisterCommand:
    """邮箱注册内部命令。"""

    email: str
    password: str
    display_name: str


@dataclass(slots=True, frozen=True)
class PhoneRegisterCommand:
    """手机号注册内部命令。"""

    phone: str
    password: str
    display_name: str
