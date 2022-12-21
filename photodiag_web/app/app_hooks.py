import logging
from io import StringIO


def on_server_loaded(_server_context):
    handler = logging.StreamHandler(StringIO())
    handler.setFormatter(
        logging.Formatter(fmt="%(asctime)s %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger = logging.getLogger("photodiag_web")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
