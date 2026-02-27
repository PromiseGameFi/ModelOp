#!/usr/bin/env python3
"""Simple scenario descriptor printer for chaos matrix runs."""

from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="Print normalized chaos run config.")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--duration-seconds", type=int, default=120)
    parser.add_argument("--virtual-users", type=int, default=100)
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "scenario": args.scenario,
                "duration_seconds": args.duration_seconds,
                "virtual_users": args.virtual_users,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
