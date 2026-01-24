import json
from pathlib import Path

__version__ = json.loads((Path(__file__).parent / "package.json").read_text())[
    "version"
]

from daggr.edge import Edge
from daggr.graph import Graph
from daggr.node import FnNode, GradioNode, InferenceNode, InteractionNode, Node
from daggr.port import ItemList, Port
from daggr.server import DaggrServer

__all__ = [
    "__version__",
    "Edge",
    "Graph",
    "Node",
    "FnNode",
    "GradioNode",
    "InferenceNode",
    "InteractionNode",
    "ItemList",
    "Port",
    "DaggrServer",
]
