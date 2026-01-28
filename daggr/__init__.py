"""daggr - Build visual, node-based AI pipelines with Gradio Spaces.

daggr lets you create DAG (directed acyclic graph) pipelines that connect
Gradio Spaces, Hugging Face models, and Python functions into interactive
applications.

Example:
    >>> from daggr import Graph, GradioNode, FnNode
    >>> import gradio as gr
    >>>
    >>> tts = GradioNode(
    ...     "mrfakename/MeloTTS",
    ...     inputs={"text": gr.Textbox()},
    ...     outputs={"audio": gr.Audio()},
    ... )
    >>> graph = Graph("TTS Demo", nodes=[tts])
    >>> graph.launch()
"""

import json
from pathlib import Path

__version__ = json.loads((Path(__file__).parent / "package.json").read_text())[
    "version"
]

from daggr.edge import Edge
from daggr.graph import Graph
from daggr.node import (
    ChoiceNode,
    FnNode,
    GradioNode,
    InferenceNode,
    InteractionNode,
    Node,
)
from daggr.port import ItemList, Port
from daggr.server import DaggrServer

__all__ = [
    "__version__",
    "ChoiceNode",
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
