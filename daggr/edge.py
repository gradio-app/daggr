from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from daggr.port import Port


class Edge:
    def __init__(self, source: Port, target: Port):
        self.source_node = source.node
        self.source_port = source.name
        self.target_node = target.node
        self.target_port = target.name

    def __repr__(self):
        return (
            f"Edge({self.source_node._name}.{self.source_port} -> "
            f"{self.target_node._name}.{self.target_port})"
        )

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (
            self.source_node._name,
            self.source_port,
            self.target_node._name,
            self.target_port,
        )
