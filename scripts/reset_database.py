from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ResetEnv = Literal["local", "test"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE_DATABASE = "postgres"
PROTECTED_DATABASES = {"postgres", "template0", "template1"}


@dataclass(slots=True, frozen=True)
class ResetTarget:
    """一次数据库重建的目标信息。"""

    app_env: ResetEnv
    database_url: str
    database_name: str
    maintenance_url: str


async def main() -> None:
    """重建开发或测试数据库，并迁移到最新结构。"""

    args = _parse_args()
    _set_app_env(args.app_env)
    target = _build_reset_target(args.app_env)
    _validate_target(target)

    if not args.yes:
        _print_plan(target)
        raise SystemExit("Refuse to reset database without --yes.")

    _print_plan(target)
    await _recreate_database(target)

    if not args.skip_migrations:
        _run_alembic_upgrade(target.app_env)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drop, recreate, and migrate the JobPilot local/test database.",
    )
    parser.add_argument(
        "--env",
        dest="app_env",
        choices=["local", "test"],
        required=True,
        help="Target environment. prod is intentionally unsupported.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually execute the destructive reset.",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Only recreate the database, do not run alembic upgrade head.",
    )
    return parser.parse_args()


def _set_app_env(app_env: ResetEnv) -> None:
    os.environ["APP_ENV"] = app_env


def _build_reset_target(app_env: ResetEnv) -> ResetTarget:
    # 延迟导入，确保 APP_ENV 已经写入环境变量。
    from job_pilot.core.config import Settings

    settings = Settings()
    database_url = settings.effective_database_url
    parsed_url = make_url(database_url)
    if parsed_url.database is None:
        raise ValueError("Database URL must include a database name.")

    maintenance_url = _to_maintenance_url(parsed_url).render_as_string(hide_password=False)
    return ResetTarget(
        app_env=app_env,
        database_url=database_url,
        database_name=parsed_url.database,
        maintenance_url=maintenance_url,
    )


def _to_maintenance_url(database_url: URL) -> URL:
    return database_url.set(database=MAINTENANCE_DATABASE)


def _validate_target(target: ResetTarget) -> None:
    if target.database_name in PROTECTED_DATABASES:
        raise ValueError(f"Refuse to reset protected database: {target.database_name}")
    if target.app_env == "test" and "test" not in target.database_name.lower():
        raise ValueError(
            "Refuse to reset test environment because database name does not contain 'test'."
        )


def _print_plan(target: ResetTarget) -> None:
    print(
        "Reset database target: "
        f"env={target.app_env}, database={target.database_name}, url={target.database_url}"
    )


async def _recreate_database(target: ResetTarget) -> None:
    engine = create_async_engine(
        target.maintenance_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    try:
        quoted_database = _quote_identifier(engine, target.database_name)
        async with engine.connect() as connection:
            await connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": target.database_name},
            )
            await connection.execute(text(f"DROP DATABASE IF EXISTS {quoted_database}"))
            await connection.execute(text(f"CREATE DATABASE {quoted_database}"))
    finally:
        await engine.dispose()


def _quote_identifier(engine: AsyncEngine, identifier: str) -> str:
    return engine.sync_engine.dialect.identifier_preparer.quote(identifier)


def _run_alembic_upgrade(app_env: ResetEnv) -> None:
    env = os.environ.copy()
    env["APP_ENV"] = app_env
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)

"""
uv run python scripts/reset_database.py --env test --yes --skip-migrations

"""
