# RabbitMQ 岗位摄入联调

## 链路边界

```text
独立 simulator
  -> send_task("job.import_raw")
  -> RabbitMQ / job.ingestion
  -> Celery Worker
  -> 事务一：RawJobRecord + JobPost + JobPostDetail
  -> 事务二：从 RawJobRecord.raw_payload 重建候选并同步 JobPostSkill
```

simulator 位于独立 `simulator/` 项目，只依赖 Celery，不导入 `job_pilot`、SQLAlchemy 或数据库配置。生产者与后端共享的稳定边界是 RabbitMQ 地址、task/queue 路由和 V1 JSON 消息契约。

## Windows 本地联调

启动基础设施并迁移开发数据库：

```powershell
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --wait
$env:APP_ENV = "local"
uv run alembic upgrade head
uv run python scripts/seed_skill_samples.py
```

启动仅监听岗位摄入队列的 Worker：

```powershell
$env:APP_ENV = "local"
uv run celery -A job_pilot.workers.celery_app:celery_app worker -P solo -Q job.ingestion -l info
```

在另一个 PowerShell 中发送固定场景：

```powershell
uv run --project simulator python simulator/producer.py new-job
uv run --project simulator python simulator/producer.py new-job
uv run --project simulator python simulator/producer.py duplicate-content
uv run --project simulator python simulator/producer.py changed-content
```

含义分别是：首次事件、相同 `message_id` 重投、不同消息但相同 raw 内容、同一来源岗位内容变化。RabbitMQ 管理端位于 `http://127.0.0.1:15675`。

核查数据库结果：

```powershell
$env:APP_ENV = "local"
uv run python scripts/verify_mq_ingestion.py
```

预期得到两个 raw 内容版本、一个规范化岗位、最新薪资 `30-40K`，以及 Python、FastAPI、PostgreSQL、RabbitMQ 四项技能。

## 失败与重放

- 契约错误和未知来源是永久错误，不进入自动重试。
- 连接中断、超时、死锁和序列化冲突进入有限指数退避重试。
- 事务二失败后，重试从 `raw_job_records.raw_payload` 重建技能输入；不依赖上一次 Worker 进程的内存变量。
- `job.ingestion.dlq` 和独立 `job.skill_sync` 仅保留为后续命名，本轮没有自定义 consumer、ack 或 DLQ 重放程序。
- 人工重放当前重新发送原始 V1 消息即可；受保护的管理 API/后台界面不在本轮范围。
