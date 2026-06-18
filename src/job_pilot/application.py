from __future__ import annotations

from dataclasses import dataclass

from job_pilot.core.resources import AppResources
from job_pilot.modules.auth.contracts import EmailRegisterCommand, PhoneRegisterCommand
from job_pilot.modules.auth.service import AuthService, AuthTokenSnapshot, build_auth_service
from job_pilot.modules.ingestion.contracts import RawJobCollectedMessage
from job_pilot.modules.ingestion.service import (
    JobSourceConfig,
    RawJobIngestionResult,
    RawJobIngestionService,
    build_raw_job_ingestion_service,
)
from job_pilot.modules.job_collections.contracts import (
    JobCollectionCreateCommand,
    JobCollectionFolderCreateCommand,
    JobCollectionFolderUpdateCommand,
    JobCollectionListQuery,
    JobCollectionUpdateCommand,
)
from job_pilot.modules.job_collections.schemas import (
    JobCollectionFolderResponse,
    JobCollectionListResponse,
    JobCollectionResponse,
)
from job_pilot.modules.job_collections.service import (
    JobCollectionService,
    build_job_collection_service,
)
from job_pilot.modules.job_match.contracts import JobSkillCoverageResult, TargetSkillSummaryResult
from job_pilot.modules.job_match.service import JobMatchService, build_job_match_service
from job_pilot.modules.job_posts.contracts import JobPostSearchQuery
from job_pilot.modules.job_posts.schemas import (
    JobPostDetailResponse,
    JobPostFilterOptionsResponse,
    JobPostListResponse,
)
from job_pilot.modules.job_posts.service import JobPostService, build_job_post_service
from job_pilot.modules.job_skills.schemas import SkillListParams, SkillListResponse
from job_pilot.modules.job_skills.service import (
    JobSkillSyncService,
    SkillDictionaryService,
    build_job_skill_sync_service,
    build_skill_dictionary_service,
)
from job_pilot.modules.job_skills.skill_sync_contracts import RawSkillCandidate, SkillSyncResult
from job_pilot.modules.job_targets.contracts import (
    JobTargetCreateCommand,
    JobTargetListQuery,
    JobTargetUpdateCommand,
)
from job_pilot.modules.job_targets.schemas import (
    JobTargetListResponse,
    JobTargetResponse,
)
from job_pilot.modules.job_targets.service import JobTargetService, build_job_target_service
from job_pilot.modules.knowledge.contracts import KnowledgeTreeQuery
from job_pilot.modules.knowledge.schemas import (
    KnowledgeTreeListResponse,
)
from job_pilot.modules.knowledge.service import KnowledgeService, build_knowledge_service
from job_pilot.modules.user_skills.contracts import (
    UserSkillListQuery,
    UserSkillUpdateCommand,
    UserSkillUpsertCommand,
)
from job_pilot.modules.user_skills.schemas import (
    UserSkillListResponse,
    UserSkillResponse,
)
from job_pilot.modules.user_skills.service import UserSkillService, build_user_skill_service
from job_pilot.uow import UnitOfWorkFactory, build_sqlalchemy_uow_factory


@dataclass(slots=True)
class JobPilotAuthApi:
    """认证公开入口，屏蔽 HTTP 和 session 细节。"""

    resources: AppResources
    uow_factory: UnitOfWorkFactory
    service: AuthService

    async def register_with_email(self, payload: EmailRegisterCommand) -> AuthTokenSnapshot:
        """使用邮箱密码注册用户。"""

        async with self.uow_factory() as uow:
            return await self.service.register_with_email_password(
                uow.require_session(),
                payload=payload,
                cache=self.resources.require_cache(),
            )

    async def register_with_phone(self, payload: PhoneRegisterCommand) -> AuthTokenSnapshot:
        """使用手机号密码注册用户。"""

        async with self.uow_factory() as uow:
            return await self.service.register_with_phone_password(
                uow.require_session(),
                payload=payload,
                cache=self.resources.require_cache(),
            )

    async def login_with_email(self, *, email: str, password: str) -> AuthTokenSnapshot:
        """使用邮箱密码登录用户。"""

        async with self.uow_factory() as uow:
            return await self.service.login_with_email_password(
                uow.require_session(),
                email=email,
                password=password,
                cache=self.resources.require_cache(),
            )

    async def login_with_phone(self, *, phone: str, password: str) -> AuthTokenSnapshot:
        """使用手机号密码登录用户。"""

        async with self.uow_factory() as uow:
            return await self.service.login_with_phone_password(
                uow.require_session(),
                phone=phone,
                password=password,
                cache=self.resources.require_cache(),
            )

    async def refresh_login(self, *, refresh_token: str) -> AuthTokenSnapshot:
        """消费 refresh token 并签发新 token。"""

        async with self.uow_factory() as uow:
            return await self.service.refresh_login(
                uow.require_session(),
                refresh_token=refresh_token,
                cache=self.resources.require_cache(),
            )

    async def logout(self, *, refresh_token: str) -> None:
        """撤销 refresh token。"""

        await self.service.logout_by_token(
            refresh_token=refresh_token,
            cache=self.resources.require_cache(),
        )


