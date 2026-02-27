from __future__ import annotations


class KVCapacityEstimator:
    def __init__(self, bytes_per_token: int) -> None:
        self._bytes_per_token = bytes_per_token

    def estimate_request_bytes(self, estimated_total_tokens: int) -> int:
        return max(0, estimated_total_tokens * self._bytes_per_token)


class KVPressureTracker:
    def __init__(self, kv_budget_bytes: int) -> None:
        if kv_budget_bytes <= 0:
            raise ValueError("kv_budget_bytes must be positive")
        self._kv_budget_bytes = kv_budget_bytes
        self._active_bytes = 0
        self._allocations: dict[str, int] = {}

    @property
    def active_bytes(self) -> int:
        return self._active_bytes

    @property
    def utilization_ratio(self) -> float:
        return min(1.0, self._active_bytes / self._kv_budget_bytes)

    def try_reserve(self, request_id: str, bytes_needed: int, shed_threshold: float) -> bool:
        projected = self._active_bytes + max(0, bytes_needed)
        projected_ratio = projected / self._kv_budget_bytes
        if projected_ratio >= shed_threshold:
            return False
        self._allocations[request_id] = max(0, bytes_needed)
        self._active_bytes = projected
        return True

    def release(self, request_id: str) -> None:
        bytes_reserved = self._allocations.pop(request_id, 0)
        self._active_bytes = max(0, self._active_bytes - bytes_reserved)
