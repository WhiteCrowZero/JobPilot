# system

系统工程模块：放置健康检查扩展、缓存策略、后台任务、日志、可观测性等跨业务能力。

## 当前状态

系统工程能力暂时主要落在 `api/`、`core/`、`db/`、`workers/` 中，`system` 目录只保留模块边界，不承载核心业务表。

已完成：

- `main.py` 使用 FastAPI lifespan 统一管理应用资源。
- `core.resources.AppResources` 统一持有数据库、缓存、分布式锁和搜索资源。
- `db.session.DatabaseResource` 负责创建 SQLAlchemy async engine 和 session maker。
- `api.deps.get_session()` 从 `app.state.resources` 获取数据库 session，避免模块级全局 engine。
- `core.redis` 独立全局 Redis client 已移除，避免重复连接和重复关闭。
- `AppResources.health_check()` 统一检查 database、Redis 和搜索资源，可用于 readiness check。
- 岗位消息由独立 Celery Worker 直接通过 RabbitMQ 消费，不再挂载到 FastAPI 的通用资源容器。
- `/api/v1/health` 用于轻量存活检查，`/api/v1/health/readiness` 用于资源就绪检查。

## 八股问题

- FastAPI lifespan 适合管理哪些资源？
- 为什么 Redis client、DB engine 这类连接资源要有明确的所有权？
- 依赖注入为什么应该从应用资源 AppResources 中获取 session？
- 全局单例资源和应用生命周期资源有什么区别？
- liveness check 和 readiness check 有什么区别？
