#!/usr/bin/env python3
"""Quick continuous batching simulator for policy tuning."""

from __future__ import annotations

import argparse
from collections import deque


def run(max_slots: int, jobs: list[int]) -> int:
    queue = deque(jobs)
    active: list[int] = []
    ticks = 0

    while queue or active:
        while len(active) < max_slots and queue:
            active.append(queue.popleft())
        ticks += 1
        active = [remaining - 1 for remaining in active if remaining - 1 > 0]
    return ticks


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate decode ticks for queued jobs.")
    parser.add_argument("--max-slots", type=int, default=4)
    parser.add_argument("--jobs", type=int, nargs="+", default=[20, 10, 5, 8, 3])
    args = parser.parse_args()
    print(run(args.max_slots, args.jobs))


if __name__ == "__main__":
    main()
