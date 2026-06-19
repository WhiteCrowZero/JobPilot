# JobPilot

> **招聘岗位情报与求职准备平台**。本项目不是投递管理系统，也不是重 AI 项目；核心目标是通过一个真实业务闭环，集中展示 *
*Python 后端开发能力**：认证鉴权、数据建模、复杂查询、缓存、异步任务、幂等、测试、迁移和容器化部署。

## 1. 项目定位

JobPilot 面向求职者和后端学习场景，围绕招聘岗位数据建立“岗位情报 → 技能分析 → 学习准备”的业务闭环：

```text
外部岗位数据进入系统
  -> 清洗、去重、结构化存储
  -> 岗位搜索、筛选、技能标签统计
  -> 用户收藏岗位、设为目标岗位
  -> 对比岗位技能与用户技能画像
  -> 生成学习任务、推荐八股题
  -> 记录题目掌握状态和学习进度
```

项目边界：

- **不是投递系统**：不管理 `applied / offer / rejected` 等投递状态，岗位投递跳转到原平台。
- **不是重 AI 项目**：AI 只作为后续增强，MVP 先用规则词典实现技能提取和匹配分析。
- **不是爬虫项目**：爬虫只是数据来源适配器，MVP 先用 seed 脚本准备岗位数据。
- **重后端工程能力**：重点在数据库设计、业务建模、权限隔离、查询性能、缓存、异步任务、测试和部署。

## 2. 技术栈

- **后端框架**：FastAPI、Pydantic v2
- **数据库**：PostgreSQL、SQLAlchemy 2.0、Alembic
- **缓存与任务**：Redis、Celery
- **认证安全**：JWT、Refresh Token
- **测试与质量**：pytest、pytest-asyncio、httpx、ruff、pyright
- **部署环境**：Docker Compose、uv

## 3. 领域模块

```text
src/job_pilot/modules/
  auth/             # 注册、登录、JWT access/refresh token、密码凭证
  users/            # 用户资料、用户状态、当前用户读取
  job_posts/        # 岗位主数据、搜索筛选、详情查询、去重
  job_skills/       # 技能字典、别名归一、岗位技能关系、按技能筛选
  job_collections/  # 用户收藏岗位
  job_targets/      # 用户目标岗位，表示“我要围绕这个岗位准备”
  user_skills/      # 用户技能画像和掌握程度
  job_match/        # 岗位技能与用户技能差距分析
  study_tasks/      # 学习任务，围绕目标岗位和缺失技能生成
  knowledge/        # 知识点、技能分类、学习资料
  questions/        # 八股题、题目掌握记录、练习记录
  ingestion/        # 系统级岗位数据摄入、清洗、去重、错误记录
  system/           # 健康检查、后台任务、缓存、日志等系统模块
```

MVP 阶段只实现核心闭环，不强行完成所有模块。模块目录先作为领域边界存在，具体实现按开发路线逐步补齐。

**当前实现状态**

| 阶段 | 状态   | 说明                                                                                      | 学习文档                                    |
|----|------|-----------------------------------------------------------------------------------------|-----------------------------------------|
| 0  | 已完成  | 用户注册、登录、JWT access/refresh token、当前用户、logout                                            | `docs/八股文档/阶段0-用户注册与认证.md`              |
| 1  | 已完成  | 岗位 raw 摄入、规范化入库、fingerprint 去重、列表/详情/筛选、分页、filter-options 缓存                            | `docs/八股文档/阶段1-岗位主数据与搜索.md`             |
| 2  | 基础完成 | 技能字典、技能别名、岗位技能关系、按技能筛选、filter-options 技能候选；生产级 worker 编排后续补齐                            | `docs/ai_report/skill_phase2_review.md` |
| 3  | 已完成  | 用户收藏岗位、收藏夹、目标岗位、用户技能画像、用户数据隔离、工作台索引优化                                                   | `docs/ai_report/用户工作台*.md`              |
| 4  | 已完成  | 目标岗位技能覆盖分析：基于 job_post_skills 与 user_skills 做 matched / weak / missing 集合计算，并统计目标岗位高频技能 | `docs/ai_report/阶段4-目标岗位技能覆盖分析收口评估.md`  |
| 5  | 已完成  | 学习任务闭环：手动创建任务、从目标岗位技能缺口生成练习任务、作答/跳过、进度与得分、任务状态流转、用户数据隔离                          | 暂不新增汇报文档                                |

## 4. MVP 范围

