# JobPilot

> **招聘岗位情报与求职准备平台**。本项目不是投递管理系统，也不是重 AI
> 项目；项目目标是让真实代码逐步对齐简历标准版本，围绕“岗位采集 → 岗位导入 → 技能匹配 → 学习任务生成”的闭环集中展示 *
*Python
后端开发能力**：认证鉴权、会话管理、数据建模、异步任务、幂等处理、用户数据隔离、测试与 Docker 部署。

## 1. 项目定位

JobPilot 面向求职者和后端学习场景，围绕招聘岗位数据建立“岗位情报 → 技能分析 → 学习准备”的业务闭环：

```text
Scrapy 爬虫采集岗位
  -> Celery + RabbitMQ 投递岗位导入任务
  -> Worker 消费任务并写入 RawJobRecord
  -> 字段规范化、fingerprint 去重、JobPost upsert
  -> 技能抽取与 JobPostSkill 同步
  -> 用户设为目标岗位、维护 UserSkill
  -> 基于 skill_id + level 计算 matched / weak / missing
  -> 根据技能缺口生成学习任务和题目练习
  -> 作答后更新任务进度，并按规则调整用户技能评级
```

项目边界：

- **不做投递流转**：不管理 `applied / offer / rejected` 等投递状态，岗位投递跳转到原平台。
- **不把 AI 作为主链路依赖**：当前学习任务生成以规则和题库为主，保证稳定、可解释、可测试。
- **爬虫是数据源适配器，不是项目主体**：本轮重点是打通爬虫与后端的 MQ 异步链路，而不是建设完整爬虫平台。
- **简历目标优先**：后续开发围绕简历中的强表述补齐代码证据、测试证据和演示链路。

## 2. 技术栈

- **后端框架**：FastAPI、Pydantic v2
- **数据库**：PostgreSQL、SQLAlchemy 2.0、Alembic
- **缓存与异步**：Redis、RabbitMQ、Celery
- **认证安全**：JWT Access Token、Refresh Token、User Session、Access Token Blacklist
- **搜索与后台增强**：Elasticsearch、Admin 后台（后续看时间）
- **测试与质量**：pytest、pytest-asyncio、httpx、ruff、pyright
- **部署环境**：Docker Compose、uv

## 3. 领域模块

```text
src/job_pilot/modules/
  auth/             # 注册、登录、JWT access/refresh token、UserSession、会话撤销
  users/            # 用户资料、用户状态、当前用户读取
  job_posts/        # 岗位主数据、搜索筛选、详情查询、fingerprint 去重
  job_skills/       # 技能字典、别名归一、岗位技能关系、按技能筛选
  ingestion/        # RawJobRecord、导入幂等、字段规范化、错误记录、重放入口
  job_collections/  # 用户收藏岗位
  job_targets/      # 用户目标岗位，表示“我要围绕这个岗位准备”
  user_skills/      # 用户技能画像、mastery_score、proficiency_level
  job_match/        # 岗位技能与用户技能差距分析
  study_tasks/      # 学习任务，围绕目标岗位和缺失技能生成
  knowledge/        # 知识点、技能分类、学习资料
  questions/        # 八股题、题目掌握记录、练习记录
  system/           # 健康检查、后台任务、缓存、日志等系统模块
```

```text
src/job_pilot/workers/
  celery_app.py       # Celery 初始化、队列、路由、重试策略
  tasks/              # import_raw_job、sync_job_skills、retry_failed_raw_job 等任务
```

## 4. 当前实现状态与下一阶段

| 阶段   | 状态        | 说明                                                                                             |
|------|-----------|------------------------------------------------------------------------------------------------|
| 阶段 0 | 已完成，待增强   | 已有注册、登录、JWT access/refresh token、当前用户、logout；下一步补 `user_sessions` 表、refresh rotation 与设备级会话管理。 |
| 阶段 1 | 已完成       | 岗位 raw 摄入、规范化入库、fingerprint 去重、岗位列表/详情/筛选、分页、filter-options 缓存。                                |
| 阶段 2 | 已完成       | 技能字典、技能别名、岗位技能关系、按技能筛选、岗位详情技能展示；岗位导入 Worker 已自动同步 `JobPostSkill`。                                  |
| 阶段 3 | 已完成       | 收藏夹、岗位收藏、目标岗位、用户技能画像、用户数据隔离。                                                                   |
| 阶段 4 | 已完成，待策略加强 | 已有 matched / weak / missing 技能差距分析；下一步统一 `skill_id + level` 匹配策略，并打通任务生成。                      |
| 阶段 5 | 已完成，待闭环联调 | 已有知识点、题库、学习任务、作答/跳过、进度得分；下一步接入技能差距结果，并补用户技能评级更新策略。                                             |
| 阶段 6 | 重点待做      | UserSession 表与会话管理。                                                                            |
| 阶段 7 | 基础完成      | RabbitMQ + 单一 Celery 摄入任务、独立 simulator、两事务恢复与重复消费联调已完成；DLQ/管理重放后续增强。                            |
| 阶段 8 | 重点待做      | 测试补强、代码质量审查、Docker 部署收口。                                                                       |
| 阶段 9 | 看时间       | 第三方登录、Elasticsearch、Admin、线上监控、前端页面。                                                           |

