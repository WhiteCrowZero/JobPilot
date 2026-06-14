from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from job_pilot.modules.job_skills.models import Skill
from job_pilot.modules.user_skills.enums import UserSkillStatus
from job_pilot.modules.user_skills.models import UserSkill
from job_pilot.modules.user_skills.schemas import UserSkillListParams


class UserSkillRepository:
    """用户技能画像数据库操作。"""

    async def skill_exists(self, db: AsyncSession, *, skill_id: int) -> bool:
        """判断标准技能是否存在。"""

        stmt = select(Skill.id).where(Skill.id == skill_id).limit(1)
        return await db.scalar(stmt) is not None

    async def get_user_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_id: int,
    ) -> UserSkill | None:
        """按用户和技能读取画像，避免跨用户访问。"""

        stmt = select(UserSkill).where(
            UserSkill.user_id == user_id,
            UserSkill.skill_id == skill_id,
        )
        return await db.scalar(stmt)

    async def list_user_skills(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        params: UserSkillListParams,
    ) -> list[UserSkill]:
        """分页读取当前用户技能画像。"""

        conditions: list[ColumnElement[bool]] = [UserSkill.user_id == user_id]
        if params.skill_ids:
            conditions.append(UserSkill.skill_id.in_(params.skill_ids))
        if not params.include_archived:
            conditions.append(UserSkill.status == UserSkillStatus.ACTIVE)

        stmt = (
            select(UserSkill)
            .where(*conditions)
            .order_by(
                UserSkill.proficiency_level.desc(),
                UserSkill.updated_at.desc(),
            )
        )
        stmt = stmt.offset(params.offset).limit(params.limit + 1)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_active_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_id: int,
        create_values: dict[str, object],
        update_values: dict[str, object],
    ) -> UserSkill:
        """新增或恢复 active 技能画像。

        新建记录使用 schema 默认值；已有记录只更新请求显式传入的字段，避免恢复时清空备注、
        证据、经验年限等已有信息。
        """

        insert_stmt = pg_insert(UserSkill).values(
            user_id=user_id,
            skill_id=skill_id,
            status=UserSkillStatus.ACTIVE,
            assessed_at=func.now(),
            archived_at=None,
            **create_values,
        )
        conflict_values: dict[str, object] = {
            "status": UserSkillStatus.ACTIVE,
            "assessed_at": func.now(),
            "archived_at": None,
            "updated_at": func.now(),
        }
        conflict_values.update(update_values)
        result = await db.execute(
            insert_stmt.on_conflict_do_update(
                constraint="uq_user_skills_user_skill",
                set_=conflict_values,
            )
            .returning(UserSkill)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one()

    async def update_user_skill(
        self,
        db: AsyncSession,
        *,
        user_skill: UserSkill,
        values: dict[str, object],
    ) -> UserSkill:
        """更新用户技能画像可编辑字段。"""

        values["updated_at"] = func.now()
        values["assessed_at"] = func.now()
        stmt = (
            update(UserSkill)
            .where(UserSkill.id == user_skill.id)
            .values(**values)
            .returning(UserSkill)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def archive_user_skill(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_id: int,
    ) -> UserSkill | None:
        """归档用户技能画像。"""

        stmt = (
            update(UserSkill)
            .where(
                UserSkill.user_id == user_id,
                UserSkill.skill_id == skill_id,
            )
            .values(
                status=UserSkillStatus.ARCHIVED,
                archived_at=func.now(),
                updated_at=func.now(),
            )
            .returning(UserSkill)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
