import logging

from settings import get_settings


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root_logger.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    openai_log_level = logging.DEBUG if get_settings().openai_debug_logging else logging.INFO
    logging.getLogger("openai._base_client").setLevel(openai_log_level)