本项目采用“技术学习型 MVP”原则：MVP 不是功能最少的 CRUD
原型，而是能体现后端工程能力的最小闭环；表结构和模块边界应贴近真实业务并保留合理扩展点，但每个阶段只实现当前主线必需的最小行为，避免一次性引入完整第三方登录、审计、设备管理、风控等复杂功能。

MVP 保留：

1. **用户认证**：注册、登录、当前用户、refresh token、logout。
    - auth
    - user
2. **岗位情报池**：岗位列表、详情、关键词/城市/薪资/技能筛选、fingerprint 去重。
    - job_posts
    - ingestion
3. **岗位技能**：维护标准技能字典和别名，支持岗位技能关系同步、岗位详情展示和按技能筛选。
    - job_skills
4. **用户工作台**：收藏岗位、设为目标岗位、维护个人技能画像。
    - job_collections
    - job_targets
    - user_skills
5. **技能差距分析**：基于结构化岗位技能和用户技能画像输出 `matched / weak / missing`，并统计目标岗位高频技能。
    - job_match
6. **学习准备闭环**：根据缺失技能创建学习任务，推荐八股题，记录掌握状态。
    - study_tasks
    - knowledge
    - questions

MVP 暂不做：

- 真实爬虫、RAG、AI 模拟面试、简历深度分析。
- 投递状态管理、offer/rejected 状态流转。
- Kafka、Kubernetes、WebSocket、复杂 RBAC、复杂监控。

## 5. 模块表归属

后续新增表时，优先按下面的归属放到对应模块，避免跨模块边界混乱：

| 模块                | 核心表                                                                 | 职责边界                                         |
|-------------------|---------------------------------------------------------------------|----------------------------------------------|
| `auth`            | `auth_identities`、`auth_password_credentials`                       | 登录身份、密码哈希、JWT token 签发与校验                    |
| `users`           | `users`、`user_profiles`                                             | 用户主体、用户状态、超级用户标记、公开资料                        |
| `job_posts`       | `job_posts`、`job_sources`、`job_post_details`                        | 岗位主数据、来源链接、fingerprint 去重、搜索筛选               |
| `job_skills`      | `skills`、`skill_aliases`、`job_post_skills`                          | 技能字典、技能别名、岗位技能关系、岗位技能筛选                      |
| `ingestion`       | `ingestion_tasks`、`raw_job_records`、`ingestion_errors`              | 外部岗位数据摄入、清洗、错误记录、幂等入库                        |
| `job_collections` | `job_collection_folders`、`job_collections`                          | 用户收藏夹、默认收藏夹、岗位收藏，必须按 `user_id` 隔离            |
| `job_targets`     | `job_targets`                                                       | 用户目标岗位、准备状态、优先级、主目标、收藏来源                     |
| `user_skills`     | `user_skills`                                                       | 用户技能画像和掌握程度                                  |
| `job_match`       | 当前不建表                                                               | 读取岗位技能、目标岗位和用户技能，输出 skill coverage 与目标岗位技能频率 |
| `study_tasks`     | `study_tasks`                                                       | 围绕目标岗位和缺失技能生成学习任务                            |
| `knowledge`       | `knowledge_points`、`learning_resources`                             | 公共知识点、学习资料、技能分类                              |
| `questions`       | `interview_questions`、`question_mastery_records`、`practice_records` | 公共题库、用户掌握状态、练习记录                             |

`system` 不作为核心业务表归属模块。健康检查、缓存、日志、后台任务等横切能力优先放在 `api/`、`core/`、`workers/` 中。

## 6. 面试引导点

本项目用于从业务场景引导后端八股：

- 用户登录：JWT、refresh token、密码哈希、鉴权授权。
- 岗位去重：唯一约束、索引、并发插入、幂等。
- 岗位筛选：动态 SQL、联合索引、分页、慢查询。
- 技能标签：一对多、多对多、JSON 字段与关系表取舍。
- 用户数据隔离：越权访问、user_id 查询条件、权限依赖。
- 用户工作台：软删除、归档恢复、默认收藏夹、主目标唯一、状态时间字段。
- 技能覆盖分析：集合交集、matched/weak/missing、无数据不打分、越权访问防护。
- 缓存：Redis、Cache Aside、缓存穿透/击穿/雪崩。
- 异步摄入：Celery、消息队列、任务状态、失败重试、重复消费。
- 测试部署：pytest、测试数据库隔离、Alembic、Docker Compose。

## 7. 本地环境

### 7.1 安装依赖

```bash
uv sync
```

### 7.2 启动基础设施

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

