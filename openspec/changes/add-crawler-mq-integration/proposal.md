## Why

岗位摄入目前只能由脚本或服务内调用，尚未真正验证“采集进程与后端数据库解耦、通过 RabbitMQ 异步导入”的主链路。现有摄入服务已具备
raw 记录、规范化、三层去重和独立技能同步基础，但重复执行时不能仅依赖上一次任务的内存技能候选，无法可靠地恢复技能同步。

本次以独立模拟生产者代替真实爬虫，先把稳定消息契约、RabbitMQ/Celery 路由、可恢复的单任务摄入和本地联调证据建立起来，为之后接入任意真实爬虫保留清晰边界。

## What Changes

- 定义并版本化 `job.raw.collected` JSON 消息契约；生产者只传递来源标识和原始 JSON 数据，不连接业务数据库，也不决定后端来源名称或根地址。
- 新增独立 simulator 进程（单独脚本，和目前项目完全独立，简单模拟即可），使用 Celery `send_task("job.import_raw", message)`
  投递模拟岗位消息，以验证生产者无需导入 Worker task 函数即可发送消息。
- 配置 RabbitMQ 为 Celery broker，定义 `job.import_raw` task、`job.ingestion` 主队列和默认队列的显式路由；第一版不把技能同步拆成第二个
  Celery task，也不增加爬虫 HTTP 接口。
- 实现完整导入 task：事务一持久化 `RawJobRecord`、`JobPost` 与详情；事务二同步 `JobPostSkill`。重复消息或重复原始内容应安全短路，但仍能从持久化
  raw record 恢复技能同步输入。
- 按错误分类决定重试：契约、固定业务和重复消息不重试；数据库、连接和死锁等瞬时错误以指数退避和抖动重试；最终失败留下可查询、可重放的持久化记录。DLQ
  仅预留命名和后续演进边界，不在本轮自行实现 consumer/ack/retry 机制。
- 移除本链路不再使用的 Redis List 通用队列抽象和 `DomainEvent`，明确 Celery 是岗位摄入的唯一消息处理入口。
- 增加单元、集成和人工联调说明，覆盖消息校验、路由、重复投递、技能同步重试恢复和 simulator 到数据库的端到端路径。

## Capabilities

### New Capabilities

- `raw-job-message-contract`: 版本化、严格校验的岗位采集消息及来源注册边界。
- `celery-job-ingestion`: RabbitMQ/Celery 单任务岗位摄入、幂等处理、分类重试及基于 raw record 的技能同步恢复。
- `crawler-simulator-integration`: 独立模拟生产者的投递方式、运行配置和可复现联调流程。

### Modified Capabilities

- 无。当前仓库没有已发布的 OpenSpec capability spec；现有摄入行为将在上述新能力中首次成为明确契约。

## Impact

- 受影响模块：`core/config.py`、`core/message_queue.py`、`workers/celery_app.py`、新增 Worker task 与 simulator、
  `modules/ingestion`、`modules/job_skills`、部署配置和 README/联调文档。
- 基础设施：Celery broker 从 Redis 配置切换为 RabbitMQ；Redis 保留为缓存与 Celery result backend。
- 数据与行为：可能需要迁移或仓储方法以持久化/查询技能同步重建所需状态和最终失败信息；不新增供爬虫调用的 HTTP API。
- 兼容性：已存在的 Redis List `MessageQueue` / `DomainEvent` 若无其他调用方将移除，属于内部 API 清理；生产者必须遵守新的
  JSON 契约。