## 5. 本轮开发范围

### 5.1 必做范围

1. **添加 UserSession 表，支持会话管理**
    - 支持多设备登录、当前设备退出、全部设备退出、refresh token rotation、access token blacklist。
    - `Access Token` 与 `Refresh Token` 都携带 `session_jti`，服务端以 `user_sessions` 作为长期可信状态。

2. **添加 Celery + RabbitMQ，奠定异步链路基础**
    - RabbitMQ 作为 broker，Redis 继续用于缓存和 result backend。
    - Worker 负责岗位导入、技能同步、失败重试与后续任务扩展。

3. **联调爬虫和后端，跑通核心业务闭环**
    - 爬虫采集岗位并投递 MQ。
    - Worker 消费岗位消息并完成 RawJobRecord 落库、规范化、JobPost upsert、JobPostSkill 同步。
    - 用户目标岗位进入技能匹配，基于 `skill_id + level` 生成 matched / weak / missing。
    - 学习任务根据 weak / missing 技能生成，并在作答后更新用户技能评级。

4. **完善测试、代码质量审查、Docker 部署**
    - 补充认证会话、异步导入、重复消费、技能匹配、学习任务生成、用户隔离等测试。
    - 统一运行 `ruff / pyright / pytest`。
    - Docker Compose 至少能启动 PostgreSQL、Redis、RabbitMQ、API、Worker。

### 5.2 看时间增强

1. 第三方登录：OAuth2 登录入口，作为 auth 域增强。
2. Elasticsearch：替换岗位关键词搜索与复杂筛选中的文本检索部分。
3. Admin：岗位导入管理、失败记录重放、题库/知识点维护。
4. 线上监控：Prometheus / Grafana / 日志采集 / 基础告警。
5. 前端页面：优先做演示闭环页面，不做复杂交互。

### 5.3 本轮明确不做

- 额度、VIP、AI 调用扣费和 quota 预扣方案。
- 复杂 RBAC、完整审计系统、微服务拆分。
- Kubernetes、Kafka、WebSocket、复杂 Agent / RAG。

## 6. 模块表归属

| 模块                | 核心表                                                                                                              | 职责边界                                                      |
|-------------------|------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|
| `auth`            | `auth_identities`、`auth_password_credentials`、`user_sessions`                                                    | 登录身份、密码哈希、token 签发、refresh rotation、设备会话、token blacklist。 |
| `users`           | `users`、`user_profiles`                                                                                          | 用户主体、用户状态、超级用户标记、公开资料。                                    |
| `job_posts`       | `job_posts`、`job_sources`、`job_post_details`                                                                     | 岗位主数据、来源链接、fingerprint 去重、搜索筛选。                           |
| `job_skills`      | `skills`、`skill_aliases`、`job_post_skills`                                                                       | 技能字典、技能别名、岗位技能关系、岗位技能筛选。                                  |
| `ingestion`       | `ingestion_tasks`、`raw_job_records`、`ingestion_errors`                                                           | 外部岗位数据摄入、清洗、错误记录、幂等入库、失败重放。                               |
| `job_collections` | `job_collection_folders`、`job_collections`                                                                       | 用户收藏夹、默认收藏夹、岗位收藏，必须按 `user_id` 隔离。                        |
| `job_targets`     | `job_targets`                                                                                                    | 用户目标岗位、准备状态、优先级、主目标、收藏来源。                                 |
| `user_skills`     | `user_skills`                                                                                                    | 用户技能画像、`mastery_score`、`proficiency_level`。               |
| `job_match`       | 当前不建表                                                                                                            | 读取岗位技能、目标岗位和用户技能，输出 skill coverage 与目标岗位技能频率。             |
| `study_tasks`     | `study_tasks`、`study_task_snapshots`、`study_task_progress`、`study_task_questions`、`study_task_question_attempts` | 围绕目标岗位和缺失技能生成学习任务、题目动作和进度聚合。                              |
| `knowledge`       | `knowledge_points`                                                                                               | 公共知识点树和知识点搜索。                                             |
| `questions`       | `questions`、`question_options`、`question_answers`、`question_skills`                                              | 公共题库、选项、答案和题目技能关系。                                        |

