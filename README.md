# JobPilot

FastAPI 后端 MVP：岗位、投递、面试复盘、学习任务与数据导入。
安装依赖：`uv sync`
启动服务：`docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d`
启动后端：`uv run uvicorn job_pilot.main:app --reload`
接口文档：<http://127.0.0.1:8000/docs>
