"""Graph module for daggr.

A Graph represents a directed acyclic graph (DAG) of nodes that can be
executed to process data through a pipeline.
"""

from __future__ import annotations

import os
import re
import sys
import warnings
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import networkx as nx

from daggr._utils import suggest_similar
from daggr.edge import Edge
from daggr.node import Node
from daggr.port import Port

if TYPE_CHECKING:
    from gradio.themes import ThemeClass as Theme


def _parse_space_id(src: str) -> str | None:
    if src.startswith("http://") or src.startswith("https://"):
        match = re.match(
            r"https?://huggingface\.co/spaces/([^/]+/[^/?#]+)", src
        )
        if match:
            return match.group(1)
        return None
    if "/" in src:
        return src
    return None


def _get_dependency_id(node) -> tuple[str | None, str]:
    from daggr.node import GradioNode, InferenceNode

    if isinstance(node, GradioNode):
        space_id = _parse_space_id(node._src)
        return space_id, "space"
    elif isinstance(node, InferenceNode):
        return node._model_name_for_hub, "model"
    return None, ""


def _fetch_current_sha(dep_id: str, dep_type: str) -> str | None:
    try:
        if dep_type == "space":
            from huggingface_hub import space_info

            info = space_info(dep_id)
            return info.sha
        elif dep_type == "model":
            from huggingface_hub import model_info

            info = model_info(dep_id)
            return info.sha
    except Exception:
        return None
    return None


def _duplicate_space_at_revision(
    space_id: str, revision: str, username: str
) -> str | None:
    try:
        from huggingface_hub import (
            create_repo,
            snapshot_download,
            upload_folder,
        )

        space_name = space_id.split("/")[-1]
        new_repo_id = f"{username}/{space_name}"

        local_dir = snapshot_download(
            repo_id=space_id,
            repo_type="space",
            revision=revision,
        )

        create_repo(
            repo_id=new_repo_id,
            repo_type="space",
            space_sdk="gradio",
            exist_ok=True,
        )

        upload_folder(
            repo_id=new_repo_id,
            repo_type="space",
            folder_path=local_dir,
        )

        return new_repo_id
    except Exception as e:
        print(f"  [daggr] Failed to duplicate Space: {e}")
        return None


