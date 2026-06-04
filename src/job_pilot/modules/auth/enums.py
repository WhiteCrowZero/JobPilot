from __future__ import annotations

from enum import StrEnum


class AuthProvider(StrEnum):
    EMAIL = "email"
    PHONE = "phone"
    GITHUB = "github"
    GOOGLE = "google"