@dataclass(slots=True)
class JobPilotJobPostApi:
    """岗位查询公开入口。"""

    resources: AppResources
    uow_factory: UnitOfWorkFactory
    service: JobPostService

    async def search(self, params: JobPostSearchQuery) -> JobPostListResponse:
        """查询岗位列表。"""

        async with self.uow_factory() as uow:
            return await self.service.search_job_posts(uow.require_session(), params)

    async def get_detail(self, *, job_post_id: int) -> JobPostDetailResponse:
        """读取岗位详情。"""

        async with self.uow_factory() as uow:
            return await self.service.get_job_post_detail(uow.require_session(), job_post_id)

    async def get_filter_options(self) -> JobPostFilterOptionsResponse:
        """读取岗位筛选项。"""

        async with self.uow_factory() as uow:
            return await self.service.get_filter_options(
                uow.require_session(),
                self.resources.require_cache(),
            )


@dataclass(slots=True)
class JobPilotSkillApi:
    """岗位技能公开入口。"""

    uow_factory: UnitOfWorkFactory
    dictionary_service: SkillDictionaryService
    sync_service: JobSkillSyncService

    async def list_skills(self, params: SkillListParams) -> SkillListResponse:
        """查询标准技能字典。"""

        async with self.uow_factory() as uow:
            return await self.dictionary_service.list_skills(uow.require_session(), params)

    async def sync_job_skills(
        self,
        *,
        job_post_id: int,
        candidates: list[RawSkillCandidate],
    ) -> SkillSyncResult:
        """同步某个岗位的标准技能标签。"""

        async with self.uow_factory() as uow:
            return await self.sync_service.sync_from_raw_candidates(
                db=uow.require_session(),
                job_post_id=job_post_id,
                candidates=candidates,
            )


