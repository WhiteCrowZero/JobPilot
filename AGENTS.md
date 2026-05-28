# JobPilot Agent Rules

## 1. Project Principles

JobPilot is a FastAPI backend MVP. Product goals come first: build a runnable, maintainable backend system before adding crawler, AI, Kafka, Kubernetes, or other advanced components.

Prioritize:

- Small, verifiable steps
- Clear module boundaries
- Simple code over premature abstractions
- Backend business flow and service coordination

Do not introduce new dependencies, large refactors, or architecture changes without user confirmation.

---

## 2. Development Workflow

Follow MVP-first iteration:

1. Keep the project runnable.
2. Implement one module or one clear task at a time.
3. Verify each runtime change with tests or a concrete command.
4. Update this file when the project structure changes.
5. Keep README concise and user-facing.

Avoid full rewrites unless explicitly requested.

---

## 3. Tools and Environment

Use `uv` by default:

```bash
uv add <package>
uv remove <package>
uv run <command>
uv sync
```

Do not use `uv pip` unless the user explicitly asks for it.

Core stack:

- Python 3.12
- FastAPI
- SQLAlchemy 2.0 async
- Alembic
- PostgreSQL
- Redis
- Celery
- pytest
- Docker Compose

---

## 4. Verification and Testing

Runtime code changes should be verified.

Recommended commands:

```bash
uv run ruff check .
uv run pytest
uv run pyright
```

Do not add excessive tests. Cover core paths first: health check, auth, job import, deduplication, and application status changes.

---

## 5. Git Rules

- Do not perform Git write operations.
- Read-only Git commands are allowed.
- You may suggest branch names and commit messages.

---

## 6. Current Project Structure

```txt
JobPilot/
├── README.md                         # 简短项目说明，控制在 10 行以内
├── AGENTS.md                         # AI/协作规则与结构树
├── pyproject.toml                    # Python 项目、依赖、工具配置
├── uv.lock                           # uv 锁文件
├── pyrightconfig.json                # Pyright 类型检查配置
├── Makefile                          # 常用命令封装
├── .python-version                   # Python 版本
├── .env                              # 本地环境变量，不建议提交到 Git
├── .env.example                      # 环境变量示例，可提交
├── .gitignore                        # Git 忽略规则
├── .dockerignore                     # Docker 构建忽略规则
├── alembic.ini                       # Alembic 主配置
├── alembic/
│   ├── env.py                        # Alembic 异步迁移环境
│   └── versions/
│       └── .gitkeep                  # 迁移脚本目录占位
├── deploy/
│   ├── .env                          # Docker Compose 服务端口与密码
│   ├── Dockerfile                    # 后端镜像构建文件，后期使用
│   └── docker-compose.yml            # PostgreSQL、Redis、Adminer、Flower
├── docs/
│   ├── 项目草稿.md                   # 项目规划草稿
│   └── 初始项目说明.md               # 初始项目使用与结构说明
├── logs/
│   └── .gitkeep                      # 日志目录占位
├── scripts/
│   └── clean.ps1                     # Windows 清理脚本
├── storage/
│   ├── .gitkeep                      # 本地存储目录占位
│   └── uploads/
│       └── .gitkeep                  # 上传文件目录占位
├── src/
│   └── job_pilot/
│       ├── __init__.py
│       ├── main.py                   # FastAPI 应用入口
│       ├── api/
│       │   ├── __init__.py
│       │   ├── deps.py               # API 公共依赖，如数据库会话
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py         # v1 总路由
│       │       └── endpoints/
│       │           ├── __init__.py
│       │           └── health.py     # 健康检查接口
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py             # Pydantic Settings 配置
│       │   ├── exceptions.py         # 项目基础异常
│       │   └── redis.py              # Redis 异步客户端
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py               # SQLAlchemy DeclarativeBase
│       │   ├── models.py             # ORM 模型集中导入入口
│       │   └── session.py            # 异步数据库连接与 Session
│       ├── modules/
│       │   ├── __init__.py
│       │   ├── auth/                 # 登录认证模块，待实现
│       │   ├── users/                # 用户模块，待实现
│       │   ├── jobs/                 # 岗位模块，待实现
│       │   ├── applications/         # 投递模块，待实现
│       │   ├── interviews/           # 面试复盘模块，待实现
│       │   ├── study_tasks/          # 学习任务模块，待实现
│       │   └── imports/              # 数据导入模块，待实现
│       ├── utils/
│       │   └── __init__.py
│       └── workers/
│           ├── __init__.py
│           └── celery_app.py         # Celery 应用与测试任务
└── tests/
    ├── __init__.py
    ├── conftest.py                   # pytest 公共 fixture
    ├── unit/
    │   ├── __init__.py
    │   └── test_health.py            # 健康检查单元测试
    └── integration/
        └── __init__.py               # 集成测试目录
```
