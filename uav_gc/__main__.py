import asyncio
import logging
import os

from .api import Api
from .link import MavLink
from .vehicle import Vehicle


async def main():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    link = MavLink.from_args()
    vehicle = Vehicle(link)
    api = Api(vehicle, link)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(link.supervise())
        tg.create_task(api.serve())


if __name__ == "__main__":
    asyncio.run(main())
