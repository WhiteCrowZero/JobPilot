from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from traceback import TracebackException
from typing import Any

from job_pilot.core.config import Settings

# 标记由本项目日志配置创建的 handler。
# 重复配置时只清理这些 handler，避免误删测试或外部工具临时挂载的 handler。
_MANAGED_HANDLER_ATTR = "_jobpilot_managed_handler"
APP_LOG_LEVEL = 25
logging.addLevelName(APP_LOG_LEVEL, "APP")

# logging.LogRecord 自带字段不应该重复放入 extra。
_RESERVED_LOG_RECORD_FIELDS = set(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__
) | {"message", "asctime"}

_LEVEL_COLORS = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    APP_LOG_LEVEL: "\033[34m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[35m",
}
_RESET_COLOR = "\033[0m"

# FastAPI 本身没有独立 logger，实际主要来自 uvicorn/starlette。
# MVP 阶段默认关闭这些框架日志，避免和业务日志同时刷控制台。
_FRAMEWORK_LOGGER_NAMES = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
    "starlette",
)


class JsonLogFormatter(logging.Formatter):
    """文件端完整 JSON Lines 日志格式。"""

    def __init__(
        self,
        *,
        service_name: str,
        app_env: str,
    ) -> None:
        super().__init__()
        self.service_name = service_name
        self.app_env = app_env

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "environment": self.app_env,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
            "process": record.process,
            "thread": record.threadName,
        }

        extra_fields = self._extract_extra_fields(record)
        if extra_fields:
            payload["extra"] = extra_fields

        if record.exc_info is not None:
            payload["exception"] = self._format_exception(record)

        return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))

    @staticmethod
    def _extract_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
        extra_fields: dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            extra_fields[key] = _to_json_safe(value)
        return extra_fields

    @staticmethod
    def _format_exception(record: logging.LogRecord) -> dict[str, Any]:
        if record.exc_info is None:
            return {}
        exc_type, exc_value, exc_traceback = record.exc_info
        if exc_type is None or exc_value is None:
            return {}
        exception = TracebackException(exc_type, exc_value, exc_traceback)
        return {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": list(exception.format()),
        }


class ConsoleLogFormatter(logging.Formatter):
    """控制台简洁日志格式，只保留人工排查最常用信息。"""

    def __init__(
        self,
        *,
        service_name: str,
        colorize: bool,
    ) -> None:
        super().__init__()
        self.service_name = service_name
        self.colorize = colorize

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        logger_name = _short_logger_name(record.name)
        line = (
            f"{timestamp} | {record.levelname:<8} | {self.service_name} | "
            f"{logger_name} | {record.getMessage()}"
        )

        if record.exc_info is not None:
            line = f"{line}\n{self.formatException(record.exc_info)}"

        if not self.colorize:
            return line
        color = _LEVEL_COLORS.get(record.levelno)
        if color is None:
            return line
        return f"{color}{line}{_RESET_COLOR}"


class LevelRangeFilter(logging.Filter):
    """只允许指定等级范围内的日志进入某个 handler。"""

    def __init__(
        self,
        *,
        min_level: int,
        max_level: int | None = None,
        excluded_levels: set[int] | None = None,
    ) -> None:
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level
        self.excluded_levels = excluded_levels or set()

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno in self.excluded_levels:
            return False
        if record.levelno < self.min_level:
            return False
        if self.max_level is not None and record.levelno > self.max_level:
            return False
        return True


class ExactLevelFilter(logging.Filter):
    """只允许指定等级的日志进入某个 handler。"""

    def __init__(self, level: int) -> None:
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self.level


def log_app_event(
    logger: logging.Logger,
    message: str,
    *args: object,
    extra: Mapping[str, object] | None = None,
) -> None:
    """记录业务事件，避免和系统 INFO 日志混在一起。"""

    logger.log(APP_LOG_LEVEL, message, *args, extra=dict(extra or {}), stacklevel=2)


