from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from daggr.node import Node


class Port:
    def __init__(self, node: Node, name: str):
        self.node = node
        self.name = name

    def __repr__(self):
        return f"Port({self.node._name}.{self.name})"

    def _as_source(self) -> tuple[Node, str]:
        return (self.node, self.name)

    def _as_target(self) -> tuple[Node, str]:
        return (self.node, self.name)

    @property
    def each(self) -> ScatteredPort:
        """Scatter this port's output - run the downstream node once per item in the list."""
        return ScatteredPort(self)

    def all(self) -> GatheredPort:
        """Gather outputs from a scattered node back into a list."""
        return GatheredPort(self)


class ScatteredPort:
    def __init__(self, port: Port, item_key: Optional[str] = None):
        self.port = port
        self.item_key = item_key

    @property
    def node(self):
        return self.port.node

    @property
    def name(self):
        return self.port.name

    def __getitem__(self, key: str) -> ScatteredPort:
        """Access a specific field from each scattered item (e.g., dialogue.json.each["text"])."""
        return ScatteredPort(self.port, key)

    def __repr__(self):
        if self.item_key:
            return f"ScatteredPort({self.port}['{self.item_key}'])"
        return f"ScatteredPort({self.port})"


class GatheredPort:
    def __init__(self, port: Port):
        self.port = port

    @property
    def node(self):
        return self.port.node

    @property
    def name(self):
        return self.port.name

    def __repr__(self):
        return f"GatheredPort({self.port})"


def scatter(port: Port, item_key: Optional[str] = None) -> ScatteredPort:
    return ScatteredPort(port, item_key)


def gather(port: Port) -> GatheredPort:
    return GatheredPort(port)


PortLike = Union[Port, ScatteredPort, GatheredPort]


def is_port(obj: Any) -> bool:
    return isinstance(obj, (Port, ScatteredPort, GatheredPort))


class PortNamespace:
    def __init__(self, node: Node, port_names: list[str]):
        self._node = node
        self._names = set(port_names)

    def __getattr__(self, name: str) -> Port:
        if name.startswith("_"):
            raise AttributeError(name)
        return Port(self._node, name)

    def __dir__(self) -> list[str]:
        return list(self._names)

    def __repr__(self):
        return f"PortNamespace({list(self._names)})"


class ItemList:
    """Define an editable list output with per-item schema.

    Example:
        outputs={
            "items": ItemList(
                speaker=gr.Dropdown(choices=["Host", "Guest"]),
                text=gr.Textbox(lines=2),
            ),
        }

    The function should return a list of dicts matching the schema keys.
    """

    def __init__(self, **schema):
        self.schema = schema
