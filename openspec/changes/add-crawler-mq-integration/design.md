## Context

当前 `RawJobIngestionService` 已实现消息 ID、来源加 raw 内容 hash、岗位 fingerprint 三层语义，并能在一次数据库会话中写入 raw/岗位/详情。`JobSkillSyncService` 已被设计为独立事务，但尚无 Worker 编排；其输入来自本次服务调用返回的内存 `raw_skill_candidates`。当事务一成功、事务二因瞬时异常失败并触发 Celery 重试时，重复 `message_id` 会跳过事务一且返回空候选，导致事务二不能可靠恢复。

当前 Celery 使用 Redis broker，`core/message_queue.py` 还保留 Redis List `DomainEvent` 通用队列。README 声明 RabbitMQ、Worker 和模拟爬虫联调是下一阶段，但仓库尚未落地任务路由和外部生产者。采集进程必须只依赖 RabbitMQ 地址、任务名和 JSON 契约，不能访问业务数据库或调用 HTTP 摄入接口。

## Goals / Non-Goals

**Goals:**

- 建立可由独立进程投递的、版本化且 JSON 安全的岗位消息契约。
- 使用 RabbitMQ broker 和一个 `job.import_raw` Celery task 完成岗位 raw 摄入及技能同步。
- 将任务切为两个连续数据库事务；第二事务仅以 `raw_record_id` / `job_post_id` 及数据库中的 raw 内容重建输入。
- 为可恢复基础设施异常配置 Celery 的有限指数退避重试；让持久化记录和幂等服务处理 at-least-once 投递。
- 用 simulator、测试和运行文档提供可复现的本地联调路径。

**Non-Goals:**

- 不实现真实 Scrapy 爬虫、通用爬虫框架或新的 HTTP 摄入 API。
- 不把技能同步拆为第二个 Celery task，不引入跨 task 分布式事务或 outbox。
- 不自行实现 RabbitMQ acknowledgement、consumer 循环、重试计数或 DLQ consumer；本轮依赖 Celery 的消费与重试封装。
- 不建设管理后台、告警/指标系统或完整的人工重放 UI；只留下持久化失败状态和可扩展命名边界。

## Decisions

### 1. 消息契约由后端仓库独立维护

`RawJobCollectedMessage` 升级为版本化的 Pydantic 契约，并作为 simulator 与未来爬虫的唯一共享输入说明。V1 必须包含：`schema_version=1`、`event_type=Literal["job.raw.collected"]`、UUID 形式的 `message_id` 与 `trace_id`、`producer`、带时区的 `produced_at` / `fetched_at`、`source_platform`、`raw_payload`，以及用于来源定位的 `external_job_id` 或 `source_url`。`raw_payload` 递归限制为 JSON 值，不允许 Python 特有对象或任意 `Any`。

后端维护 `source_platform` 到名称、根地址和 adapter 的来源注册表；消息中的平台键是稳定标识，而名称和 `base_url` 不由生产者信任或写入。未知平台在持久化前判为永久业务错误。

`message_id` 表示一次业务事件；Celery 重投保持不变。生产者发现同一来源岗位内容变化时生成新的 `message_id`；同一次采集链路的 `trace_id` 跨重试不变。生产者可依次用详情 URL、外部岗位 ID、规范化内容 hash 判断是否需要发出新事件；后端仍以 message ID、`source_id + raw_content_hash`、fingerprint 为最终防线。

备选方案是让爬虫发送来源名称、地址和任意字典，或由后端推断 payload 字段。它会把来源配置和解析歧义泄漏给生产者，且违背现有“仅映射显式 source 字段”的边界，因此不采用。

### 2. 一个命名 task，显式队列路由

Celery broker 改为 RabbitMQ，Redis 继续作为 result backend 与缓存。Celery 显式声明 `job.ingestion` 和 `default` 队列，并将 task 名 `job.import_raw` 路由到 `job.ingestion`；`job.skill_sync`、`job.ingestion.dlq` 仅保留为未来命名约定，不创建第二任务或自定义 consumer。

独立 simulator 仅创建配置相同的 Celery producer，并调用 `send_task("job.import_raw", args=[message_json])`。任务名是生产端与 Worker 的稳定集成点，避免 producer 导入 Worker 函数、FastAPI app 或数据库会话。

不继续使用 `RedisListMessageQueue` / `DomainEvent` 作为这条链路的中间抽象。Celery 已承担发布、消费、序列化和确认语义；两层队列会造成两套重试和难以验证的交付语义。删除前先确认没有其他调用方。

### 3. 两个数据库事务，第二事务从 raw record 重建

`job.import_raw` 的执行顺序固定如下：