def configure_logging(
    settings: Settings,
    *,
    service_name: str = "app",
    configure_root: bool = False,
) -> None:
    """配置 JobPilot 日志。

    `APP` 记录业务事件，`INFO` 记录系统生命周期和基础运行信息，`ERROR`
    记录错误。Web 进程默认只配置 `job_pilot` logger，并关闭 uvicorn/starlette
    等框架日志；脚本或 worker 可以设置 configure_root=True，用同一套 handler
    接管当前进程日志。
    """

    base_log_level = _parse_log_level(settings.LOG_LEVEL)
    console_log_level = _parse_optional_log_level(
        settings.LOG_CONSOLE_LEVEL,
        fallback=base_log_level,
    )
    file_log_level = _parse_optional_log_level(
        settings.LOG_FILE_LEVEL,
        fallback=base_log_level,
    )
    logger_level = min(console_log_level, file_log_level)
    service = _normalize_service_name(service_name)
    target_logger = logging.getLogger() if configure_root else logging.getLogger("job_pilot")

    _remove_managed_handlers(target_logger)
    target_logger.setLevel(logger_level)
    target_logger.propagate = False

    if settings.LOG_SUPPRESS_FRAMEWORK_LOGS:
        _suppress_framework_loggers()

    file_formatter = JsonLogFormatter(
        service_name=service,
        app_env=settings.APP_ENV,
    )
    console_formatter = ConsoleLogFormatter(
        service_name=service,
        colorize=settings.LOG_CONSOLE_COLOR,
    )

    if settings.LOG_CONSOLE_ENABLED:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_log_level)
        console_handler.setFormatter(console_formatter)
        _mark_managed(console_handler)
        target_logger.addHandler(console_handler)

    if settings.LOG_FILE_ENABLED:
        log_dir = Path(settings.LOG_DIR) / service
        log_dir.mkdir(parents=True, exist_ok=True)

        app_handler = _build_file_handler(
            log_dir / "app.jsonl",
            level=max(APP_LOG_LEVEL, file_log_level),
            formatter=file_formatter,
            settings=settings,
        )
        app_handler.addFilter(ExactLevelFilter(APP_LOG_LEVEL))
        target_logger.addHandler(app_handler)

        info_handler = _build_file_handler(
            log_dir / "info.jsonl",
            level=max(logging.INFO, file_log_level),
            formatter=file_formatter,
            settings=settings,
        )
        info_handler.addFilter(
            LevelRangeFilter(
                min_level=logging.INFO,
                max_level=logging.WARNING,
                excluded_levels={APP_LOG_LEVEL},
            )
        )
        target_logger.addHandler(info_handler)

        error_handler = _build_file_handler(
            log_dir / "error.jsonl",
            level=max(logging.ERROR, file_log_level),
            formatter=file_formatter,
            settings=settings,
        )
        error_handler.addFilter(LevelRangeFilter(min_level=logging.ERROR))
        target_logger.addHandler(error_handler)


def _build_file_handler(
    file_path: Path,
    *,
    level: int,
    formatter: logging.Formatter,
    settings: Settings,
) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        file_path,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    _mark_managed(handler)
    return handler


def _suppress_framework_loggers() -> None:
    for logger_name in _FRAMEWORK_LOGGER_NAMES:
        framework_logger = logging.getLogger(logger_name)
        framework_logger.handlers.clear()
        framework_logger.propagate = False
        framework_logger.disabled = True


def _mark_managed(handler: logging.Handler) -> None:
    setattr(handler, _MANAGED_HANDLER_ATTR, True)


def _remove_managed_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, _MANAGED_HANDLER_ATTR, False):
            logger.removeHandler(handler)
            handler.close()


def _parse_log_level(level_name: str) -> int:
    normalized = level_name.strip().upper()
    level = logging.getLevelName(normalized)
    if isinstance(level, int):
        return level
    raise ValueError(f"Invalid log level: {level_name!r}")


def _parse_optional_log_level(level_name: str | None, *, fallback: int) -> int:
    if level_name is None:
        return fallback
    if not level_name.strip():
        return fallback
    return _parse_log_level(level_name)


def _normalize_service_name(service_name: str) -> str:
    service = service_name.strip().lower().replace(" ", "_")
    if not service:
        raise ValueError("service_name must not be empty")
    return service


def _short_logger_name(logger_name: str) -> str:
    if logger_name.startswith("job_pilot."):
        return logger_name.removeprefix("job_pilot.")
    return logger_name


def _to_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _to_json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
