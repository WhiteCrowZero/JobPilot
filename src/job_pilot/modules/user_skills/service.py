from __future__ import annotations

import logging
from dataclasses import MISSING

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.core.logging import log_app_event
from job_pilot.core.pagination import trim_page_items
from job_pilot.modules.user_skills.contracts import (
    UserSkillListQuery,
    UserSkillUpdateCommand,
    UserSkillUpsertCommand,
)
from job_pilot.modules.user_skills.enums import (
    UserSkillInterestLevel,
    UserSkillProficiencyLevel,
)
from job_pilot.modules.user_skills.exceptions import (
    StandardSkillNotFoundError,
    UserSkillNotFoundError,
)
from job_pilot.modules.user_skills.models import UserSkill
from job_pilot.modules.user_skills.repository import UserSkillRepository
from job_pilot.modules.user_skills.schemas import (
    UserSkillListResponse,
    UserSkillResponse,
)

logger = logging.getLogger(__name__)


class UserSkillService:
    """用户技能画像 service，负责业务校验和响应转换。"""

    def __init__(self, repository: UserSkillRepository) -> None:
        self.repository = repository

    async def upsert_user_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: UserSkillUpsertCommand,
    ) -> UserSkillResponse:
        """新增、更新或恢复当前用户技能画像。"""

        create_values = {
            "source": payload.source,
            "proficiency_level": payload.proficiency_level,
            "interest_level": payload.interest_level,
            "years_of_experience": payload.years_of_experience,
            "last_used_at": payload.last_used_at,
            "evidence": payload.evidence,
            "note": payload.note,
        }
        update_values = self._build_update_values(payload, exclude={"skill_id"})

        if not await self.repository.skill_exists(db, skill_id=payload.skill_id):
            raise StandardSkillNotFoundError()

        user_skill = await self.repository.upsert_active_skill(
            db,
            user_id=user_id,
            skill_id=payload.skill_id,
            create_values=create_values,
            update_values=update_values,
        )

        log_app_event(
            logger,
            "User skill upserted",
            extra={
                "event": "user_skills.upserted",
                "user_id": user_id,
                "skill_id": user_skill.skill_id,
                "user_skill_id": user_skill.id,
                "status": user_skill.status.value,
            },
        )
        return self._to_response(user_skill)

    async def list_user_skills(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: UserSkillListQuery,
    ) -> UserSkillListResponse:
        """分页读取当前用户技能画像。"""

        user_skills = await self.repository.list_user_skills(
            db,
            user_id=user_id,
            params=params,
        )
        page_items, has_next = trim_page_items(
            user_skills,
            page_size=params.page_size,
        )
        return UserSkillListResponse(
            items=[self._to_response(user_skill) for user_skill in page_items],
            page=params.page,
            page_size=params.page_size,
            total=None,
            has_next=has_next,
        )

    async def update_user_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_id: int,
        payload: UserSkillUpdateCommand,
    ) -> UserSkillResponse:
        """更新当前用户某个技能画像。"""

        user_skill = await self.repository.get_user_skill(
            db,
            user_id=user_id,
            skill_id=skill_id,
        )
        if user_skill is None:
            raise UserSkillNotFoundError()
        values = self._build_update_values(payload)
        if values:
            user_skill = await self.repository.update_user_skill(
                db,
                user_skill=user_skill,
                values=values,
            )
            log_app_event(
                logger,
                "User skill updated",
                extra={
                    "event": "user_skills.updated",
                    "user_id": user_id,
                    "skill_id": user_skill.skill_id,
                    "user_skill_id": user_skill.id,
                    "updated_fields": sorted(values.keys()),
                },
            )
        return self._to_response(user_skill)

    async def archive_user_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_id: int,
    ) -> UserSkillResponse:
        """归档当前用户某个技能画像。"""

        user_skill = await self.repository.archive_user_skill(
            db,
            user_id=user_id,
            skill_id=skill_id,
        )
        if user_skill is None:
            raise UserSkillNotFoundError()
        log_app_event(
            logger,
            "User skill archived",
            extra={
                "event": "user_skills.archived",
                "user_id": user_id,
                "skill_id": user_skill.skill_id,
                "user_skill_id": user_skill.id,
            },
        )
        return self._to_response(user_skill)

    @staticmethod
    def _build_update_values(
        payload: UserSkillUpdateCommand | UserSkillUpsertCommand,
        *,
        exclude: set[str] | None = None,
    ) -> dict[str, object]:
        values: dict[str, object] = {}
        excluded_fields = exclude or set()
        field_names = payload.fields_set or _changed_dataclass_fields(payload)
        for field_name in field_names:
            if field_name in excluded_fields:
                continue
            values[field_name] = getattr(payload, field_name)
        return values

    @staticmethod
    def _to_response(user_skill: UserSkill) -> UserSkillResponse:
        return UserSkillResponse(
            id=user_skill.id,
            user_id=user_skill.user_id,
            skill_id=user_skill.skill_id,
            status=user_skill.status,
            source=user_skill.source,
            proficiency_level=UserSkillProficiencyLevel(user_skill.proficiency_level),
            interest_level=UserSkillInterestLevel(user_skill.interest_level),
            years_of_experience=user_skill.years_of_experience,
            last_used_at=user_skill.last_used_at,
            evidence=user_skill.evidence,
            note=user_skill.note,
            assessed_at=user_skill.assessed_at,
            archived_at=user_skill.archived_at,
            created_at=user_skill.created_at,
            updated_at=user_skill.updated_at,
        )


def build_user_skill_service() -> UserSkillService:
    """组装用户技能画像 service 的默认依赖。"""

    return UserSkillService(repository=UserSkillRepository())


def _changed_dataclass_fields(payload: object) -> frozenset[str]:
    """推断直接构造 command 时显式改变过的字段。"""

    changed_fields: set[str] = set()
    for field_name, field_info in payload.__dataclass_fields__.items():  # type: ignore[attr-defined]
        if field_name == "fields_set" or field_info.default is MISSING:
            continue
        if getattr(payload, field_name) != field_info.default:
            changed_fields.add(field_name)
    return frozenset(changed_fields)
