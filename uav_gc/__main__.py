import logging
import os

import uvicorn

from .api import create_app
from .link import MavLink
from .vehicle import Vehicle


def main():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    host = os.environ.get("HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("HTTP_PORT", "8080"))

    link = MavLink.from_args()
    vehicle = Vehicle(link)
    app = create_app(vehicle, link.supervise)

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
