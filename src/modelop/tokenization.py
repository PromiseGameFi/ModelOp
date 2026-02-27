from __future__ import annotations

import math


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / chars_per_token))

