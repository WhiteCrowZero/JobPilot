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
- **不是爬虫项目**：爬虫只是数据来源适配器，MVP 先用 `data/sample/jobs.json` 或 seed 脚本准备岗位数据。
- **重后端工程能力**：重点在数据库设计、业务建模、权限隔离、查询性能、缓存、异步任务、测试和部署。

## 2. 技术栈

- **后端框架**：FastAPI、Pydantic v2
- **数据库**：PostgreSQL、SQLAlchemy 2.0、Alembic
- **缓存与任务**：Redis、Celery
- **认证安全**：JWT、Refresh Token、密码哈希
- **测试与质量**：pytest、pytest-asyncio、httpx、ruff、pyright
- **部署环境**：Docker Compose、uv

## 3. 领域模块

```text
src/job_pilot/modules/
  auth/             # 注册、登录、JWT、refresh token、会话撤销
  users/            # 用户资料、用户状态、当前用户读取
  job_posts/        # 岗位主数据、搜索筛选、详情查询、去重
  job_skills/       # 岗位技能标签、规则提取、热门技能统计
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

第一阶段只实现核心闭环，不强行完成所有模块。模块目录先作为领域边界存在，具体实现按开发路线逐步补齐。

### 3.1 当前实现状态

当前项目处于阶段 0：认证与用户模块建设中。

已完成：

- FastAPI 应用入口、`/api/v1/health` 健康检查。
- `auth` / `users` 基础分层：`router / schema / service / repository / model`。
- 用户注册、登录、当前用户读取、JWT access token / refresh token 基础签发与解析。
- `users`、`auth_accounts`、`user_sessions` 模型定义。
- App lifespan 统一管理数据库 engine、Redis 缓存连接、分布式锁、轻量消息队列。
- `AppResources.health_check()` 统一检查数据库、Redis、消息队列资源状态。
- Redis 缓存抽象、分布式锁抽象、轻量消息队列抽象、Celery app 基础配置。
- 基础单元测试：健康检查、JWT token 解析与类型校验。

阶段 0 仍需补齐：

- refresh token hash 落库到 `user_sessions`。
- refresh token 轮换、session 撤销、logout。
- 用户禁用后的 refresh / 当前用户访问校验。
- 首个 Alembic migration。
- 注册、登录、刷新、退出、当前用户接口测试。

## 4. MVP 范围

MVP 保留：

1. **用户认证**：注册、登录、当前用户、refresh token、logout。
    - auth
    - user
2. **岗位情报池**：岗位列表、详情、关键词/城市/薪资/技能筛选、fingerprint 去重。
    - job_posts
    - ingestion
3. **岗位技能**：规则词典提取技能标签，支持按技能筛选岗位。
    - job_skills
4. **用户工作台**：收藏岗位、设为目标岗位、维护个人技能画像。
    - job_collections
    - job_targets
    - user_skills
5. **技能差距分析**：输出 `matched / missing / weak` 技能列表。
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

| 模块                | 核心表                                                                 | 职责边界                                    |
|-------------------|---------------------------------------------------------------------|-----------------------------------------|
| `auth`            | `auth_accounts`、`user_sessions`                                     | 登录身份、密码哈希、refresh token session、会话撤销    |
| `users`           | `users`                                                             | 用户基础资料、用户状态、超级用户标记                      |
| `job_posts`       | `job_posts`、`job_sources`                                           | 岗位主数据、来源链接、fingerprint 去重、搜索筛选          |
| `job_skills`      | `skills`、`skill_aliases`、`job_post_skills`                          | 技能字典、技能别名、岗位技能关系、热门技能统计                 |
| `ingestion`       | `ingestion_tasks`、`raw_job_records`、`ingestion_errors`              | 外部岗位数据摄入、清洗、错误记录、幂等入库                   |
| `job_collections` | `job_collections`                                                   | 用户收藏岗位，必须按 `user_id` 隔离                 |
| `job_targets`     | `job_targets`                                                       | 用户目标岗位、准备状态、优先级                         |
| `user_skills`     | `user_skills`                                                       | 用户技能画像和掌握程度                             |
| `job_match`       | 可先不建表                                                               | 读取岗位技能和用户技能，输出 matched / missing / weak |
| `study_tasks`     | `study_tasks`                                                       | 围绕目标岗位和缺失技能生成学习任务                       |
| `knowledge`       | `knowledge_points`、`learning_resources`                             | 公共知识点、学习资料、技能分类                         |
| `questions`       | `interview_questions`、`question_mastery_records`、`practice_records` | 公共题库、用户掌握状态、练习记录                        |

`system` 不作为核心业务表归属模块。健康检查、缓存、日志、后台任务等横切能力优先放在 `api/`、`core/`、`workers/` 中。

## 6. 面试引导点

本项目用于从业务场景引导后端八股：

- 用户登录：JWT、refresh token、密码哈希、鉴权授权。
- 岗位去重：唯一约束、索引、并发插入、幂等。
- 岗位筛选：动态 SQL、联合索引、分页、慢查询。
- 技能标签：一对多、多对多、JSON 字段与关系表取舍。
- 用户数据隔离：越权访问、user_id 查询条件、权限依赖。
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
| PostgreSQL      | 开发数据库                   | `localhost:5432`        |
| PostgreSQL Test | 测试数据库                   | `localhost:5433`        |
| Redis           | 缓存、Celery broker/result | `localhost:6479`        |
| pgAdmin         | PostgreSQL Web 管理       | `http://localhost:8180` |
| Prometheus      | 指标采集与查询                 | `http://localhost:9090` |
| Grafana         | 监控面板                    | `http://localhost:3000` |