@dataclass(slots=True)
class JobPilotWorkbenchApi:
    """用户工作台公开入口，聚合收藏、目标岗位、技能画像和匹配分析。"""

    uow_factory: UnitOfWorkFactory
    collection_service: JobCollectionService
    target_service: JobTargetService
    user_skill_service: UserSkillService
    match_service: JobMatchService

    async def create_collection_folder(
        self,
        *,
        user_id: int,
        payload: JobCollectionFolderCreateCommand,
    ) -> JobCollectionFolderResponse:
        """创建当前用户收藏夹。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.create_folder(
                uow.require_session(),
                user_id=user_id,
                payload=payload,
            )

    async def list_collection_folders(self, *, user_id: int) -> list[JobCollectionFolderResponse]:
        """查询当前用户收藏夹。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.list_folders(
                uow.require_session(),
                user_id=user_id,
            )

    async def update_collection_folder(
        self,
        *,
        user_id: int,
        folder_id: int,
        payload: JobCollectionFolderUpdateCommand,
    ) -> JobCollectionFolderResponse:
        """更新当前用户收藏夹。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.update_folder(
                uow.require_session(),
                user_id=user_id,
                folder_id=folder_id,
                payload=payload,
            )

    async def set_default_collection_folder(
        self,
        *,
        user_id: int,
        folder_id: int,
    ) -> JobCollectionFolderResponse:
        """设置当前用户默认收藏夹。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.set_default_folder(
                uow.require_session(),
                user_id=user_id,
                folder_id=folder_id,
            )

    async def archive_collection_folder(
        self,
        *,
        user_id: int,
        folder_id: int,
    ) -> JobCollectionFolderResponse:
        """归档当前用户收藏夹。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.archive_folder(
                uow.require_session(),
                user_id=user_id,
                folder_id=folder_id,
            )

    async def collect_job(
        self,
        *,
        user_id: int,
        payload: JobCollectionCreateCommand,
    ) -> JobCollectionResponse:
        """收藏或恢复岗位。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.collect_job(
                uow.require_session(),
                user_id=user_id,
                payload=payload,
            )

    async def list_collections(
        self,
        *,
        user_id: int,
        params: JobCollectionListQuery,
    ) -> JobCollectionListResponse:
        """查询当前用户岗位收藏。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.list_collections(
                uow.require_session(),
                user_id=user_id,
                params=params,
            )

    async def update_collection(
        self,
        *,
        user_id: int,
        collection_id: int,
        payload: JobCollectionUpdateCommand,
    ) -> JobCollectionResponse:
        """更新当前用户岗位收藏。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.update_collection(
                uow.require_session(),
                user_id=user_id,
                collection_id=collection_id,
                payload=payload,
            )

    async def remove_collection(self, *, user_id: int, collection_id: int) -> JobCollectionResponse:
        """软删除当前用户岗位收藏。"""

        async with self.uow_factory() as uow:
            return await self.collection_service.remove_collection(
                uow.require_session(),
                user_id=user_id,
                collection_id=collection_id,
            )

    async def create_target(
        self,
        *,
        user_id: int,
        payload: JobTargetCreateCommand,
    ) -> JobTargetResponse:
        """新增或恢复目标岗位。"""

        async with self.uow_factory() as uow:
            return await self.target_service.create_target(
                uow.require_session(),
                user_id=user_id,
                payload=payload,
            )

    async def list_targets(
        self,
        *,
        user_id: int,
        params: JobTargetListQuery,
    ) -> JobTargetListResponse:
        """查询当前用户目标岗位。"""

        async with self.uow_factory() as uow:
            return await self.target_service.list_targets(
                uow.require_session(),
                user_id=user_id,
                params=params,
            )

    async def update_target(
        self,
        *,
        user_id: int,
        target_id: int,
        payload: JobTargetUpdateCommand,
    ) -> JobTargetResponse:
        """更新当前用户目标岗位。"""

        async with self.uow_factory() as uow:
            return await self.target_service.update_target(
                uow.require_session(),
                user_id=user_id,
                target_id=target_id,
                payload=payload,
            )

    async def archive_target(self, *, user_id: int, target_id: int) -> JobTargetResponse:
        """归档当前用户目标岗位。"""

        async with self.uow_factory() as uow:
            return await self.target_service.archive_target(
                uow.require_session(),
                user_id=user_id,
                target_id=target_id,
            )

    async def upsert_user_skill(
        self,
        *,
        user_id: int,
        payload: UserSkillUpsertCommand,
    ) -> UserSkillResponse:
        """新增、更新或恢复当前用户技能画像。"""

        async with self.uow_factory() as uow:
            return await self.user_skill_service.upsert_user_skill(
                uow.require_session(),
                user_id=user_id,
                payload=payload,
            )

    async def list_user_skills(
        self,
        *,
        user_id: int,
        params: UserSkillListQuery,
    ) -> UserSkillListResponse:
        """查询当前用户技能画像。"""

        async with self.uow_factory() as uow:
            return await self.user_skill_service.list_user_skills(
                uow.require_session(),
                user_id=user_id,
                params=params,
            )

    async def update_user_skill(
        self,
        *,
        user_id: int,
        skill_id: int,
        payload: UserSkillUpdateCommand,
    ) -> UserSkillResponse:
        """更新当前用户技能画像。"""

        async with self.uow_factory() as uow:
            return await self.user_skill_service.update_user_skill(
                uow.require_session(),
                user_id=user_id,
                skill_id=skill_id,
                payload=payload,
            )

    async def archive_user_skill(self, *, user_id: int, skill_id: int) -> UserSkillResponse:
        """归档当前用户技能画像。"""

        async with self.uow_factory() as uow:
            return await self.user_skill_service.archive_user_skill(
                uow.require_session(),
                user_id=user_id,
                skill_id=skill_id,
            )

    async def analyze_job_skill_coverage(
        self,
        *,
        user_id: int,
        job_post_id: int,
        required_level: int = 3,
    ) -> JobSkillCoverageResult:
        """分析当前用户对某个岗位技能的覆盖情况。"""

        async with self.uow_factory() as uow:
            return await self.match_service.analyze_job_skill_coverage(
                uow.require_session(),
                user_id=user_id,
                job_post_id=job_post_id,
                required_level=required_level,
            )

    async def analyze_target_skill_coverage(
        self,
        *,
        user_id: int,
        target_id: int,
        required_level: int = 3,
    ) -> JobSkillCoverageResult:
        """分析当前用户某个目标岗位的技能覆盖情况。"""

        async with self.uow_factory() as uow:
            return await self.match_service.analyze_target_skill_coverage(
                uow.require_session(),
                user_id=user_id,
                target_id=target_id,
                required_level=required_level,
            )

    async def analyze_target_skill_summary(
        self,
        *,
        user_id: int,
        limit: int = 20,
        required_level: int = 3,
    ) -> TargetSkillSummaryResult:
        """统计当前用户目标岗位集合的技能摘要。"""

        async with self.uow_factory() as uow:
            return await self.match_service.analyze_target_skill_summary(
                uow.require_session(),
                user_id=user_id,
                limit=limit,
                required_level=required_level,
            )