默认服务：

| 服务              | 用途                      | 地址                      |
|-----------------|-------------------------|-------------------------|
| PostgreSQL      | 开发数据库                   | `127.0.0.1:5432`        |
| PostgreSQL Test | 测试数据库                   | `127.0.0.1:5433`        |
| Redis           | 缓存、Celery broker/result | `127.0.0.1:6279`        |
| pgAdmin         | PostgreSQL Web 管理       | `http://127.0.0.1:8180` |
| Prometheus      | 指标采集与查询                 | `http://127.0.0.1:9090` |
| Grafana         | 监控面板                    | `http://127.0.0.1:3000` |

pgAdmin 默认登录账号来自 `deploy/.env`：

```text
admin@jobpilot.com / jobpilot_pgadmin
```

真实情况以 `deploy/.env` 为准。

### 7.3 启动后端

```bash
uv run uvicorn job_pilot.main:app --reload
```

接口文档：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/v1/health
```

### 7.4 数据库迁移

```bash
uv run alembic revision --autogenerate -m "your message"
uv run alembic upgrade head
```

查看当前版本：

```bash
alembic current
```

回滚：

```bash
alembic downgrade -1
```

### 7.5 测试

linux:

```bash
APP_ENV=test uv run pytest
```

windows:

```bash
$env:APP_ENV='test'
uv run pytest
```

测试数据库使用 `.env.test` 中的配置，避免污染开发数据库。

测试目录分层：

| 目录             | 用途                                                              |
|----------------|-----------------------------------------------------------------|
| `tests/unit/`  | 测纯函数、service、小型资源对象，不依赖真实 HTTP 服务                               |
| `tests/api/`   | 接口路径、后续进程内 API 测试辅助                                             |
| `tests/smoke/` | 类似 Postman 的真实 HTTP 冒烟测试，使用 `@pytest.mark.smoke` 标记，验证已启动服务是否健康 |

真实服务冒烟测试默认跳过。需要先启动 API、PostgreSQL、Redis，再显式允许 smoke 测试：

```bash
uv run uvicorn job_pilot.main:app --reload
uv run pytest tests/smoke --run-smoke
```

smoke 测试默认请求 `http://127.0.0.1:8000`。普通 `uv run pytest` 只会收集并跳过 smoke 测试，不会请求真实服务。

如果外部资源不同，可以检查`/health/readiness`接口，如果其中有资源出现问题，大概率是 Windows 的开放端口出现问题了（换成其他端口即可），检查命令：

```bash
netsh interface ipv4 show excludedportrange protocol=tcp
```

## 8. 开发路线

每个阶段都要同时产出：

```text
1. 代码
2. 测试
3. README / 学习文档
4. 涉及八股问题
```

| 阶段 | 状态   | 目标          | 必须交付                                                                                                                                   |
|----|------|-------------|----------------------------------------------------------------------------------------------------------------------------------------|
| 0  | 已完成  | 认证闭环        | `users/user_profiles/auth_identities/auth_password_credentials`、register/login/me/refresh、access/refresh token 轮换                      |
| 1  | 已完成  | 岗位主数据       | `job_posts/job_sources/job_post_details`、raw 摄入、fingerprint 唯一约束、列表/详情/关键词/城市/薪资筛选、分页、索引、filter-options 缓存                             |
| 2  | 基础完成 | 技能标签        | `skills/skill_aliases/job_post_skills`、别名归一、按技能筛选、岗位详情技能展示、filter-options 技能候选、同步 service 测试                                           |
| 3  | 已完成  | 用户工作台       | 用户技能画像、岗位收藏夹、默认收藏夹切换、收藏/取消/恢复、目标岗位、目标状态、主目标唯一、收藏来源校验、用户数据隔离、工作台索引优化                                                                    |
| 4  | 已完成  | 目标岗位技能覆盖分析  | 基于 `job_post_skills` 与 `user_skills` 做集合交集分析，输出 `matched / weak / missing`，并统计 active/paused 目标岗位高频技能；不分析 description，不引入 AI/embedding |
| 5  | 已完成  | 学习闭环        | 基于阶段 4 输出的 `weak_skills / missing_skills` 创建学习任务，维护任务状态，支持题目作答/跳过、进度得分、任务归档和用户隔离                                                   |
| 6  | 未开始  | Cache Aside | 岗位详情、热门技能、任务进度缓存；cache miss/hit、写后删缓存、TTL、空值缓存测试                                                                                       |
| 7  | 未开始  | Celery 摄入   | `ingestion_tasks/raw_job_records/ingestion_errors`、异步清洗、技能提取、幂等入库、失败重试、部分失败状态                                                          |
| 8  | 未开始  | 工程化收尾       | Docker Compose API/Worker、完整迁移、集成测试、README 总览、简历讲法、八股索引                                                                                |

