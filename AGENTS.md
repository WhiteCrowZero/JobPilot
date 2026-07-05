# JobPilot Agent 规则

## 1. 项目原则

JobPilot 是一个基于 FastAPI 构建的招聘岗位情报与求职准备后端项目。项目围绕“岗位采集 → 岗位导入 → 技能匹配 →
学习任务生成”的主线，建立：

```text
岗位情报 → 技能分析 → 学习准备
```

业务闭环目标：

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

---

## 2. 开发规范

1. 遵循 MVP 优先：先保证业务闭环正确，再做生产级增强；当前迭代期不需要为了兼容旧接口或旧表结构而保留冗余代码。
2. 每个阶段或模块尽量同时产出：
    ```text
    1. 代码
    2. 测试
    3. README / 状态文档 / 学习文档
    4. 涉及的八股问题
    ```
3. 业务模块按 `model / schema / contract / enum / exception / repository / service / router` 分层组织；`router` 只做 HTTP
   参数、鉴权依赖和调用，不写业务规则；`service` 负责业务判断、状态流转和异常；`repository` 负责 SQL 查询和持久化，不决定复杂业务语义。
4. 用户私有数据必须在查询条件中绑定 `user_id`；子资源操作必须同时校验父资源归属，例如 `task_question_id` 必须属于当前
   `task_id`，而 `task_id` 必须属于当前用户。
5. 所有 service 调用 repository 都写成“显式注入 + factory”，参考格式：
   `def build_xxx_service() -> XxxService: return XxxService(repository=XxxRepository())`。
6. 每个 `.py` 文件开头加 `from __future__ import annotations`；函数参数、返回值、类属性都写具体类型，尽量避免 `Any`。
7. 注释和文档使用中文，日志内容使用英文；每个函数和类尽量写一个简短总注释，特别简单的函数或类可以不写。
8. 文件读写统一使用 UTF-8；本地地址统一写 `127.0.0.1`，不要写 `localhost`。
9. service 的异常尽量使用 `src/job_pilot/core/exceptions.py` 或模块内 `exceptions.py` 中的异常，不要在业务层到处抛
   `HTTPException`。
10. 状态查询要统一：需要用户主动筛选时使用 `statuses`；普通用户不该看到的 archived/deleted/draft/rejected 数据默认不可见，不要用
    `include_archived` 这类混杂参数。
11. Schema 只拦截明显无意义、危险或会破坏业务流程的请求；需要查数据库才能判断的业务规则放到 service/repository。
12. 数据库索引只服务真实 `WHERE / JOIN / ORDER BY / UNIQUE / 幂等约束 / 后台摄入更新路径`，不要为低选择性字段、无调用路径字段或
    `ILIKE '%keyword%'` 提前乱建索引。
13. 写入模式按业务语义区分：收藏、目标岗位、用户技能等使用恢复型 upsert；raw 岗位和岗位主数据使用摄入型 upsert；普通 create
    冲突就是业务错误。
14. 日志不追求多，普通查询不大量打日志；关键业务事件在 service 层记录，禁止记录 password、token、完整请求体、答案正文、大
    payload 和原始 HTML。
15. 测试采用 AAA，测试名表达业务行为，重点覆盖用户隔离、归档默认不可见、恢复型 upsert、重复消费、学习任务幂等、作答进度、错误请求无副作用等核心不变量。

---

## 3. 工具与环境

默认使用 `uv` 进行依赖和环境管理：

```bash
uv add <package>
uv remove <package>
uv run <command>
uv sync
```

禁止使用：

```bash
uv pip
```

---

## 4. 验证与测试

所有运行时代码变更都应进行验证。

推荐验证命令：

```bash
uv run ruff format
uv run ruff check . --fix
uv run pytest
uv run pyright
```

要求：

1. AAA原则
2. 见名知意，比如：test_create_user_with_invalid_email()
3. 我提供的测试数据库：

---

## 5. 项目基本结构

我隐藏了一些不重要的文件，主要结构如下；真实文件以仓库当前内容为准，README 中的本轮目标优先：

