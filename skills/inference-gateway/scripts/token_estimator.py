#!/usr/bin/env python3
"""Naive token estimator helper used during gateway tuning."""

from __future__ import annotations

import argparse
import math


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / chars_per_token))


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate token count from text length.")
    parser.add_argument("text", help="Prompt text to estimate.")
    parser.add_argument("--chars-per-token", type=float, default=4.0)
    args = parser.parse_args()
    print(estimate_tokens(args.text, chars_per_token=args.chars_per_token))


if __name__ == "__main__":
    main()
