import logging
import sys

from app.config import get_settings

settings = get_settings()


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("finmatrix")


logger = setup_logging()
