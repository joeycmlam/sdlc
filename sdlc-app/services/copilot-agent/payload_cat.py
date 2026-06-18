"""payload-cat — read a staged agent payload from Redis to stdout.

Companion CLI for the StagePayloadTool. Used by agents in shell pipes:

    payload-cat brd-7b3e9c | python /jira-cli/jira_cli.py SCRUM-51 --update-description -

Reads the key `agent:payload:<name>` from REDIS_URL (default
redis://localhost:6379/0) and writes the raw bytes to stdout. Exits
non-zero if the key is missing.
"""

from __future__ import annotations

import os
import sys

import redis

_KEY_PREFIX = "agent:payload:"
_DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        sys.stderr.write("usage: payload-cat <name>\n")
        return 2 if argv and argv[0] not in ("-h", "--help") else 0

    name = argv[0]
    url = os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
    try:
        client = redis.from_url(url, decode_responses=False)
        value = client.get(f"{_KEY_PREFIX}{name}")
    except redis.RedisError as exc:
        sys.stderr.write(f"payload-cat: redis error: {exc}\n")
        return 3

    if value is None:
        sys.stderr.write(f"payload-cat: key not found: {name}\n")
        return 1

    sys.stdout.buffer.write(value)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
