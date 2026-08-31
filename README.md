# JobPilot

## 1. 项目定位

JobPilot 面向求职者和后端学习场景，围绕招聘岗位数据建立“岗位情报 → 技能分析 → 学习准备”的业务闭环：

```text
爬虫采集岗位
  -> Celery + RabbitMQ 投递岗位导入任务
  -> Worker 消费任务并写入 RawJobRecord
  -> 字段规范化、fingerprint 去重、JobPost upsert
  -> LLM 技能抽取与 JobPostSkill 同步
  -> 用户选择目标岗位、维护 UserSkill
  -> 基于 skill_id + level 计算 matched / weak / missing
  -> 根据技能缺口生成学习任务和题目练习
```

## 2. 技术栈

- **后端框架**：FastAPI、Pydantic v2
- **数据库**：PostgreSQL、SQLAlchemy 2.0、Alembic
- **缓存与异步**：Redis、RabbitMQ、Celery
- **认证安全**：JWT Access Token、Refresh Token、User Session、Access Token Blacklist
- **测试与质量**：pytest、pytest-asyncio、httpx、ruff、pyright
- **部署环境**：Docker Compose、uv

## 3. 领域模块

```text
src/job_pilot/modules/
  auth/             # 注册、登录、JWT access/refresh token、UserSession 会话管理
  users/            # 用户资料、用户状态、当前用户读取
  job_posts/        # 岗位主数据、搜索筛选、详情查询、fingerprint 去重
  job_skills/       # 技能字典、别名归一、岗位技能关系、按技能筛选
  ingestion/        # RawJobRecord、导入幂等、字段规范化、错误记录、重放入口
  job_collections/  # 用户收藏岗位
  job_targets/      # 用户目标岗位
  user_skills/      # 用户技能画像
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

## 4. 本地环境

### 4.1 安装依赖

```powershell
uv sync
```

### 4.2 启动基础设施

P1 之前 Docker 只提供基础设施：PostgreSQL、测试 PostgreSQL、Redis、RabbitMQ。API 和 Worker 暂时使用本地 `uv run`
启动，避免镜像构建和容器内调试干扰主线开发。

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

### 4.3 启动 API

```powershell
uv run uvicorn job_pilot.main:app --reload
```

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/v1/health
```

### 4.4 启动 Worker

```powershell
uv run celery -A job_pilot.workers.celery_app:celery_app worker -P solo -l info
```

按队列启动：

```powershell
uv run celery -A job_pilot.workers.celery_app:celery_app worker -P solo -Q job.ingestion -l info
```

独立 simulator 与完整联调步骤见 [`docs/mq_integration.md`](docs/mq_integration.md)。

### 4.5 数据库迁移

```powershell
uv run alembic revision --autogenerate -m "your message"
uv run alembic upgrade head
```

### 4.6 测试与质量检查

```powershell
$env:APP_ENV = "test"; uv run pytest
uv run ruff check .
uv run pyright
```

## 5. 阶段完成标准

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
