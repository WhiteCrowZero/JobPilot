from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from job_pilot.modules.user_skills.exceptions import (
    StandardSkillNotFoundError,
    UserSkillNotFoundError,
)
from job_pilot.modules.user_skills.models import UserSkill
from job_pilot.modules.user_skills.repository import UserSkillRepository
from job_pilot.modules.user_skills.schemas import (
    UserSkillListParams,
    UserSkillListResponse,
    UserSkillResponse,
    UserSkillUpdate,
    UserSkillUpsert,
)


class UserSkillService:
    """用户技能画像 service，负责业务校验和响应转换。"""

    def __init__(self, repository: UserSkillRepository) -> None:
        self.repository = repository

    async def upsert_user_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        payload: UserSkillUpsert,
    ) -> UserSkillResponse:
        """新增、更新或恢复当前用户技能画像。"""

        create_values = payload.model_dump(exclude={"skill_id"})
        update_values = payload.model_dump(exclude={"skill_id"}, exclude_unset=True)

        try:
            if not await self.repository.skill_exists(db, skill_id=payload.skill_id):
                raise StandardSkillNotFoundError()

            user_skill = await self.repository.upsert_active_skill(
                db,
                user_id=user_id,
                skill_id=payload.skill_id,
                create_values=create_values,
                update_values=update_values,
            )

            await db.commit()
        except Exception:
            await db.rollback()
            raise

        return self._to_response(user_skill)

    async def list_user_skills(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: UserSkillListParams,
    ) -> UserSkillListResponse:
        """分页读取当前用户技能画像。"""

        user_skills = await self.repository.list_user_skills(
            db,
            user_id=user_id,
            params=params,
        )
        has_next = len(user_skills) > params.page_size
        page_items = user_skills[: params.page_size]
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
        payload: UserSkillUpdate,
    ) -> UserSkillResponse:
        """更新当前用户某个技能画像。"""

        try:
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
                await db.commit()
        except Exception:
            await db.rollback()
            raise
        return self._to_response(user_skill)

    async def archive_user_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_id: int,
    ) -> UserSkillResponse:
        """归档当前用户某个技能画像。"""

        try:
            user_skill = await self.repository.archive_user_skill(
                db,
                user_id=user_id,
                skill_id=skill_id,
            )
            if user_skill is None:
                raise UserSkillNotFoundError()
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return self._to_response(user_skill)

    @staticmethod
    def _build_update_values(payload: UserSkillUpdate) -> dict[str, object]:
        values: dict[str, object] = {}
        for field_name in payload.model_fields_set:
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
            proficiency_level=user_skill.proficiency_level,
            interest_level=user_skill.interest_level,
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
