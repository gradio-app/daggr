from __future__ import annotations

from typing import Dict, List

import networkx as nx

from daggr.edge import Edge
from daggr.node import GradioNode, Node
from daggr.port import Port


class Graph:
    def __init__(self, name: str = "daggr-workflow"):
        self.name = name
        self.nodes: Dict[str, Node] = {}
        self._nx_graph = nx.DiGraph()
        self._edges: List[Edge] = []

    def edge(self, source: Port, target: Port) -> Graph:
        edge = Edge(source, target)
        self._add_edge(edge)
        return self

    def _add_node(self, node: Node) -> None:
        if node._name in self.nodes:
            if self.nodes[node._name] is not node:
                raise ValueError(f"Node with name '{node._name}' already exists")
            return
        self.nodes[node._name] = node
        self._nx_graph.add_node(node._name)

        if isinstance(node, GradioNode):
            node.discover_api()

    def _add_edge(self, edge: Edge) -> None:
        self._add_node(edge.source_node)
        self._add_node(edge.target_node)

        self._edges.append(edge)
        self._nx_graph.add_edge(edge.source_node._name, edge.target_node._name)

        if not nx.is_directed_acyclic_graph(self._nx_graph):
            self._nx_graph.remove_edge(edge.source_node._name, edge.target_node._name)
            self._edges.pop()
            raise ValueError("Connection would create a cycle in the DAG")

    def get_entry_nodes(self) -> List[Node]:
        entry_nodes = []
        for node_name in self.nodes:
            if self._nx_graph.in_degree(node_name) == 0:
                entry_nodes.append(self.nodes[node_name])
        return entry_nodes

    def get_execution_order(self) -> List[str]:
        return list(nx.topological_sort(self._nx_graph))

    def get_connections(self) -> List[tuple]:
        return [edge.as_tuple() for edge in self._edges]

    def launch(self, **kwargs):
        from daggr.ui import UIGenerator

        ui_generator = UIGenerator(self)
        demo = ui_generator.generate_ui()
        if hasattr(ui_generator, "_custom_css"):
            kwargs.setdefault("css", ui_generator._custom_css)
        return demo.launch(**kwargs)

    def __repr__(self):
        return f"Graph(name={self.name}, nodes={len(self.nodes)}, edges={len(self._edges)})"
