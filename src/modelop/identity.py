from __future__ import annotations

import asyncio


class InflightRequestRegistry:
    """Track in-flight request IDs to prevent concurrent collisions."""

    def __init__(self) -> None:
        self._active_request_ids: set[str] = set()
        self._lock = asyncio.Lock()

    async def claim(self, request_id: str) -> bool:
        async with self._lock:
            if request_id in self._active_request_ids:
                return False
            self._active_request_ids.add(request_id)
            return True

    async def release(self, request_id: str) -> None:
        async with self._lock:
            self._active_request_ids.discard(request_id)