def _prompt_dependency_changes(changed: list[dict]) -> None:
    from daggr import _client_cache

    is_tty = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()

    print("\n  ⚠️  Upstream dependency changes detected:\n")
    for item in changed:
        print(
            f"    • {item['type']} '{item['id']}' (node: {item['node']._name})\n"
            f"      cached:  {item['cached_sha'][:12]}\n"
            f"      current: {item['current_sha'][:12]}"
        )
    print()

    if not is_tty:
        for item in changed:
            _client_cache.set_dependency_hash(item["id"], item["current_sha"])
        print(
            "  [daggr] Non-interactive mode: auto-updated all hashes.\n"
            "  Set DAGGR_DEPENDENCY_CHECK=skip to suppress this warning.\n"
        )
        return

    for item in changed:
        is_space = item["type"] == "space"
        if is_space:
            print(
                f"  How would you like to handle '{item['id']}'?\n"
                f"    [1] Duplicate the original version under your namespace (safer)\n"
                f"    [2] Update to the latest version"
            )
        else:
            print(
                f"  How would you like to handle '{item['id']}'?\n"
                f"    [1] Update to the latest version"
            )

        try:
            choice = input("  Choice [1]: ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            choice = "1"

        if is_space and choice == "1":
            username = _get_hf_username()
            if username is None:
                print(
                    "  [daggr] Not logged in to Hugging Face. "
                    "Updating hash instead.\n"
                    "  Run `huggingface-cli login` to enable Space duplication."
                )
                _client_cache.set_dependency_hash(
                    item["id"], item["current_sha"]
                )
            else:
                print(
                    f"  [daggr] Duplicating '{item['id']}' at revision "
                    f"{item['cached_sha'][:12]} under {username}/..."
                )
                new_id = _duplicate_space_at_revision(
                    item["id"], item["cached_sha"], username
                )
                if new_id:
                    item["node"]._src = new_id
                    _client_cache.set_dependency_hash(new_id, item["cached_sha"])
                    print(
                        f"  [daggr] Duplicated → '{new_id}'. "
                        f"Node now points to duplicated Space."
                    )
                else:
                    print(
                        "  [daggr] Duplication failed (revision may have been "
                        "squashed). Updating hash instead."
                    )
                    _client_cache.set_dependency_hash(
                        item["id"], item["current_sha"]
                    )
        else:
            _client_cache.set_dependency_hash(item["id"], item["current_sha"])
            print(f"  [daggr] Updated hash for '{item['id']}'.")

    print()


def _get_hf_username() -> str | None:
    try:
        from huggingface_hub import get_token, whoami

        token = get_token()
        if not token:
            return None
        info = whoami(cache=True)
        return info.get("name")
    except Exception:
        return None


class Graph:
    """A directed acyclic graph (DAG) of nodes for data processing.

    A Graph connects nodes together to form a pipeline. Data flows from entry
    nodes (nodes with no inputs) through the graph to output nodes.

    Example:
        >>> from daggr import Graph, FnNode
        >>> def step1(x): return {"out": x * 2}
        >>> def step2(y): return {"out": y + 1}
        >>> n1 = FnNode(step1)
        >>> n2 = FnNode(step2, inputs={"y": n1.out})
        >>> graph = Graph("My Pipeline", nodes=[n2])
        >>> graph.launch()
    """

    def __init__(
        self,
        name: str,
        nodes: Sequence[Node] | None = None,
        persist_key: str | bool | None = None,
    ):
        """Create a new Graph.

        Args:
            name: Display name for this graph shown in the UI.
            nodes: Optional list of nodes to add to the graph.
            persist_key: Unique key used to store this graph's data in the database.
                         If not provided, derived from name by converting to lowercase
                         and replacing spaces/special chars with underscores.
                         Set to False to disable persistence entirely.
                         Use a custom string to ensure persistence works correctly
                         if you change the display name later.
        """
        if not name or not isinstance(name, str):
            raise ValueError(
                "Graph requires a 'name' parameter. "
                "Example: Graph(name='My Podcast Generator', nodes=[...])"
            )
        self.name = name
        if persist_key is False:
            self.persist_key = None
        elif persist_key:
            self.persist_key = persist_key
        else:
            import re

            self.persist_key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        self.nodes: dict[str, Node] = {}
        self._nx_graph = nx.DiGraph()
        self._edges: list[Edge] = []

        if nodes:
            for node in nodes:
                self.add(node)

    def add(self, node: Node) -> Graph:
        """Add a node to the graph.

        Also adds any upstream nodes connected via the node's port connections.

        Args:
            node: The node to add.

        Returns:
            self, for method chaining.
        """
        self._add_node(node)
        self._create_edges_from_port_connections(node)
        return self

    def edge(self, source: Port, target: Port) -> Graph:
        """Create an edge connecting two ports.

        Args:
            source: The source port (output of a node).
            target: The target port (input of a node).

        Returns:
            self, for method chaining.

        Raises:
            ValueError: If the edge would create a cycle.
        """
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

    def _create_edges_from_port_connections(self, node: Node) -> None:
        for target_port_name, source_port in node._port_connections.items():
            source_node = source_port.node
            source_port_name = source_port.name

            if source_port_name not in source_node._output_ports:
                available = set(source_node._output_ports)
                suggestion = suggest_similar(source_port_name, available)
                available_str = ", ".join(available) or "(none)"
                msg = (
                    f"Output port '{source_port_name}' not found on node "
                    f"'{source_node._name}'. Available outputs: {available_str}"
                )
                if suggestion:
                    msg += f" Did you mean '{suggestion}'?"
                raise ValueError(msg)

            is_new_node = source_node._name not in self.nodes
            self._add_node(source_node)
            if is_new_node:
                self._create_edges_from_port_connections(source_node)
            target_port = Port(node, target_port_name)
            edge = Edge(source_port, target_port)
            self._add_edge(edge)

    def _add_edge(self, edge: Edge) -> None:
        self._add_node(edge.source_node)
        self._add_node(edge.target_node)

        self._edges.append(edge)
        self._nx_graph.add_edge(edge.source_node._name, edge.target_node._name)

        if not nx.is_directed_acyclic_graph(self._nx_graph):
            self._nx_graph.remove_edge(edge.source_node._name, edge.target_node._name)
            self._edges.pop()
            raise ValueError("Connection would create a cycle in the DAG")

    def get_entry_nodes(self) -> list[Node]:
        """Get all nodes with no incoming edges (entry points of the graph)."""
        entry_nodes = []
        for node_name in self.nodes:
            if self._nx_graph.in_degree(node_name) == 0:
                entry_nodes.append(self.nodes[node_name])
        return entry_nodes

    def get_execution_order(self) -> list[str]:
        """Get the topologically sorted order of node names for execution."""
        return list(nx.topological_sort(self._nx_graph))

    def get_connections(self) -> list[tuple]:
        """Get all edges as tuples of (source_node, source_port, target_node, target_port)."""
        return [edge.as_tuple() for edge in self._edges]

    def _validate_edges(self) -> None:
        errors = []
        for edge in self._edges:
            source_node = edge.source_node
            target_node = edge.target_node
            source_port = edge.source_port
            target_port = edge.target_port

            if source_port not in source_node._output_ports:
                available = set(source_node._output_ports)
                available_str = ", ".join(available) or "(none)"
                suggestion = suggest_similar(source_port, available)
                msg = (
                    f"Output port '{source_port}' not found on node "
                    f"'{source_node._name}'. Available outputs: {available_str}"
                )
                if suggestion:
                    msg += f" Did you mean '{suggestion}'?"
                errors.append(msg)

            if target_port not in target_node._input_ports:
                available = set(target_node._input_ports)
                available_str = ", ".join(available) or "(none)"
                suggestion = suggest_similar(target_port, available)
                msg = (
                    f"Input port '{target_port}' not found on node "
                    f"'{target_node._name}'. Available inputs: {available_str}"
                )
                if suggestion:
                    msg += f" Did you mean '{suggestion}'?"
                errors.append(msg)

        if errors:
            raise ValueError("Invalid port connections:\n  - " + "\n  - ".join(errors))

    def launch(
        self,
        host: str | None = None,
        port: int | None = None,
        share: bool | None = None,
        open_browser: bool = True,
        theme: Theme | str | None = None,
        **kwargs,
    ):
        """Launch the graph as an interactive web application.

        Starts a web server that displays the graph and allows users to
        execute nodes and view results.

        Args:
            host: Host to bind to. Defaults to GRADIO_SERVER_NAME env var,
                or "127.0.0.1" if not set. Set to "0.0.0.0" to make
                accessible on a network or when deploying to Hugging Face Spaces.
            port: Port to bind to. Defaults to GRADIO_SERVER_PORT env var,
                or 7860 if not set.
            share: If True, create a public share link. Defaults to True in
                Colab/Kaggle environments, False otherwise.
            open_browser: If True, automatically open the app in the default
                web browser. Defaults to True.
            theme: A Gradio theme to use for styling. Can be a Gradio `Theme` instance,
                a string name like "default", "soft", "monochrome", "glass",
                or a Hub theme like "gradio/seafoam". Defaults to the Gradio
                default theme.
            **kwargs: Additional arguments passed to uvicorn.
        """
        import os

        from daggr.server import DaggrServer

        if host is None:
            host = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
        if port is None:
            port = int(os.environ.get("GRADIO_SERVER_PORT", "7860"))

        self._prepare_local_nodes()
        self._check_dependency_hashes()
        server = DaggrServer(self, theme=theme)
        server.run(
            host=host, port=port, share=share, open_browser=open_browser, **kwargs
        )

    def _prepare_local_nodes(self) -> None:
        from daggr.local_space import prepare_local_node
        from daggr.node import ChoiceNode, GradioNode

        for node in self.nodes.values():
            if isinstance(node, ChoiceNode):
                for variant in node._variants:
                    if isinstance(variant, GradioNode) and variant._run_locally:
                        prepare_local_node(variant)
            elif isinstance(node, GradioNode) and node._run_locally:
                prepare_local_node(node)

    def _check_dependency_hashes(self) -> None:
        mode = os.environ.get("DAGGR_DEPENDENCY_CHECK", "").lower()
        if mode == "skip":
            return

        from daggr import _client_cache
        from daggr.node import ChoiceNode, GradioNode, InferenceNode

        nodes_to_check: list[GradioNode | InferenceNode] = []
        for node in self.nodes.values():
            if isinstance(node, ChoiceNode):
                for variant in node._variants:
                    if isinstance(variant, (GradioNode, InferenceNode)):
                        nodes_to_check.append(variant)
            elif isinstance(node, (GradioNode, InferenceNode)):
                nodes_to_check.append(node)

        if not nodes_to_check:
            return

        changed: list[dict[str, Any]] = []
        for node in nodes_to_check:
            dep_id, dep_type = _get_dependency_id(node)
            if dep_id is None:
                continue

            current_sha = _fetch_current_sha(dep_id, dep_type)
            if current_sha is None:
                continue

            cached_sha = _client_cache.get_dependency_hash(dep_id)
            if cached_sha is None:
                _client_cache.set_dependency_hash(dep_id, current_sha)
            elif cached_sha != current_sha:
                changed.append({
                    "type": dep_type,
                    "id": dep_id,
                    "node": node,
                    "cached_sha": cached_sha,
                    "current_sha": current_sha,
                })

        if not changed:
            return

        if mode == "update":
            for item in changed:
                _client_cache.set_dependency_hash(item["id"], item["current_sha"])
                print(
                    f"  [daggr] Auto-updated hash for {item['type']} "
                    f"'{item['id']}' → {item['current_sha'][:12]}"
                )
            return

        if mode == "error":
            descs = [
                f"  • {item['type']} '{item['id']}': "
                f"{item['cached_sha'][:12]} → {item['current_sha'][:12]}"
                for item in changed
            ]
            raise RuntimeError(
                "Upstream dependencies have changed:\n"
                + "\n".join(descs)
                + "\nSet DAGGR_DEPENDENCY_CHECK=update to accept changes."
            )

        _prompt_dependency_changes(changed)

    def get_subgraphs(self) -> list[set[str]]:
        """Get all weakly connected components of the graph.

        Returns a list of sets, where each set contains the node names
        belonging to a connected subgraph. If the graph is fully connected,
        returns a single set with all node names.
        """
        return [set(c) for c in nx.weakly_connected_components(self._nx_graph)]

    def get_output_nodes(self) -> list[str]:
        """Get all nodes with no outgoing edges (output/leaf nodes)."""
        return [
            node_name
            for node_name in self.nodes
            if self._nx_graph.out_degree(node_name) == 0
        ]

    def get_api_schema(self) -> dict:
        """Get the API schema describing inputs and outputs for each subgraph.

        Returns a dict with:
        - subgraphs: list of subgraph info, each containing:
          - id: subgraph identifier (e.g., "main" or "subgraph_0")
          - inputs: list of {node, port, type, component} for each input
          - outputs: list of {node, port, type, component} for each output
        """
        from daggr.node import ChoiceNode

        subgraphs = self.get_subgraphs()
        output_nodes = set(self.get_output_nodes())
        result = {"subgraphs": []}

        for idx, subgraph_nodes in enumerate(subgraphs):
            subgraph_id = "main" if len(subgraphs) == 1 else f"subgraph_{idx}"

            inputs = []
            outputs = []

            for node_name in subgraph_nodes:
                node = self.nodes[node_name]

                if isinstance(node, ChoiceNode):
                    continue

                if node._input_components:
                    for port_name, comp in node._input_components.items():
                        comp_type = self._get_component_type(comp)
                        inputs.append(
                            {
                                "node": node_name,
                                "port": port_name,
                                "type": comp_type,
                                "id": f"{node_name}__{port_name}".replace(
                                    " ", "_"
                                ).replace("-", "_"),
                            }
                        )

                if node_name in output_nodes and node._output_components:
                    for port_name, comp in node._output_components.items():
                        if comp is None:
                            continue
                        comp_type = self._get_component_type(comp)
                        outputs.append(
                            {
                                "node": node_name,
                                "port": port_name,
                                "type": comp_type,
                            }
                        )

            result["subgraphs"].append(
                {
                    "id": subgraph_id,
                    "inputs": inputs,
                    "outputs": outputs,
                }
            )

        return result

    def _get_component_type(self, component) -> str:
        """Get the type string for a Gradio component."""
        class_name = component.__class__.__name__
        type_map = {
            "Audio": "audio",
            "Textbox": "textbox",
            "TextArea": "textarea",
            "JSON": "json",
            "Chatbot": "json",
            "Image": "image",
            "Number": "number",
            "Markdown": "markdown",
            "Text": "text",
            "Dropdown": "dropdown",
            "Video": "video",
            "File": "file",
            "Model3D": "model3d",
            "Gallery": "gallery",
            "Slider": "slider",
            "Radio": "radio",
            "Checkbox": "checkbox",
            "CheckboxGroup": "checkboxgroup",
            "ColorPicker": "colorpicker",
            "Label": "label",
            "HighlightedText": "highlightedtext",
            "Code": "code",
            "HTML": "html",
            "Dataframe": "dataframe",
        }
        return type_map.get(class_name, "text")

    def __repr__(self):
        return f"Graph(name={self.name}, nodes={len(self.nodes)}, edges={len(self._edges)})"
