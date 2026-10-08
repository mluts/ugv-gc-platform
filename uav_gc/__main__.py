import argparse
import logging
import sys

import uvicorn
from argon2 import PasswordHasher

from .api import create_app
from .auth import Auth, TokenCodec, hash_password
from .config import ConfigError, load_config
from .link import MavLink
from .users import UserStore
from .vehicle import Vehicle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.toml")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        sys.exit(str(exc))

    logging.basicConfig(
        level=config.log.level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    hasher = PasswordHasher()
    users = UserStore(config.users.database)

    admin_username = config.users.admin_username
    admin_password = config.users.admin_password
    if users.count() == 0:
        if admin_username is None or admin_password is None:
            users.close()
            sys.exit(
                "empty user store: set users.admin_username and users.admin_password "
                f"in {args.config}"
            )
        users.bootstrap(admin_username, hash_password(hasher, admin_password))

    codec = TokenCodec(config.auth.secret, config.auth.token_ttl_min * 60)
    auth = Auth(users, codec, hasher)

    link = MavLink(config.link.device, config.link.baud)
    vehicle = Vehicle(link)
    app = create_app(vehicle, link.supervise, users=users, auth=auth)

    uvicorn.run(app, host=config.http.host, port=config.http.port)


if __name__ == "__main__":
    main()
