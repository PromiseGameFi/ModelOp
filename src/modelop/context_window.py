from __future__ import annotations

from dataclasses import dataclass

from modelop.tokenization import estimate_tokens


@dataclass(frozen=True)
class ContextOptimizationResult:
    prompt: str
    original_prompt_tokens: int
    effective_prompt_tokens: int
    prompt_truncated: bool


class ContextWindowOptimizer:
    def __init__(
        self,
        chars_per_token: float = 4.0,
        head_ratio: float = 0.35,
        truncation_marker: str = "\n[...context truncated...]\n",
    ) -> None:
        self._chars_per_token = chars_per_token
        self._head_ratio = min(0.90, max(0.10, head_ratio))
        self._marker = truncation_marker

    def optimize(self, prompt: str, max_prompt_tokens: int) -> ContextOptimizationResult:
        original_prompt_tokens = estimate_tokens(prompt, chars_per_token=self._chars_per_token)
        if max_prompt_tokens <= 0:
            return ContextOptimizationResult(
                prompt="",
                original_prompt_tokens=original_prompt_tokens,
                effective_prompt_tokens=0,
                prompt_truncated=True,
            )

        if original_prompt_tokens <= max_prompt_tokens:
            return ContextOptimizationResult(
                prompt=prompt,
                original_prompt_tokens=original_prompt_tokens,
                effective_prompt_tokens=original_prompt_tokens,
                prompt_truncated=False,
            )

        max_chars = max(1, int(max_prompt_tokens * self._chars_per_token))
        marker_len = len(self._marker)
        if max_chars <= marker_len + 4:
            trimmed = prompt[:max_chars]
        else:
            head_chars = int(max_chars * self._head_ratio)
            tail_chars = max_chars - head_chars - marker_len
            if tail_chars < 1:
                tail_chars = 1
                head_chars = max(1, max_chars - marker_len - tail_chars)
            trimmed = f"{prompt[:head_chars]}{self._marker}{prompt[-tail_chars:]}"

        effective_prompt_tokens = estimate_tokens(trimmed, chars_per_token=self._chars_per_token)
        return ContextOptimizationResult(
            prompt=trimmed,
            original_prompt_tokens=original_prompt_tokens,
            effective_prompt_tokens=effective_prompt_tokens,
            prompt_truncated=True,
        )
