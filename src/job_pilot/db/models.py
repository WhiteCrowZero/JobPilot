"""集中导入所有 SQLAlchemy 模型，确保 Alembic 能发现完整 metadata。"""

from __future__ import annotations

from job_pilot.modules.auth.models import AuthIdentity, AuthPasswordCredential
from job_pilot.modules.ingestion.models import RawJobRecord
from job_pilot.modules.job_collections.models import JobCollection, JobCollectionFolder
from job_pilot.modules.job_posts.models import (
    JobPost,
    JobPostDetail,
    JobSource,
)
from job_pilot.modules.job_skills.models import JobPostSkill, Skill, SkillAlias
from job_pilot.modules.job_targets.models import JobTarget
from job_pilot.modules.user_skills.models import UserSkill
from job_pilot.modules.users.models import User, UserProfile

__all__ = [
    "AuthIdentity",
    "AuthPasswordCredential",
    "User",
    "UserProfile",
    "JobPost",
    "JobPostDetail",
    "JobSource",
    "JobPostSkill",
    "Skill",
    "SkillAlias",
    "RawJobRecord",
    "JobCollectionFolder",
    "JobCollection",
    "JobTarget",
    "UserSkill",
]
