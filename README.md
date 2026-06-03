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

第一阶段只实现核心闭环，不强行完成所有模块。

## 4. MVP 范围

MVP 保留：

1. **用户认证**：注册、登录、当前用户、refresh token、logout。
2. **岗位情报池**：岗位列表、详情、关键词/城市/薪资/技能筛选、fingerprint 去重。
3. **岗位技能**：规则词典提取技能标签，支持按技能筛选岗位。
4. **用户工作台**：收藏岗位、设为目标岗位、维护个人技能画像。
5. **技能差距分析**：输出 `matched / missing / weak` 技能列表。
6. **学习准备闭环**：根据缺失技能创建学习任务，推荐八股题，记录掌握状态。

MVP 暂不做：

- 真实爬虫、RAG、AI 模拟面试、简历深度分析。
- 投递状态管理、offer/rejected 状态流转。
- Kafka、Kubernetes、WebSocket、复杂 RBAC、复杂监控。

## 5. 简历目标描述

> 基于 **FastAPI** 构建招聘岗位情报与求职准备平台，围绕岗位数据摄入、清洗去重、技能标签提取、岗位搜索筛选、目标岗位管理、技能差距分析、学习任务生成和八股题掌握记录，形成
**“岗位情报 → 技能分析 → 学习准备”** 的后端业务闭环。系统重点体现 **认证鉴权、数据建模、复杂查询、缓存优化、异步任务、幂等处理、测试与容器化部署
** 等后端工程能力。

## 6. 本地环境

### 6.1 安装依赖

```bash
uv sync
```

### 6.2 启动基础设施

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

默认服务：

| 服务              | 用途                      | 地址                      |
|-----------------|-------------------------|-------------------------|
| PostgreSQL      | 开发数据库                   | `localhost:5432`        |
| PostgreSQL Test | 测试数据库                   | `localhost:5433`        |
| Redis           | 缓存、Celery broker/result | `localhost:6479`        |
| pgAdmin         | PostgreSQL Web 管理        | `http://localhost:8180` |
| Prometheus      | 指标采集与查询                 | `http://localhost:9090` |
| Grafana         | 监控面板                    | `http://localhost:3000` |

pgAdmin 默认登录账号来自 `deploy/.env`：

```text
admin@jobpilot.com / jobpilot_pgadmin
```

### 6.3 启动后端

```bash
uv run uvicorn job_pilot.main:app --reload
```

接口文档：

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/v1/health
```

### 6.4 数据库迁移

```bash
uv run alembic revision --autogenerate -m "your message"
uv run alembic upgrade head
```

### 6.5 测试

```bash
APP_ENV=test uv run pytest
```

测试数据库使用 `.env.test` 中的配置，避免污染开发数据库。

## 7. 开发路线

| 阶段 | 目标                                      | 对应能力                     |
|----|-----------------------------------------|--------------------------|
| 0  | auth/users/session                      | JWT、Refresh Token、用户数据隔离 |
| 1  | job_posts/job_skills                    | 数据建模、查询筛选、唯一约束、索引        |
| 2  | job_collections/job_targets/user_skills | 用户工作台、权限隔离、业务状态          |
| 3  | job_match                               | 技能差距分析、service 层业务计算     |
| 4  | study_tasks/questions/mastery           | 学习闭环、公共题库与用户状态分离         |
| 5  | Redis cache                             | Cache Aside、缓存失效、热门统计缓存  |
| 6  | Celery ingestion                        | 异步任务、幂等、错误记录、任务状态        |
| 7  | tests/docker/docs                       | 可运行、可测试、可迁移、可复盘          |

## 8. 面试引导点

本项目用于从业务场景引导后端八股：

- 用户登录：JWT、refresh token、密码哈希、鉴权授权。
- 岗位去重：唯一约束、索引、并发插入、幂等。
- 岗位筛选：动态 SQL、联合索引、分页、慢查询。
- 技能标签：一对多、多对多、JSON 字段与关系表取舍。
- 用户数据隔离：越权访问、user_id 查询条件、权限依赖。
- 缓存：Redis、Cache Aside、缓存穿透/击穿/雪崩。
- 异步摄入：Celery、消息队列、任务状态、失败重试、重复消费。
- 测试部署：pytest、测试数据库隔离、Alembic、Docker Compose。
