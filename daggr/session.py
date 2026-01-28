"""Session management for daggr.

This module provides per-session execution contexts for security isolation
and concurrency management.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from daggr.graph import Graph


class ConcurrencyManager:
    """Manages concurrency limits for FnNode execution within a session.
    
    By default, only one FnNode runs at a time per session. FnNodes can opt
    into concurrent execution via the `concurrent` parameter, and can share
    limits via `concurrency_group`.
    """

    def __init__(self):
        self._default_semaphore = asyncio.Semaphore(1)
        self._group_semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def get_semaphore(
        self,
        concurrent: bool,
        concurrency_group: str | None,
        max_concurrent: int,
    ) -> asyncio.Semaphore | None:
        """Get the appropriate semaphore for a FnNode.
        
        Returns None if the node should run without concurrency limits
        (concurrent=True with no group).
        """
        if not concurrent:
            return self._default_semaphore

        if concurrency_group:
            async with self._lock:
                if concurrency_group not in self._group_semaphores:
                    self._group_semaphores[concurrency_group] = asyncio.Semaphore(
                        max_concurrent
                    )
                return self._group_semaphores[concurrency_group]

        return None


class ExecutionSession:
    """Per-session execution context.
    
    Each WebSocket connection gets its own ExecutionSession, providing:
    - Isolated HF token
    - Isolated results cache
    - Isolated Gradio client cache
    - Per-session concurrency management
    """

    def __init__(self, graph: Graph, hf_token: str | None = None):
        self.graph = graph
        self.hf_token = hf_token
        self.results: dict[str, Any] = {}
        self.scattered_results: dict[str, list[Any]] = {}
        self.selected_variants: dict[str, int] = {}
        self.clients: dict[str, Any] = {}
        self.concurrency = ConcurrencyManager()

    def set_hf_token(self, token: str | None):
        """Update the HF token and clear cached clients."""
        if token != self.hf_token:
            self.hf_token = token
            self.clients = {}

    def clear_results(self):
        """Clear cached results for a fresh execution."""
        self.results = {}
        self.scattered_results = {}