阶段 1 先提供轻量 seed 导入，保证系统早期就有岗位数据可查。阶段 2 已完成技能字典与岗位技能关系的基础服务侧能力；阶段 3
已完成用户工作台闭环，当前用户可维护技能画像、收藏岗位、切换默认收藏夹、设置目标岗位并维护目标状态。阶段 4
已完成目标岗位技能覆盖分析，当前只基于 `job_post_skills` 与 `user_skills` 做集合计算，不分析
`job_post_details.description`，不引入 AI/embedding。阶段 5 已完成学习任务闭环，当前支持手动创建任务、
从目标岗位 missing/weak 技能缺口生成练习任务、提交作答、跳过题目、进度得分和任务状态流转。当前
`scripts/seed_jobs.py` 只负责岗位主数据导入，不在脚本内同步技能。后续会在独立 worker /
编排层中完成“岗位主数据摄入成功后，开启第二个事务同步岗位技能”的生产流程。下一阶段开始接入缓存，阶段 7 再把摄入流程升级为
Celery 异步任务和幂等处理。

## 9. API 路线

接口设计按业务闭环推进，优先保证用户侧核心流程可用：

| 阶段 | API                                                                                                                                                                                                                                                                                                              | 说明                                                 |
|----|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------|
| 0  | `POST /auth/register/email`、`POST /auth/register/phone`、`POST /auth/login/email`、`POST /auth/login/phone`、`POST /auth/refresh`、`POST /auth/logout`、`GET /users/me`                                                                                                                                               | 完成邮箱/手机号登录态、refresh 轮换、退出和当前用户读取                   |
| 1  | `GET /jobs`、`GET /jobs/{job_id}` 、`GET /jobs/filter-options`                                                                                                                                                                                                                                                     | 岗位列表、详情、关键词/城市/薪资筛选                                |
| 2  | `GET /skills`、`GET /jobs?skill_ids=1`、`GET /jobs/filter-options`                                                                                                                                                                                                                                                 | 技能字典、岗位详情技能展示、filter-options 技能候选、按技能筛选岗位          |
| 3  | `/user/skills`、`/jobs/collections/folders`、`/jobs/collections/folders/{folder_id}/default`、`/jobs/collections`、`/jobs/targets`                                                                                                                                                                                   | 用户技能画像、收藏夹、岗位收藏、目标岗位                               |
| 4  | `GET /jobs/match/jobs/{job_post_id}/coverage`、`GET /jobs/match/targets/{target_id}/coverage`、`GET /jobs/match/targets/skills`                                                                                                                                                                                    | 单岗位技能覆盖、目标岗位技能覆盖、目标岗位技能统计；只基于结构化技能集合计算             |
| 5  | `POST /learning/study-tasks`、`GET /learning/study-tasks`、`PATCH /learning/study-tasks/{task_id}`、`DELETE /learning/study-tasks/{task_id}`、`POST /learning/study-tasks/targets/{target_id}/generate`、`POST /learning/study-tasks/{task_id}/questions/{task_question_id}/attempts`、`POST /learning/study-tasks/{task_id}/questions/{task_question_id}/skip` | 创建学习任务、查询任务、更新/归档任务本体、从目标岗位缺口生成任务、提交作答和跳过题目；进度由作答行为派生 |
| 6  | 无需新增业务 API                                                                                                                                                                                                                                                                                                       | 在岗位详情、热门技能、任务进度等高频读接口接入缓存                          |
| 7  | `POST /ingestion/tasks`、`GET /ingestion/tasks/{task_id}`、`GET /ingestion/tasks/{task_id}/errors`                                                                                                                                                                                                                 | 创建摄入任务、查询状态、查看错误记录                                 |

## 10. 阶段完成标准

一个阶段完成时至少满足：

- 运行时代码已按模块分层：`router / schema / service / repository / model`。
- 新增或变更数据库结构必须有 Alembic migration。
- 测试覆盖正常路径、关键异常路径、权限隔离或幂等场景。
- 模块 README 记录业务边界、核心流程、关键表、测试点。
- 八股问题能从代码实现自然引出，不只停留在概念解释。
- 验证命令至少执行：

```bash
uv run ruff check .
uv run pytest
uv run pyright
```
