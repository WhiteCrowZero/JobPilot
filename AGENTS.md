# JobPilot Agent 规则

## 1. 项目原则

JobPilot 是一个基于 FastAPI
构建的后端工程项目，围绕招聘岗位数据的采集/摄入、结构化存储、搜索筛选、技能标签提取、目标岗位管理、技能差距分析、学习任务生成和八股题掌握记录，重点展示后端数据建模、缓存、异步任务、权限隔离、测试与部署能力。

> 项目重点体现开发者的后端基本功和一定的深度，从MVP到产品级别演进。

---

## 2. 开发规范

1. 遵循 MVP 优先的迭代方式，除非用户明确要求（严格以`[system refactor]`开头），否则不要进行整体重写，直接明确拒绝。
2. 以后每做一个模块，都要同时产出 4 个东西：
    ```text
    1. 代码
    2. 测试
    3. README / 学习文档
    4. 涉及八股问题
    ```
3. 每个函数和类属性，都要写类型注释，一定是具体的类型，尽量不要是 `Any`
4. 每个.py文件的开头加上 `from __future__ import annotations`
5. service 的异常尽量抛到 `src/job_pilot/core/exceptions.py` 定义的异常中，不要到处乱写 HTTPException，往统一异常靠。

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
uv run ruff check .
uv run pytest
uv run pyright
```

要求：

1. AAA原则
2. 见名知意，比如：test_create_user_with_invalid_email()
3. 我提供的测试数据库：

---

## 5. 项目基本结构

我隐藏了一些不重要的文件，主要结构如下：

```text
JobPilot/
|-- README.md
|-- AGENTS.md
|-- pyproject.toml
|-- .env
|-- .env.example
|-- .env.test
|-- .gitignore
|-- .dockerignore
|-- alembic.ini
|-- alembic/
|   |-- env.py
|   `-- versions/
|-- deploy/
|   |-- .env
|   |-- Dockerfile
|   `-- docker-compose.yml
|-- docs/
|   |-- 思路草稿.md
|   `-- 项目规划.md
|-- logs/
|-- src/
|   `-- job_pilot/
|       |-- main.py
|       |-- api/
|       |   |-- deps.py
|       |   |-- health.py
|       |   `-- v1/
|       |       `-- router.py
|       |-- core/
|       |   |-- config.py
|       |   |-- enums.py
|       |   |-- cache.py
|       |   |-- exceptions.py
|       |   |-- message_queue.py
|       |   `-- resources.py
|       |-- db/
|       |   |-- base.py
|       |   |-- models.py
|       |   `-- session.py
|       |-- modules/
|       |   |-- __init__.py
|       |   |-- auth/
|       |   |-- users/
|       |   |-- job_posts/
|       |   |-- job_skills/
|       |   |-- job_collections/
|       |   |-- job_targets/
|       |   |-- user_skills/
|       |   |-- job_match/
|       |   |-- study_tasks/
|       |   |-- knowledge/
|       |   |-- questions/
|       |   |-- ingestion/
|       |   `-- system/
|       |-- utils/
|       `-- workers/
|           `-- celery_app.py
`-- tests/
    |-- conftest.py
    |-- api/
    |-- unit/
    `-- smoke/
```

## 6. 项目最终简历形态

> 一切都是奔着这个目标，实现功能的同时，学会相关知识点，能够讲好整个项目。

* **项目描述：** 基于 **FastAPI 模块化后端架构**
  开发的招聘岗位情报与求职准备平台，围绕岗位数据摄入、清洗去重、技能标签提取、岗位搜索筛选、目标岗位管理、技能差距分析、学习任务生成、八股题掌握记录等场景，形成
  **“岗位情报 → 技能分析 → 学习准备”** 的后端业务闭环。系统重点体现 **认证鉴权、数据建模、复杂查询、缓存优化、异步任务、幂等处理、测试与容器化部署
  ** 等后端工程能力。
* **技术栈：** **FastAPI、Pydantic v2、SQLAlchemy 2.0、Alembic、PostgreSQL、Redis、Celery、JWT、Docker Compose、pytest、uv**
* **个人职责：**
    1. 基于 **FastAPI + SQLAlchemy 2.0** 完成后端模块化设计，将系统拆分为 **用户认证、岗位数据、数据摄入、用户工作台、学习准备、缓存与异步任务
       ** 等领域模块，采用 **router / schema / service / repository / model** 分层组织代码。
    2. 设计 **JWT access token + refresh token** 认证体系，支持用户注册登录、token 刷新、会话撤销、用户禁用校验；通过 *
       *FastAPI Depends** 获取当前用户，并在收藏、目标岗位、技能画像、学习任务等模块中实现 **用户数据隔离**。
    3. 设计 **岗位数据模型与技能标签模型**，支持岗位列表、详情、关键词搜索、城市/薪资/技能多条件筛选；通过 **岗位
       fingerprint + 数据库唯一约束** 实现岗位去重，使用 **Alembic** 管理数据库结构演进。
    4. 设计 **目标岗位与用户技能画像模块**，支持用户收藏岗位、设为目标岗位、维护个人技能水平；基于岗位技能与用户技能进行 *
       *matched / missing / weak 技能差距分析**，为学习任务生成提供依据。
    5. 设计 **学习任务与八股题掌握模块**，支持根据目标岗位缺失技能生成学习任务，按技能推荐面试题，并记录用户对题目的 *
       *todo / reviewing / mastered** 掌握状态，形成岗位准备闭环。
    6. 引入 **Redis Cache Aside 缓存模式**，缓存岗位详情、热门技能统计、任务进度等高频数据；在写操作后删除相关缓存，降低数据库重复查询压力，并保证
       **数据库作为最终事实来源**。
    7. 使用 **Celery + Redis** 处理岗位数据摄入、字段清洗、技能提取、去重入库等异步任务，避免耗时任务阻塞 HTTP 请求；结合 *
       *任务状态表、错误记录、唯一约束和幂等设计** 处理重复执行、部分失败和失败重试等场景。
    8. 编写 **pytest 单元测试与接口测试**，覆盖认证鉴权、权限隔离、岗位查询、收藏目标岗位、技能差距分析、学习任务生成、数据摄入去重等核心流程；使用
       **Docker Compose** 编排 PostgreSQL、Redis、API、Worker 等服务，保证项目可运行、可迁移、可测试。
* **技术亮点：** 使用 **Redis、Celery、唯一约束、幂等任务、Cache Aside、用户数据隔离、异步数据摄入**
  保障系统在高频查询和批量数据处理场景下的稳定性与可扩展性。