```text
JobPilot/
|-- README.md
|-- AGENTS.md
|-- pyproject.toml
|-- .env
|-- .env.example
|-- .env.test
|-- alembic.ini
|-- alembic/
|-- deploy/
|   |-- .env
|   |-- .env.example
|   |-- Dockerfile
|   `-- docker-compose.yml
|-- docs/
|-- logs/
|-- scripts/
|-- src/
|   `-- job_pilot/
|       |-- main.py
|       |-- application.py
|       |-- api/
|       |   |-- deps.py
|       |   |-- health.py
|       |   `-- v1/
|       |       |-- jobs.py
|       |       |-- learning.py
|       |       |-- router.py
|       |       `-- users.py
|       |-- core/
|       |   |-- config.py
|       |   |-- enums.py
|       |   |-- cache.py
|       |   |-- exceptions.py
|       |   |-- message_queue.py
|       |   |-- pagination.py
|       |   |-- resources.py
|       |   |-- uow.py
|       |   |-- search/
|       |   `-- middleware/
|       |-- db/
|       |   |-- base.py
|       |   |-- models.py
|       |   |-- upsert.py
|       |   `-- session.py
|       |-- modules/
|       |   |-- auth/             # 注册、登录、JWT access/refresh token、UserSession、会话撤销
|       |   |-- users/            # 用户资料、用户状态、当前用户读取
|       |   |-- job_posts/        # 岗位主数据、搜索筛选、详情查询、fingerprint 去重
|       |   |-- job_skills/       # 技能字典、别名归一、岗位技能关系、按技能筛选
|       |   |-- ingestion/        # RawJobRecord、导入幂等、字段规范化、错误记录、重放入口
|       |   |-- job_collections/  # 用户收藏岗位
|       |   |-- job_targets/      # 用户目标岗位，表示“我要围绕这个岗位准备”
|       |   |-- user_skills/      # 用户技能画像、mastery_score、proficiency_level
|       |   |-- job_match/        # 岗位技能与用户技能差距分析
|       |   |-- study_tasks/      # 学习任务，围绕目标岗位和缺失技能生成
|       |   |-- knowledge/        # 知识点、技能分类、学习资料
|       |   |-- questions/        # 八股题、题目掌握记录、练习记录
|       |   `-- system/           # 健康检查、后台任务、缓存、日志等系统模块
|       `-- workers/
|           |-- celery_app.py       # Celery 初始化、队列、路由、重试策略
|           `-- tasks/              # import_raw_job、sync_job_skills、retry_failed_raw_job 等任务
`-- tests/
    |-- conftest.py
    |-- api/
    |-- unit/
    `-- integration/
```

## 6. 项目最终简历形态

> 一切都是奔着这个目标，实现功能的同时，学会相关知识点，能够讲好整个项目。

* **项目描述：** 基于 **FastAPI 模块化后端架构**
  开发的招聘岗位情报与求职准备平台，围绕岗位采集、岗位导入、结构化去重、技能标签同步、岗位搜索筛选、目标岗位管理、技能差距分析、学习任务生成和题目练习记录等场景，形成
  **“岗位情报 → 技能分析 → 学习准备”** 的后端业务闭环。系统重点体现 **认证鉴权、会话管理、数据建模、异步任务、幂等处理、用户数据隔离、测试与
  Docker 部署** 等后端工程能力。
* **技术栈：** **FastAPI、Pydantic v2、SQLAlchemy 2.0、Alembic、PostgreSQL、Redis、RabbitMQ、Celery、JWT、Docker Compose、pytest、uv
  **
* **个人职责：**
    1. 基于 **FastAPI + SQLAlchemy 2.0** 完成后端模块化设计，将系统拆分为 **用户认证、岗位数据、数据摄入、用户工作台、学习准备、缓存与异步任务
       ** 等领域模块，采用 **router / schema / service / repository / model** 分层组织代码。
    2. 设计 **JWT access token + refresh token + UserSession** 认证体系，支持用户注册登录、token 刷新、会话撤销、全部退出、用户禁用校验和
       access token blacklist；通过 **FastAPI Depends** 获取当前用户，并在收藏、目标岗位、技能画像、学习任务等模块中实现 *
       *用户数据隔离**。
    3. 设计 **岗位数据模型与技能标签模型**，支持岗位列表、详情、关键词搜索、城市/薪资/技能多条件筛选；通过 **岗位
       fingerprint + 数据库唯一约束** 实现岗位去重，使用 **Alembic** 管理数据库结构演进。
    4. 设计 **RawJobRecord 摄入模型与幂等导入流程**，通过 `message_id`、`raw_content_hash`、岗位 fingerprint
       和唯一约束处理重复投递、重复采集、重复入库和失败重试。
    5. 设计 **目标岗位与用户技能画像模块**，支持用户收藏岗位、设为目标岗位、维护个人技能水平；基于岗位技能与用户技能进行 *
       *matched / weak / missing** 技能差距分析，为学习任务生成提供依据。
    6. 设计 **学习任务与题目练习模块**，支持根据目标岗位 weak / missing
       技能生成学习任务，按技能推荐面试题，并记录作答、跳过、任务进度和用户技能评级更新，形成岗位准备闭环。
    7. 使用 **Celery + RabbitMQ** 处理岗位数据摄入、字段清洗、技能提取、去重入库等异步任务，避免耗时任务阻塞 HTTP
       请求；结合任务状态、错误记录、唯一约束和幂等设计处理重复执行、部分失败和失败重试等场景。
    8. 编写 **pytest 单元测试、接口契约测试与集成测试**，覆盖认证鉴权、权限隔离、岗位查询、收藏目标岗位、技能差距分析、学习任务生成、数据摄入去重等核心流程；使用
       **Docker Compose** 编排 PostgreSQL、Redis、RabbitMQ、API、Worker 等服务，保证项目可运行、可迁移、可测试。
* **技术亮点：** 使用 **UserSession、Redis、RabbitMQ、Celery、唯一约束、幂等任务、Cache Aside、用户数据隔离、异步数据摄入**
  保障系统在高频查询和批量数据处理场景下的稳定性与可扩展性。
