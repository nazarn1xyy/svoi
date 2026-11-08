"""python -m svoi_api.seed [--fixtures-only] [--no-demo-users]

Loads catalogs (and demo users in local/test) into DATABASE_URL, then refreshes fixtures in
local/test. Output is deterministic: running it twice changes nothing.
"""

import argparse
import asyncio
import os

from svoi_api.seed.fixtures import export
from svoi_api.seed.load import DEMO_ENVS, load


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="python -m svoi_api.seed")
    parser.add_argument("--fixtures-only", action="store_true", help="skip the database")
    parser.add_argument("--no-demo-users", action="store_true", help="catalogs only")
    args = parser.parse_args()
    env = os.environ.get("ENV", "local")
    if not args.fixtures_only:
        url = os.environ.get("DATABASE_URL")
        if not url:
            parser.error("DATABASE_URL is not set (or pass --fixtures-only)")
        asyncio.run(load(url, env=env, demo_users=False if args.no_demo_users else None))
    if args.fixtures_only or env in DEMO_ENVS:
        export()


main()
