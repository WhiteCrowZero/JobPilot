## 1. 契约与来源边界

- [x] 1.1 将 `RawJobCollectedMessage` 收敛为 V1 JSON 消息契约：版本、事件 Literal、UUID 标识、带时区时间、来源定位字段和递归 JSON payload 校验。
- [x] 1.2 定义后端维护的 `source_platform` 来源注册表，绑定来源名称、根地址与 adapter；未知平台在持久化前按永久错误处理。
- [x] 1.3 补充契约单元测试：有效消息、版本/事件/类型错误、无稳定来源定位、未知平台，以及 message/trace ID 语义。

## 2. RabbitMQ 与 Celery 基础设施

- [x] 2.1 更新配置、示例环境和 Compose，使 RabbitMQ 成为 Celery broker，Redis 保持缓存和 Celery result backend，并使用 `127.0.0.1` 本地示例。
- [x] 2.2 在 Celery app 显式声明 `default` 与 `job.ingestion` 队列，并将 `job.import_raw` 路由至 `job.ingestion`；为将来的 `job.skill_sync` / `job.ingestion.dlq` 保留命名说明但不注册消费任务。
- [x] 2.3 全仓检索 `MessageQueue` / `DomainEvent` 引用；确认无其他调用或完成必要迁移后，删除 Redis List 队列实现及其无效测试/配置。
- [x] 2.4 为 broker、任务路由和序列化配置补充单元测试，验证岗位任务不会落入默认队列。

## 3. 可恢复的岗位导入 Worker

- [x] 3.1 新增并注册 `job.import_raw` task：先校验消息和来源，再用独立会话提交 raw/job/detail 的事务一。
- [x] 3.2 调整摄入服务/仓储返回值和查询方法，使任一摄入结果均能提供持久化 `raw_record_id` 与关联 `job_post_id`，包括重复 message 和重复 raw 路径。
- [x] 3.3 新增从 `raw_record_id` 重新读取 raw payload、选择 adapter 并重建 `RawSkillCandidate` 的服务入口；事务二调用 `JobSkillSyncService` 并独立提交。
- [x] 3.4 设计并实现最小持久化状态/错误记录变更，能诊断事务二待恢复或最终失败；如涉及模型字段，创建 Alembic migration 并先迁移测试库。
- [x] 3.5 把数据库连接、超时和死锁等映射为有限次数、指数退避和 jitter 的 Celery 重试白名单；契约、永久业务、重复投递和未匹配技能不重试。
- [x] 3.6 为 task 编排补充单元/集成测试：首次成功、相同 message、不同 message 的相同 raw、fingerprint upsert、事务二失败后的重试重建、最终失败诊断和未匹配技能完成路径。

## 4. 独立 simulator 与联调资料

- [ ] 4.1 创建独立 simulator 入口和固定 JSON 样本，仅加载 producer 配置与契约，通过 `send_task("job.import_raw", ...)` 发送且不导入 Worker task 或创建数据库连接。
- [ ] 4.2 为 simulator 增加相同事件、不同 message 的相同内容、以及内容变化三种可重复样本，便于演示三层幂等行为。
- [ ] 4.3 更新 README/联调文档：基础设施启动、迁移、指定队列 Worker 启动、simulator 执行、RabbitMQ 管理界面与数据库结果核查、失败后重放边界。
- [ ] 4.4 编写端到端联调测试或受控手工验收脚本，验证 simulator → RabbitMQ → Worker → RawJobRecord / JobPost / JobPostSkill 的完整闭环。

## 5. 验证与交付

- [ ] 5.1 在可用基础设施下执行 Alembic upgrade、相关单元与集成测试；记录 RabbitMQ 或数据库不可用时的明确前置条件，不以跳过关键测试代替联调。
- [ ] 5.2 执行 `uv run ruff format`、`uv run ruff check . --fix`、`uv run pytest` 和 `uv run pyright`，修复本变更引入的问题。
- [ ] 5.3 复核日志不会输出完整 raw payload，且每条关键 Worker 日志能以 trace ID、message ID、raw record ID 和 Celery task ID 关联。