```text
validate message and source registry
  -> transaction 1: RawJobRecord + JobPost + JobPostDetail, commit
  -> transaction 2: reload RawJobRecord.raw_payload by raw_record_id
       -> source adapter -> JobDraft.raw_skills -> RawSkillCandidate
       -> JobSkillSyncService, commit
```

事务一的结果必须始终包含可供后续处理的 `raw_record_id` 以及可查得的 `job_post_id`，而不是只传递内存技能候选。若同一 `message_id` 再次执行，事务一按幂等语义短路；Worker 仍以已持久化 raw record 尝试或确认事务二，以便 Celery 对“事务一已提交、事务二失败”的重试可恢复。`JobSkillSyncService` 的 hash 比较使已经成功的重复同步无副作用。

不在第一版把事务二投递到 `job.skill_sync`。单 task 仍会产生“事务一成功、事务二失败”的可见短暂不一致，但持久化重建与 idempotent sync 解决恢复问题，避免此时引入跨消息的投递原子性。

### 4. 显式错误边界与 Celery 重试策略

任务入口先做 schema 和版本校验。消息契约错误、来源/adapter 的确定性错误及未匹配技能均不重试：前两类保存或关联可诊断失败状态，未匹配技能则作为成功的同步结果记录。相同 `message_id` 和相同来源 raw hash 不是异常，按幂等成功路径处理。

仅数据库连接中断、超时、临时死锁等明确的基础设施异常允许 Celery `retry`，使用有限最大次数、指数退避和 jitter。超过次数后保留 raw record 的失败诊断，日志带 `trace_id`、`message_id`、`raw_record_id` 和 task id，不记录完整 `raw_payload`。具体可重试异常白名单在实现时落到核心异常类型/数据库异常映射中，不能对所有 `Exception` 无条件重试。

### 5. 持久化、部署与验证顺序

如现有 `RawJobRecord` 状态不足以区分“规范化已完成、技能同步待恢复/最终失败”，通过最小迁移补充可查询状态或错误信息，而不是仅依赖 Celery result backend。部署前先配置 RabbitMQ 持久 broker、可重启 worker 和数据库迁移；消息的最终处理正确性依赖数据库唯一约束，不能假设 exactly-once。

测试分层覆盖契约、task 路由和编排单元测试，以及含 PostgreSQL/RabbitMQ（或明确隔离替身）的联调测试。手动联调用 simulator 投递固定样本，检查 Worker 日志、RabbitMQ 队列和 raw/job/skill 结果；不把 API 进程当成必要中间层。

## Risks / Trade-offs

- [事务一和事务二不原子] → 事务二从 raw record 重建，任务重试和幂等 hash 使其可恢复；后续需要独立扩展时再评估拆 task/outbox。
- [Celery late acknowledgement 导致重复执行] → message ID、来源加内容 hash、fingerprint 和技能 hash 都必须保留数据库约束与幂等逻辑。
- [错误地把永久错误配置为重试] → 使用异常白名单和相应测试；契约/adapter 错误直接进入失败记录，不消耗队列重试。
- [模拟 producer 与未来爬虫偏离] → simulator 只封装公共 JSON 契约和 `send_task`，样本数据与契约测试共用。
- [RabbitMQ/数据库在本地不可用] → 联调文档明确服务启动、迁移和健康检查前置条件；纯单元测试不要求常驻基础设施。
- [删除 Redis List 抽象影响非摄入调用方] → 实施前全仓检索引用，只有在无调用或完成受控迁移后删除。

## Migration Plan

1. 增加/更新配置和部署环境，使 RabbitMQ 成为 broker，Redis 仍为 result backend；启动基础设施并迁移数据库。
2. 发布 Worker 的队列声明与 `job.import_raw` task，但先不切换任何真实采集生产者。
3. 运行 simulator 的固定样本，验证新入库、重复 message、重复 raw、内容变化和事务二故障恢复。
4. 通过质量检查和联调清单后，将未来真实爬虫按同一契约接入；无需授予其数据库凭据。
5. 回滚时停止 worker/simulator 并恢复原 broker 配置；已持久化 raw 记录保留，待修复后可重放，禁止删除作为回滚手段。

## Open Questions

- 最终失败后的“可重放”入口本轮只提供脚本/管理命令还是同时暴露受保护的管理 API，待后续后台范围确认。
- 为记录事务二最终失败，选择扩展 `RawJobRecord` 还是使用已有/新增 `ingestion_errors` 的关联模型，实施前需以现有迁移和模型为准。
- `external_job_id` 与 `source_url` 的最小约束拟定为至少一个存在；若真实来源不能提供两者之一，需要在接入该来源前补充稳定来源标识策略。
