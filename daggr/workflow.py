from typing import Dict, List, Optional, Tuple, Any
import networkx as nx
from gradio_client import Client

from daggr.node import GradioNode


class Workflow:
    def __init__(self, name: str = "daggr-workflow"):
        self.name = name
        self.nodes: Dict[str, GradioNode] = {}
        self.graph = nx.DiGraph()
        self.connections: List[Tuple[str, str, str, str]] = []

    def add_node(self, node: GradioNode) -> GradioNode:
        if node.name in self.nodes:
            raise ValueError(f"Node with name '{node.name}' already exists")
        self.nodes[node.name] = node
        self.graph.add_node(node.name)
        self._discover_node_api(node)
        return node

    def connect(
        self,
        source: GradioNode,
        source_output: str,
        target: GradioNode,
        target_input: str,
    ):
        if source.name not in self.nodes:
            raise ValueError(f"Source node '{source.name}' not in workflow")
        if target.name not in self.nodes:
            raise ValueError(f"Target node '{target.name}' not in workflow")

        self.connections.append((source.name, source_output, target.name, target_input))
        self.graph.add_edge(source.name, target.name)

        if not nx.is_directed_acyclic_graph(self.graph):
            self.graph.remove_edge(source.name, target.name)
            self.connections.pop()
            raise ValueError("Connection would create a cycle in the DAG")

    def mark_interaction(self, node: GradioNode):
        if node.name not in self.nodes:
            raise ValueError(f"Node '{node.name}' not in workflow")
        node.is_interaction_point = True

    def _discover_node_api(self, node: GradioNode):
        try:
            client = Client(node.src)
            api_info = client.view_api()
            node._api_info = api_info
            
            if isinstance(api_info, dict):
                endpoints = api_info.get("named_endpoints", {})
                predict_info = endpoints.get("/predict", {})
                if not predict_info:
                    for key, value in endpoints.items():
                        if "/predict" in key or key == "predict":
                            predict_info = value
                            break
                
                if predict_info:
                    node.inputs = predict_info.get("parameters", [])
                    node.outputs = predict_info.get("returns", [])
                else:
                    node.inputs = []
                    node.outputs = []
            else:
                node.inputs = []
                node.outputs = []
        except Exception as e:
            print(f"Warning: Could not discover API for {node.name}: {e}")
            node.inputs = []
            node.outputs = []

    def get_entry_nodes(self) -> List[GradioNode]:
        entry_nodes = []
        for node_name in self.nodes:
            if self.graph.in_degree(node_name) == 0:
                entry_nodes.append(self.nodes[node_name])
        return entry_nodes

    def get_execution_order(self) -> List[str]:
        return list(nx.topological_sort(self.graph))

    def launch(self, **kwargs):
        from daggr.ui import UIGenerator

        ui_generator = UIGenerator(self)
        demo = ui_generator.generate_ui()
        return demo.launch(**kwargs)

