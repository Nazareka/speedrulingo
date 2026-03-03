import logging

from settings import get_settings


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    openai_log_level = logging.DEBUG if get_settings().openai_debug_logging else logging.INFO
    logging.getLogger("openai._base_client").setLevel(openai_log_level)