@dataclass(slots=True)
class JobPilotIngestionApi:
    """岗位摄入公开入口。"""

    uow_factory: UnitOfWorkFactory

    async def consume_raw_job(
        self,
        *,
        source_config: JobSourceConfig,
        message: RawJobCollectedMessage,
    ) -> RawJobIngestionResult:
        """消费单条原始岗位消息。"""

        service = self._build_service(source_config)
        async with self.uow_factory() as uow:
            try:
                return await service.consume_raw_job_message(
                    session=uow.require_session(),
                    message=message,
                )
            except Exception:
                # 摄入失败记录由 service 写入 raw_job_records，属于需要保留的业务结果。
                await uow.commit()
                raise

    @staticmethod
    def _build_service(source_config: JobSourceConfig) -> RawJobIngestionService:
        """按来源构建摄入 service。"""

        return build_raw_job_ingestion_service(source_config)


@dataclass(slots=True)
class JobPilotLearningApi:
    """用户工作台公开入口，聚合收藏、目标岗位、技能画像和匹配分析。"""

    resources: AppResources
    uow_factory: UnitOfWorkFactory
    knowledge_service: KnowledgeService

    async def get_knowledge_tree(self, params: KnowledgeTreeQuery) -> KnowledgeTreeListResponse:
        """读取知识点树。"""

        async with self.uow_factory() as uow:
            return await self.knowledge_service.get_knowledge_trees(
                uow.require_session(),
                params=params,
                cache=self.resources.require_cache(),
            )


@dataclass(slots=True)
class JobPilot:
    """JobPilot 作为库使用时的公开业务入口。"""

    auth: JobPilotAuthApi
    job_posts: JobPilotJobPostApi
    skills: JobPilotSkillApi
    workbench: JobPilotWorkbenchApi
    ingestion: JobPilotIngestionApi
    learning: JobPilotLearningApi


def build_job_pilot(resources: AppResources) -> JobPilot:
    """按默认依赖组装 JobPilot 库公开入口。"""

    uow_factory = build_sqlalchemy_uow_factory(resources.require_database().session_factory)
    search_backend = resources.require_search_backend()

    return JobPilot(
        auth=JobPilotAuthApi(
            resources=resources,
            uow_factory=uow_factory,
            service=build_auth_service(),
        ),
        job_posts=JobPilotJobPostApi(
            resources=resources,
            uow_factory=uow_factory,
            service=build_job_post_service(search_backend=search_backend),
        ),
        skills=JobPilotSkillApi(
            uow_factory=uow_factory,
            dictionary_service=build_skill_dictionary_service(search_backend),
            sync_service=build_job_skill_sync_service(search_backend),
        ),
        workbench=JobPilotWorkbenchApi(
            uow_factory=uow_factory,
            collection_service=build_job_collection_service(),
            target_service=build_job_target_service(),
            user_skill_service=build_user_skill_service(),
            match_service=build_job_match_service(),
        ),
        ingestion=JobPilotIngestionApi(uow_factory=uow_factory),
        learning=JobPilotLearningApi(
            resources=resources,
            uow_factory=uow_factory,
            knowledge_service=build_knowledge_service(),
        ),
    )