pgAdmin 默认登录账号来自 `deploy/.env`：

```text
admin@jobpilot.com / jobpilot_pgadmin
```

> 注意：`deploy/docker-compose.yml` 默认把 Redis 导出到 `6479`。如果使用 `deploy/.env.example` 或本机已有 Redis，请同步检查
`.env` 中的 `REDIS_URL`、`CELERY_BROKER_URL`、`CELERY_RESULT_BACKEND` 端口。

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

### 7.5 测试

```bash
APP_ENV=test uv run pytest
```

测试数据库使用 `.env.test` 中的配置，避免污染开发数据库。

测试目录分层：

| 目录 | 用途 |
|----|----|
| `tests/unit/` | 测纯函数、service、小型资源对象，不依赖真实 HTTP 服务 |
| `tests/api/` | 接口路径、后续进程内 API 测试辅助 |
| `tests/smoke/` | 类似 Postman 的真实 HTTP 冒烟测试，使用 `@pytest.mark.smoke` 标记，验证已启动服务是否健康 |

真实服务冒烟测试默认跳过。需要先启动 API、PostgreSQL、Redis，再显式允许 smoke 测试：

```bash
uv run uvicorn job_pilot.main:app --reload
uv run pytest tests/smoke --run-smoke
```

smoke 测试默认请求 `http://127.0.0.1:8000`。普通 `uv run pytest` 只会收集并跳过 smoke 测试，不会请求真实服务。

## 8. 开发路线

每个阶段都要同时产出：

```text
1. 代码
2. 测试
3. README / 学习文档
4. 涉及八股问题
```

| 阶段 | 目标          | 必须交付                                                                                                                                     |
|----|-------------|------------------------------------------------------------------------------------------------------------------------------------------|
| 0  | 认证闭环        | `users/auth_accounts/user_sessions`、register/login/me/refresh/logout、refresh token hash 落库、session revoke、migration、auth API 测试、JWT 八股文档 |
| 1  | 岗位主数据       | `job_posts/job_sources`、seed 数据导入、fingerprint 唯一约束、列表/详情/关键词/城市/薪资筛选、索引、API 测试                                                           |
| 2  | 技能标签        | `skills/skill_aliases/job_post_skills`、规则词典提取、按技能筛选、热门技能统计、去重测试                                                                          |
| 3  | 用户工作台       | 收藏、取消收藏、目标岗位、目标状态、用户技能画像、`user_id + job_id` 唯一约束、越权测试                                                                                    |
| 4  | 技能差距分析      | `matched/missing/weak` service、目标岗位匹配接口、纯 service 单元测试、边界用例                                                                              |
| 5  | 学习闭环        | 学习任务生成、题库推荐、题目掌握状态、公共题库和用户状态拆表、任务状态流转测试                                                                                                  |
| 6  | Cache Aside | 岗位详情、热门技能、任务进度缓存；cache miss/hit、写后删缓存、TTL、空值缓存测试                                                                                         |
| 7  | Celery 摄入   | `ingestion_tasks/raw_job_records/ingestion_errors`、异步清洗、技能提取、幂等入库、失败重试、部分失败状态                                                            |
| 8  | 工程化收尾       | Docker Compose API/Worker、完整迁移、集成测试、README 总览、简历讲法、八股索引                                                                                  |

阶段 1 要先提供轻量 seed / JSON 导入，保证系统早期就有岗位数据可查。阶段 7 再把摄入流程升级为 Celery 异步任务和幂等处理。

## 9. API 路线

接口设计按业务闭环推进，优先保证用户侧核心流程可用：

| 阶段 | API                                                                                                                                                                                     | 说明                        |
|----|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------|
| 0  | `POST /auth/register`、`POST /auth/login`、`POST /auth/refresh`、`POST /auth/logout`、`GET /users/me`                                                                                       | 完成登录态、刷新、退出和当前用户读取        |
| 1  | `GET /jobs`、`GET /jobs/{job_id}`                                                                                                                                                        | 岗位列表、详情、关键词/城市/薪资筛选       |
| 2  | `GET /skills`、`GET /skills/hot`、`GET /jobs?skill=python`                                                                                                                                | 技能字典、热门技能、按技能筛选岗位         |
| 3  | `POST /job-collections`、`DELETE /job-collections/{job_id}`、`GET /job-collections`、`POST /job-targets`、`GET /job-targets`、`PATCH /job-targets/{target_id}`、`PUT /user-skills/{skill_id}` | 用户收藏、目标岗位、技能画像            |
| 4  | `GET /job-targets/{target_id}/match`                                                                                                                                                    | 输出目标岗位与用户技能画像的差距          |
| 5  | `POST /study-tasks/generate`、`GET /study-tasks`、`PATCH /study-tasks/{task_id}`、`GET /questions/recommended`、`PUT /questions/{question_id}/mastery`                                      | 生成学习任务、推荐题目、记录掌握状态        |
| 6  | 无需新增业务 API                                                                                                                                                                              | 在岗位详情、热门技能、任务进度等高频读接口接入缓存 |
| 7  | `POST /ingestion/tasks`、`GET /ingestion/tasks/{task_id}`、`GET /ingestion/tasks/{task_id}/errors`                                                                                        | 创建摄入任务、查询状态、查看错误记录        |

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
