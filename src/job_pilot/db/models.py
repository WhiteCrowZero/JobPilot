"""集中导入所有 SQLAlchemy 模型，确保 Alembic 能发现完整 metadata。"""

from __future__ import annotations

from job_pilot.modules.auth.models import AuthIdentity, AuthPasswordCredential
from job_pilot.modules.users.models import User, UserProfile

__all__ = [
    "AuthIdentity",
    "AuthPasswordCredential",
    "User",
    "UserProfile",
]
