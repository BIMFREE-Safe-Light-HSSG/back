import logging.config
import os
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_LEVEL = "INFO"


def _log_root() -> Path:
    raw_log_root = os.getenv("LOG_ROOT")
    if raw_log_root and raw_log_root.strip():
        path = Path(raw_log_root.strip())
        return path if path.is_absolute() else PROJECT_ROOT / path

    return PROJECT_ROOT / "logs"


def _log_level() -> str:
    return os.getenv("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper() or DEFAULT_LOG_LEVEL


def _dated_log_file(directory: Path, prefix: str) -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return directory / f"{prefix}-{today}.log"


def ensure_log_directories() -> dict[str, Path]:
    root = _log_root()
    directories = {
        "runtime": root / "backend" / "runtime",
        "app": root / "backend" / "app",
        "error": root / "backend" / "error",
        "migrations": root / "migrations",
        "infrastructure": root / "infrastructure",
    }

    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    return directories


def configure_logging() -> None:
    directories = ensure_log_directories()
    log_level = _log_level()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": log_level,
                    "formatter": "standard",
                },
                "app_file": {
                    "class": "logging.FileHandler",
                    "level": log_level,
                    "formatter": "standard",
                    "filename": str(_dated_log_file(directories["app"], "app")),
                    "encoding": "utf-8",
                },
                "error_file": {
                    "class": "logging.FileHandler",
                    "level": "WARNING",
                    "formatter": "standard",
                    "filename": str(_dated_log_file(directories["error"], "error")),
                    "encoding": "utf-8",
                },
            },
            "root": {
                "level": log_level,
                "handlers": ["console", "app_file", "error_file"],
            },
            "loggers": {
                "app": {
                    "level": log_level,
                    "propagate": True,
                },
            },
        }
    )