## 7. 本地环境

### 7.1 安装依赖

```powershell
uv sync
```

### 7.2 启动基础设施

P1 之前 Docker 只提供基础设施：PostgreSQL、测试 PostgreSQL、Redis、RabbitMQ。API 和 Worker 暂时使用本地 `uv run` 启动，避免镜像构建和容器内调试干扰主线开发。

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --remove-orphans
```

核心服务：

| 服务                  | 用途                             | 默认地址                     |
|---------------------|--------------------------------|--------------------------|
| PostgreSQL          | 开发数据库                          | `127.0.0.1:15432`        |
| PostgreSQL Test     | 测试数据库                          | `127.0.0.1:15433`        |
| Redis               | 缓存、Celery result backend、短期黑名单 | `127.0.0.1:16379`        |
| RabbitMQ            | Celery broker、岗位导入队列           | `127.0.0.1:15674`        |
| RabbitMQ Management | 队列观察与调试                        | `http://127.0.0.1:15675` |

### 7.3 启动 API

```powershell
uv run uvicorn job_pilot.main:app --reload
```

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/v1/health
```

### 7.4 启动 Worker

```powershell
uv run celery -A job_pilot.workers.celery_app:celery_app worker -P solo -l info
```

按队列启动：

```powershell
uv run celery -A job_pilot.workers.celery_app:celery_app worker -P solo -Q job.ingestion -l info
```

独立 simulator 与完整联调步骤见 [`docs/mq_integration.md`](docs/mq_integration.md)。

### 7.5 数据库迁移

```powershell
uv run alembic revision --autogenerate -m "your message"
uv run alembic upgrade head
```

### 7.6 测试与质量检查

```powershell
$env:APP_ENV = "test"; uv run pytest
uv run ruff check .
uv run pyright
```

## 8. 开发路线

每个阶段都要同时产出：

```text
1. 代码
2. 测试
3. README / 学习文档
4. 涉及八股问题
```

| 优先级 | 任务                | 交付标准                                                       |
|-----|-------------------|------------------------------------------------------------|
| P0  | UserSession 会话管理  | 表、模型、迁移、登录/刷新/退出/全部退出/会话列表、access blacklist、并发 refresh 测试。 |
| P0  | Celery + RabbitMQ | Docker 服务、Celery app、队列配置、导入任务、重试与失败记录、Worker 启动文档。        |
| P0  | 爬虫与后端联调           | 爬虫 pipeline 投递岗位消息，Worker 自动完成导入、去重、技能同步。                  |
| P0  | 核心业务闭环            | 导入岗位 -> 目标岗位 -> 技能匹配 -> 学习任务生成 -> 作答 -> 用户技能评级更新。          |
| P0  | 测试与部署             | 认证、异步导入、匹配、任务生成、用户隔离测试；Docker Compose 跑 API + Worker。      |
| P1  | 第三方登录             | OAuth2 登录入口和账号绑定。                                          |
| P1  | Elasticsearch     | 岗位搜索接入 ES，保留 DB 查询作为降级方案。                                  |
| P1  | Admin             | 管理导入失败记录、岗位数据、题库和知识点。                                      |
| P1  | 线上监控              | 指标、日志、告警、Worker 健康状态。                                      |
| P1  | 前端页面              | 演示登录、岗位搜索、目标岗位、技能匹配、学习任务。                                  |

## 9. 阶段完成标准

一个阶段完成时至少满足：

- 运行时代码已按模块分层：`router / schema / service / repository / model`。
- 新增或变更数据库结构必须有 Alembic migration。
- 测试覆盖正常路径、关键异常路径、并发冲突与幂等处理场景。
- 模块 README 记录业务边界、核心流程、关键表、测试点。
- 验证命令至少执行：

```bash
uv run ruff check .
uv run pytest
uv run pyright
```
