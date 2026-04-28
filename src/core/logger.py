import sys

from loguru import logger

from src.core.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "{message}"
        ),
        colorize=True,
    )
    logger.add(
        "logs/app.log",
        level=settings.LOG_LEVEL,
        rotation="100 MB",
        retention="30 days",
        compression="gz",
        serialize=False,
    )


__all__ = ["logger", "setup_logging"]
