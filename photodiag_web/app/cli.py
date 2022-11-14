import argparse
import logging
import os

from bokeh.application.application import Application
from bokeh.application.handlers import ScriptHandler
from bokeh.server.server import Server

from photodiag_web.app.handler import PhotodiagWebHandler

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """The photodiag-web command line interface.
    This is a wrapper around a bokeh server that provides an interface to launch the application,
    bundled with the pyzebra package.
    """
    app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")

    parser = argparse.ArgumentParser(
        prog="photodiag-web", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--port", type=int, default=5006, help="port to listen on for HTTP requests"
    )

    parser.add_argument(
        "--allow-websocket-origin",
        metavar="HOST[:PORT]",
        type=str,
        action="append",
        default=None,
        help="hostname that can connect to the server websocket",
    )

    parser.add_argument(
        "--args",
        nargs=argparse.REMAINDER,
        default=[],
        help="command line arguments for the pyzebra application",
    )

    args = parser.parse_args()

    logger.info(app_path)

    photodiag_web_handler = PhotodiagWebHandler()
    handler = ScriptHandler(filename=app_path, argv=args.args)
    server = Server(
        {"/": Application(photodiag_web_handler, handler)},
        port=args.port,
        allow_websocket_origin=args.allow_websocket_origin,
    )

    server.start()
    server.io_loop.start()


if __name__ == "__main__":
    main()
