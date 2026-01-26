from __future__ import annotations

import asyncio
import json
import mimetypes
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from daggr.executor import SequentialExecutor
from daggr.state import SessionState

if TYPE_CHECKING:
    from daggr.graph import Graph


class DaggrServer:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.executor = SequentialExecutor(graph)
        self.state = SessionState()
        self.app = FastAPI(title=graph.name)
        self.connections: Dict[str, WebSocket] = {}
        self._setup_routes()

    def _setup_routes(self):
        frontend_dir = Path(__file__).parent / "frontend" / "dist"
        if not frontend_dir.exists():
            raise RuntimeError(
                f"Frontend not found at {frontend_dir}. "
                "If developing, run 'npm run build' in daggr/frontend/"
            )

        @self.app.get("/api/graph")
        async def get_graph():
            return self._build_graph_data()

        @self.app.get("/api/hf_user")
        async def get_hf_user():
            return self._get_hf_user_info()

        @self.app.get("/api/user_info")
        async def get_user_info():
            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            is_on_spaces = os.environ.get("SPACE_ID") is not None
            return {
                "hf_user": hf_user,
                "user_id": user_id,
                "is_on_spaces": is_on_spaces,
                "can_persist": user_id is not None,
            }

        @self.app.get("/api/sheets")
        async def list_sheets():
            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            if not user_id:
                return JSONResponse(
                    {"error": "Login required to access sheets on Spaces"},
                    status_code=401,
                )
            sheets = self.state.list_sheets(user_id, self.graph.name)
            return {"sheets": sheets, "user_id": user_id}

        @self.app.post("/api/sheets")
        async def create_sheet(request: Request):
            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            if not user_id:
                return JSONResponse(
                    {"error": "Login required to create sheets on Spaces"},
                    status_code=401,
                )
            body = await request.json()
            name = body.get("name")
            sheet_id = self.state.create_sheet(user_id, self.graph.name, name)
            sheet = self.state.get_sheet(sheet_id)
            return {"sheet": sheet}

        @self.app.patch("/api/sheets/{sheet_id}")
        async def rename_sheet(sheet_id: str, request: Request):
            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            if not user_id:
                return JSONResponse({"error": "Login required"}, status_code=401)
            sheet = self.state.get_sheet(sheet_id)
            if not sheet:
                return JSONResponse({"error": "Sheet not found"}, status_code=404)
            if sheet["user_id"] != user_id:
                return JSONResponse({"error": "Access denied"}, status_code=403)
            body = await request.json()
            new_name = body.get("name")
            if not new_name:
                return JSONResponse({"error": "Name required"}, status_code=400)
            self.state.rename_sheet(sheet_id, new_name)
            return {"success": True, "sheet": self.state.get_sheet(sheet_id)}

        @self.app.delete("/api/sheets/{sheet_id}")
        async def delete_sheet(sheet_id: str):
            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            if not user_id:
                return JSONResponse({"error": "Login required"}, status_code=401)
            sheet = self.state.get_sheet(sheet_id)
            if not sheet:
                return JSONResponse({"error": "Sheet not found"}, status_code=404)
            if sheet["user_id"] != user_id:
                return JSONResponse({"error": "Access denied"}, status_code=403)
            self.state.delete_sheet(sheet_id)
            return {"success": True}

        @self.app.get("/api/sheets/{sheet_id}/state")
        async def get_sheet_state(sheet_id: str):
            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            if not user_id:
                return JSONResponse({"error": "Login required"}, status_code=401)
            sheet = self.state.get_sheet(sheet_id)
            if not sheet:
                return JSONResponse({"error": "Sheet not found"}, status_code=404)
            if sheet["user_id"] != user_id:
                return JSONResponse({"error": "Access denied"}, status_code=403)
            state = self.state.get_sheet_state(sheet_id)
            return {"sheet": sheet, "state": state}

        @self.app.post("/api/run/{node_name}")
        async def run_to_node(node_name: str, data: dict):
            session_id = data.get("session_id")
            input_values = data.get("inputs", {})
            selected_results = data.get("selected_results", {})
            return self._execute_to_node(
                node_name, session_id, input_values, selected_results
            )

        @self.app.websocket("/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            await websocket.accept()
            self.connections[session_id] = websocket

            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            current_sheet_id: Optional[str] = None

            try:
                while True:
                    data = await websocket.receive_json()
                    action = data.get("action")

                    if action == "run":
                        node_name = data.get("node_name")
                        input_values = data.get("inputs", {})
                        item_list_values = data.get("item_list_values", {})
                        selected_results = data.get("selected_results", {})
                        run_id = data.get("run_id")
                        sheet_id = data.get("sheet_id") or current_sheet_id

                        async for result in self._execute_to_node_streaming(
                            node_name,
                            sheet_id,
                            input_values,
                            item_list_values,
                            selected_results,
                            run_id,
                            user_id,
                        ):
                            await websocket.send_json(result)

                    elif action == "get_graph":
                        try:
                            sheet_id = data.get("sheet_id")

                            persisted_inputs = {}
                            persisted_results: Dict[str, List[Any]] = {}
                            persisted_transform = None

                            if user_id and sheet_id:
                                sheet = self.state.get_sheet(sheet_id)
                                if sheet and sheet["user_id"] == user_id:
                                    current_sheet_id = sheet_id
                                    state = self.state.get_sheet_state(sheet_id)
                                    persisted_inputs = state.get("inputs", {})
                                    persisted_results = state.get("results", {})
                                    persisted_transform = sheet.get("transform")

                            node_results = {}
                            for node_name, results_list in persisted_results.items():
                                if results_list:
                                    node_results[node_name] = results_list[-1]

                            graph_data = self._build_graph_data(
                                node_results=node_results,
                                input_values=persisted_inputs,
                            )
                            graph_data["session_id"] = session_id
                            graph_data["sheet_id"] = current_sheet_id
                            graph_data["user_id"] = user_id
                            graph_data["persisted_results"] = persisted_results
                            graph_data["transform"] = persisted_transform

                            await websocket.send_json(
                                {"type": "graph", "data": graph_data}
                            )
                        except Exception as e:
                            print(f"[ERROR] get_graph failed: {e}")
                            import traceback

                            traceback.print_exc()
                            await websocket.send_json(
                                {"type": "error", "error": str(e)}
                            )

                    elif action == "save_input":
                        if user_id and current_sheet_id:
                            node_id = data.get("node_id")
                            port_name = data.get("port_name")
                            value = data.get("value")
                            if node_id and port_name is not None:
                                self.state.save_input(
                                    current_sheet_id, node_id, port_name, value
                                )
                                await websocket.send_json(
                                    {"type": "input_saved", "node_id": node_id}
                                )

                    elif action == "save_transform":
                        if user_id and current_sheet_id:
                            x = data.get("x", 0)
                            y = data.get("y", 0)
                            scale = data.get("scale", 1)
                            self.state.save_transform(current_sheet_id, x, y, scale)

                    elif action == "set_sheet":
                        sheet_id = data.get("sheet_id")
                        if user_id and sheet_id:
                            sheet = self.state.get_sheet(sheet_id)
                            if sheet and sheet["user_id"] == user_id:
                                current_sheet_id = sheet_id
                                await websocket.send_json(
                                    {"type": "sheet_set", "sheet_id": sheet_id}
                                )

            except WebSocketDisconnect:
                if session_id in self.connections:
                    del self.connections[session_id]
            except Exception as e:
                print(f"[ERROR] WebSocket error: {e}")
                import traceback

                traceback.print_exc()

        @self.app.get("/")
        async def serve_index():
            index_path = frontend_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return HTMLResponse(self._get_dev_html())

        @self.app.get("/assets/{path:path}")
        async def serve_assets(path: str):
            file_path = frontend_dir / "assets" / path
            if file_path.exists():
                content_type, _ = mimetypes.guess_type(str(file_path))
                return FileResponse(file_path, media_type=content_type)
            return Response(status_code=404)

        @self.app.get("/file/{path:path}")
        async def serve_local_file(path: str):
            import tempfile

            file_path = Path("/") / path
            temp_dir = Path(tempfile.gettempdir()).resolve()
            try:
                resolved = file_path.resolve()
                if not str(resolved).startswith(str(temp_dir)):
                    return Response(status_code=403)
            except (ValueError, OSError):
                return Response(status_code=403)
            if resolved.exists() and resolved.is_file():
                content_type, _ = mimetypes.guess_type(str(resolved))
                return FileResponse(
                    resolved, media_type=content_type or "application/octet-stream"
                )
            return Response(status_code=404)

        @self.app.get("/{path:path}")
        async def serve_static(path: str):
            if path.startswith("api/") or path.startswith("ws/"):
                return Response(status_code=404)
            file_path = frontend_dir / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            index_path = frontend_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return HTMLResponse(self._get_dev_html())

    def _get_dev_html(self) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.graph.name}</title>
    <script type="module" src="http://localhost:5173/src/main.ts"></script>
</head>
<body>
    <div id="app"></div>
</body>
</html>"""

    def _get_node_type(self, node, node_name: str) -> str:
        type_map = {
            "FnNode": "FN",
            "TextInput": "INPUT",
            "ImageInput": "IMAGE",
            "ChooseOne": "SELECT",
            "Approve": "APPROVE",
            "GradioNode": "GRADIO",
            "InferenceNode": "MODEL",
            "InteractionNode": "ACTION",
        }
        class_name = node.__class__.__name__
        return type_map.get(class_name, class_name.upper())

    def _has_scattered_input(self, node_name: str) -> bool:
        for edge in self.graph._edges:
            if edge.target_node._name == node_name and edge.is_scattered:
                return True
        return False

    def _get_scattered_edge(self, node_name: str):
        for edge in self.graph._edges:
            if edge.target_node._name == node_name and edge.is_scattered:
                return edge
        return None

    def _is_output_node(self, node_name: str) -> bool:
        return self.graph._nx_graph.out_degree(node_name) == 0

    def _get_component_type(self, component) -> str:
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
        }
        return type_map.get(class_name, "text")

    def _serialize_component(self, comp, port_name: str) -> Dict[str, Any]:
        comp_type = self._get_component_type(comp)
        comp_class = comp.__class__.__name__

        props = {
            "label": getattr(comp, "label", "") or port_name,
            "show_label": bool(getattr(comp, "label", "")),
            "interactive": getattr(comp, "interactive", True),
            "visible": getattr(comp, "visible", True),
        }

        if hasattr(comp, "placeholder"):
            props["placeholder"] = comp.placeholder
        if hasattr(comp, "lines"):
            props["lines"] = comp.lines
        if hasattr(comp, "max_lines"):
            props["max_lines"] = comp.max_lines
        if hasattr(comp, "type"):
            props["type"] = comp.type
        if hasattr(comp, "choices") and comp.choices:
            props["choices"] = [
                c[1] if isinstance(c, (tuple, list)) else c for c in comp.choices
            ]

        return {
            "component": comp_class.lower(),
            "type": comp_type,
            "port_name": port_name,
            "props": props,
            "value": getattr(comp, "value", None),
        }

    def _file_to_url(self, value: Any) -> Any:
        if (
            isinstance(value, str)
            and value.startswith("/")
            and not value.startswith("/file/")
        ):
            if Path(value).exists():
                return f"/file{value}"
        return value

    def _build_input_components(self, node) -> List[Dict[str, Any]]:
        if not node._input_components:
            return []
        return [
            self._serialize_component(comp, port_name)
            for port_name, comp in node._input_components.items()
        ]

    def _build_output_components(
        self, node, result: Any = None
    ) -> List[Dict[str, Any]]:
        if not node._output_components:
            return []

        components = []
        for port_name, comp in node._output_components.items():
            if comp is None:
                continue

            visible = getattr(comp, "visible", True)
            if visible is False:
                continue

            comp_data = self._serialize_component(comp, port_name)
            comp_type = self._get_component_type(comp)
            if result is not None:
                if isinstance(result, dict):
                    value = result.get(
                        port_name, result.get(comp_data["props"]["label"])
                    )
                else:
                    value = result
                if comp_type == "audio":
                    value = self._file_to_url(value)
                if comp_type == "image":
                    value = self._file_to_url(value)
                comp_data["value"] = value
            components.append(comp_data)
        return components

    def _build_scattered_items(
        self, node_name: str, result: Any = None
    ) -> List[Dict[str, Any]]:
        scattered_edge = self._get_scattered_edge(node_name)
        if not scattered_edge:
            return []

        node = self.graph.nodes[node_name]
        item_output_type = "text"
        for comp in node._output_components.values():
            if comp is None:
                continue
            comp_type = self._get_component_type(comp)
            if comp_type == "audio":
                item_output_type = "audio"
                break

        items = []
        if result and isinstance(result, dict) and "_scattered_results" in result:
            results = result["_scattered_results"]
            source_items = result.get("_items", [])
            for i, item_result in enumerate(results):
                source_item = source_items[i] if i < len(source_items) else None
                preview = ""
                output = None

                if isinstance(source_item, dict):
                    preview_parts = [
                        f"{k}: {str(v)[:20]}" for k, v in list(source_item.items())[:2]
                    ]
                    preview = ", ".join(preview_parts)
                elif source_item:
                    preview = str(source_item)[:50]

                if isinstance(item_result, dict):
                    first_key = list(item_result.keys())[0] if item_result else None
                    if first_key:
                        output = item_result[first_key]
                else:
                    output = item_result

                if output and item_output_type == "audio":
                    output = self._file_to_url(output)
                elif output:
                    output = str(output)

                items.append(
                    {
                        "index": i + 1,
                        "preview": preview or f"Item {i + 1}",
                        "output": output,
                        "is_audio_output": item_output_type == "audio",
                    }
                )
        return items

    def _serialize_item_list_schema(
        self, schema: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        serialized = []
        for field_name, comp in schema.items():
            comp_data = self._serialize_component(comp, field_name)
            serialized.append(comp_data)
        return serialized

    def _build_item_list_items(
        self, node, port_name: str, result: Any = None
    ) -> List[Dict[str, Any]]:
        schema = node._item_list_schemas.get(port_name, {})
        if not schema:
            return []

        items = []
        if result and isinstance(result, dict) and port_name in result:
            item_list = result[port_name]
            if isinstance(item_list, list):
                for i, item_data in enumerate(item_list):
                    item = {"index": i, "fields": {}}
                    if isinstance(item_data, dict):
                        for field_name in schema:
                            item["fields"][field_name] = item_data.get(field_name)
                    items.append(item)
        return items

    def _apply_item_list_edits(
        self, node_name: str, result: Any, item_list_values: Dict
    ) -> Any:
        node = self.graph.nodes[node_name]
        if not node._item_list_schemas:
            return result

        node_id = node_name.replace(" ", "_").replace("-", "_")
        edits = item_list_values.get(node_id, {})
        if not edits:
            return result

        first_port = list(node._item_list_schemas.keys())[0]
        if isinstance(result, dict) and first_port in result:
            items = result[first_port]
            if isinstance(items, list):
                for idx_str, field_edits in edits.items():
                    idx = int(idx_str)
                    if 0 <= idx < len(items) and isinstance(items[idx], dict):
                        items[idx].update(field_edits)
        return result

    def _compute_node_depths(self) -> Dict[str, int]:
        depths: Dict[str, int] = {}
        connections = self.graph.get_connections()

        for node_name in self.graph.nodes:
            if self.graph._nx_graph.in_degree(node_name) == 0:
                depths[node_name] = 0

        changed = True
        while changed:
            changed = False
            for source, _, target, _ in connections:
                if source in depths:
                    new_depth = depths[source] + 1
                    if target not in depths or depths[target] < new_depth:
                        depths[target] = new_depth
                        changed = True

        for node_name in self.graph.nodes:
            if node_name not in depths:
                depths[node_name] = 0

        return depths

    def _get_hf_user_info(self) -> Optional[dict]:
        try:
            from huggingface_hub import get_token, whoami

            token = get_token()
            if not token:
                return None

            info = whoami()
            return {
                "username": info.get("name"),
                "fullname": info.get("fullname"),
                "avatar_url": info.get("avatarUrl"),
            }
        except Exception:
            return None

    def _build_graph_data(
        self,
        node_results: Dict[str, Any] | None = None,
        node_statuses: Dict[str, str] | None = None,
        input_values: Dict[str, Any] | None = None,
        history: Dict[str, Dict[str, List[Dict]]] | None = None,
        session_id: str | None = None,
    ) -> dict:
        node_results = node_results or {}
        node_statuses = node_statuses or {}
        input_values = input_values or {}
        history = history or {}

        depths = self._compute_node_depths()

        synthetic_input_nodes: List[Dict[str, Any]] = []
        synthetic_edges: List[Dict[str, Any]] = []
        input_node_positions: Dict[str, tuple] = {}

        component_to_input_node: Dict[int, str] = {}
        creation_order = 0
        for node_name in self.graph.nodes:
            node = self.graph.nodes[node_name]
            if node._input_components:
                for idx, (port_name, comp) in enumerate(node._input_components.items()):
                    comp_id = id(comp)

                    if comp_id in component_to_input_node:
                        existing_input_node = component_to_input_node[comp_id]
                        existing_input_id = existing_input_node.replace(
                            " ", "_"
                        ).replace("-", "_")
                        synthetic_edges.append(
                            {
                                "from_node": existing_input_id,
                                "from_port": "value",
                                "to_node": node_name.replace(" ", "_").replace(
                                    "-", "_"
                                ),
                                "to_port": port_name,
                            }
                        )
                        continue

                    input_node_name = f"{node_name}__{port_name}"
                    input_node_id = input_node_name.replace(" ", "_").replace("-", "_")
                    component_to_input_node[comp_id] = input_node_name

                    comp_data = self._serialize_component(comp, "value")
                    label = comp_data["props"].get("label") or port_name

                    if input_node_id in input_values:
                        comp_data["value"] = input_values[input_node_id].get(
                            "value", comp_data["value"]
                        )

                    synthetic_input_nodes.append(
                        {
                            "node_name": input_node_name,
                            "display_name": label,
                            "target_node": node_name,
                            "target_port": port_name,
                            "component": comp_data,
                            "index": idx,
                            "creation_order": creation_order,
                        }
                    )
                    creation_order += 1

                    synthetic_edges.append(
                        {
                            "from_node": input_node_id,
                            "from_port": "value",
                            "to_node": node_name.replace(" ", "_").replace("-", "_"),
                            "to_port": port_name,
                        }
                    )

        max_depth = max(depths.values()) if depths else 0

        nodes_by_depth: Dict[int, List[str]] = {}
        for node_name, depth in depths.items():
            if depth not in nodes_by_depth:
                nodes_by_depth[depth] = []
            nodes_by_depth[depth].append(node_name)

        x_spacing = 350
        input_column_x = 50
        x_start = 400
        y_start = 120
        y_gap = 30
        base_node_height = 100
        component_base_height = 60
        line_height = 18

        def calc_component_height(comp_data: Dict) -> int:
            lines = comp_data.get("props", {}).get("lines", 1)
            lines = min(lines, 6)
            return component_base_height + max(0, lines - 1) * line_height

        def calc_node_height(components: List[Dict], num_ports: int = 1) -> int:
            comp_height = sum(calc_component_height(c) for c in components)
            port_height = max(num_ports, 1) * 22
            return base_node_height + port_height + comp_height

        all_input_nodes_sorted: List[Dict] = []
        for syn_node in synthetic_input_nodes:
            target_depth = depths.get(syn_node["target_node"], 0)
            all_input_nodes_sorted.append({**syn_node, "target_depth": target_depth})
        all_input_nodes_sorted.sort(key=lambda x: x["creation_order"])

        current_input_y = y_start
        for syn_node in all_input_nodes_sorted:
            input_node_positions[syn_node["node_name"]] = (
                input_column_x,
                current_input_y,
            )
            node_height = calc_node_height([syn_node["component"]], 1)
            current_input_y += node_height + y_gap

        node_positions: Dict[str, tuple] = {}
        for depth in range(max_depth + 1):
            depth_nodes = nodes_by_depth.get(depth, [])
            current_y = y_start
            for node_name in depth_nodes:
                node = self.graph.nodes[node_name]
                output_comps = self._build_output_components(node)
                num_ports = max(
                    len(node._input_ports or []), len(node._output_ports or [])
                )
                node_height = calc_node_height(output_comps, num_ports)
                x = x_start + depth * x_spacing
                node_positions[node_name] = (x, current_y)
                current_y += node_height + y_gap

        nodes = []

        for syn_node in synthetic_input_nodes:
            node_name = syn_node["node_name"]
            display_name = syn_node["display_name"]
            node_id = node_name.replace(" ", "_").replace("-", "_")
            x, y = input_node_positions.get(node_name, (50, 50))
            comp = syn_node["component"]

            nodes.append(
                {
                    "id": node_id,
                    "name": display_name,
                    "type": "INPUT",
                    "inputs": [],
                    "outputs": ["value"],
                    "x": x,
                    "y": y,
                    "has_input": False,
                    "input_value": "",
                    "input_components": [comp],
                    "output_components": [],
                    "is_map_node": False,
                    "map_items": [],
                    "map_item_count": 0,
                    "item_output_type": "text",
                    "status": "pending",
                    "result": "",
                    "is_output_node": False,
                    "is_input_node": True,
                }
            )

        for node_name in self.graph.nodes:
            node = self.graph.nodes[node_name]
            x, y = node_positions.get(node_name, (50, 50))

            result = node_results.get(node_name)
            result_str = ""
            is_scattered = self._has_scattered_input(node_name)
            if result is not None and not node._output_components and not is_scattered:
                if isinstance(result, dict):
                    display_result = {
                        k: v for k, v in result.items() if not k.startswith("_")
                    }
                    result_str = json.dumps(display_result, indent=2, default=str)[:300]
                elif isinstance(result, (list, tuple)):
                    result_str = json.dumps(list(result)[:5], default=str)
                else:
                    result_str = str(result)[:300]

            node_id = node_name.replace(" ", "_").replace("-", "_")

            input_ports_data = []
            for port in node._input_ports or []:
                if port in node._fixed_inputs:
                    continue
                port_history = history.get(node_name, {}).get(port, [])
                input_ports_data.append(
                    {
                        "name": port,
                        "history_count": len(port_history) if port_history else 0,
                    }
                )

            output_components = self._build_output_components(node, result)
            scattered_items = (
                self._build_scattered_items(node_name, result) if is_scattered else []
            )

            item_output_type = "text"
            if is_scattered:
                for comp in node._output_components.values():
                    if comp is None:
                        continue
                    comp_type = self._get_component_type(comp)
                    if comp_type == "audio":
                        item_output_type = "audio"
                        break

            item_list_schema = None
            item_list_items = []
            if node._item_list_schemas:
                first_port = list(node._item_list_schemas.keys())[0]
                item_list_schema = self._serialize_item_list_schema(
                    node._item_list_schemas[first_port]
                )
                item_list_items = self._build_item_list_items(node, first_port, result)

            output_ports = []
            for port_name in node._output_ports or []:
                if port_name in node._item_list_schemas:
                    schema = node._item_list_schemas[port_name]
                    for field_name in schema:
                        output_ports.append(f"{port_name}.{field_name}")
                elif port_name in node._output_components:
                    output_ports.append(port_name)

            is_output = self._is_output_node(node_name)

            nodes.append(
                {
                    "id": node_id,
                    "name": node_name,
                    "type": self._get_node_type(node, node_name),
                    "inputs": input_ports_data,
                    "outputs": output_ports,
                    "x": x,
                    "y": y,
                    "has_input": False,
                    "input_value": input_values.get(node_name, ""),
                    "input_components": [],
                    "output_components": output_components,
                    "is_map_node": is_scattered,
                    "map_items": scattered_items,
                    "map_item_count": len(scattered_items),
                    "item_output_type": item_output_type,
                    "item_list_schema": item_list_schema,
                    "item_list_items": item_list_items,
                    "status": node_statuses.get(node_name, "pending"),
                    "result": result_str,
                    "is_output_node": is_output,
                    "is_input_node": False,
                }
            )

        edges = []
        for i, edge in enumerate(self.graph._edges):
            from_port = edge.source_port
            if edge.item_key:
                from_port = f"{edge.source_port}.{edge.item_key}"
            edges.append(
                {
                    "id": f"edge_{i}",
                    "from_node": edge.source_node._name.replace(" ", "_").replace(
                        "-", "_"
                    ),
                    "from_port": from_port,
                    "to_node": edge.target_node._name.replace(" ", "_").replace(
                        "-", "_"
                    ),
                    "to_port": edge.target_port,
                    "is_scattered": edge.is_scattered,
                    "is_gathered": edge.is_gathered,
                }
            )

        for i, syn_edge in enumerate(synthetic_edges):
            edges.append(
                {
                    "id": f"input_edge_{i}",
                    "from_node": syn_edge["from_node"],
                    "from_port": syn_edge["from_port"],
                    "to_node": syn_edge["to_node"],
                    "to_port": syn_edge["to_port"],
                }
            )

        return {
            "name": self.graph.name,
            "nodes": nodes,
            "edges": edges,
            "inputs": input_values,
            "history": history,
            "session_id": session_id,
        }

    def _get_ancestors(self, node_name: str) -> List[str]:
        ancestors = set()
        to_visit = [node_name]
        while to_visit:
            current = to_visit.pop()
            for source, _, target, _ in self.graph.get_connections():
                if target == current and source not in ancestors:
                    ancestors.add(source)
                    to_visit.append(source)
        return list(ancestors)

    def _get_user_provided_output(
        self, node, node_id: str, input_values: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not node._output_components:
            return None

        node_inputs = input_values.get(node_id, {})
        if not node_inputs:
            return None

        result = {}
        has_user_value = False
        for port_name, comp in node._output_components.items():
            if comp is None:
                continue
            if port_name in node_inputs:
                value = node_inputs[port_name]
                if value is not None:
                    if isinstance(value, str) and value.startswith("data:"):
                        value = self._save_data_url_as_gradio_file(value)
                    result[port_name] = value
                    has_user_value = True

        return result if has_user_value else None

    def _save_data_url_as_gradio_file(self, data_url: str):
        import base64
        import tempfile
        import uuid

        from daggr.executor import FileValue

        try:
            header, data = data_url.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            ext_map = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "audio/webm": ".webm",
                "audio/wav": ".wav",
                "audio/mp3": ".mp3",
                "audio/mpeg": ".mp3",
            }
            ext = ext_map.get(mime_type, ".bin")
            file_data = base64.b64decode(data)
            temp_dir = Path(tempfile.gettempdir()) / "daggr_uploads"
            temp_dir.mkdir(exist_ok=True)
            file_path = temp_dir / f"{uuid.uuid4()}{ext}"
            file_path.write_bytes(file_data)
            return FileValue(str(file_path))
        except Exception as e:
            print(f"[ERROR] Failed to save data URL: {e}")
            return data_url

    def _convert_urls_to_file_values(self, data: Any) -> Any:
        from daggr.executor import FileValue

        if isinstance(data, str):
            if data.startswith(("http://", "https://", "/")) and any(
                data.lower().endswith(ext)
                for ext in (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp",
                    ".wav",
                    ".mp3",
                    ".webm",
                    ".mp4",
                    ".ogg",
                )
            ):
                return FileValue(data)
            return data
        elif isinstance(data, dict):
            return {k: self._convert_urls_to_file_values(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_urls_to_file_values(item) for item in data]
        return data

    def _execute_to_node(
        self,
        target_node: str,
        session_id: Optional[str],
        input_values: Dict[str, Any],
        selected_results: Dict[str, int],
    ) -> dict:
        from daggr.node import InteractionNode

        if not session_id:
            session_id = self.state.create_session(self.graph.name)

        ancestors = self._get_ancestors(target_node)
        nodes_to_run = ancestors + [target_node]
        execution_order = self.graph.get_execution_order()
        nodes_to_execute = [n for n in execution_order if n in nodes_to_run]

        entry_inputs: Dict[str, Dict[str, Any]] = {}
        for node_name in nodes_to_execute:
            node = self.graph.nodes[node_name]
            if node._input_components:
                node_inputs = {}
                for port_name in node._input_components:
                    input_node_name = f"{node_name}__{port_name}"
                    input_node_id = input_node_name.replace(" ", "_").replace("-", "_")
                    if input_node_id in input_values:
                        value = input_values[input_node_id].get("value")
                        if value is not None:
                            node_inputs[port_name] = value
                if node_inputs:
                    entry_inputs[node_name] = node_inputs
            elif isinstance(node, InteractionNode):
                value = input_values.get(node_name, "")
                port = node._input_ports[0] if node._input_ports else "input"
                entry_inputs[node_name] = {port: value}

        existing_results = {}
        if session_id:
            for node_name in nodes_to_execute:
                if node_name in selected_results:
                    cached = self.state.get_result_by_index(
                        session_id, node_name, selected_results[node_name]
                    )
                else:
                    cached = self.state.get_latest_result(session_id, node_name)
                if cached is not None:
                    existing_results[node_name] = self._convert_urls_to_file_values(
                        cached
                    )

        self.executor.results = dict(existing_results)

        node_results = {}
        node_statuses = {}

        for node_name in nodes_to_execute:
            if node_name in existing_results:
                node_results[node_name] = existing_results[node_name]
                node_statuses[node_name] = "completed"
                continue

            node_statuses[node_name] = "running"
            user_input = entry_inputs.get(node_name, {})
            result = self.executor.execute_node(node_name, user_input)
            node_results[node_name] = result
            node_statuses[node_name] = "completed"
            self.state.save_result(session_id, node_name, result)

        return self._build_graph_data(
            node_results, node_statuses, input_values, {}, session_id
        )

    async def _execute_to_node_streaming(
        self,
        target_node: str,
        sheet_id: Optional[str],
        input_values: Dict[str, Any],
        item_list_values: Dict[str, Any],
        selected_results: Dict[str, int],
        run_id: str,
        user_id: Optional[str] = None,
    ):
        from daggr.node import InteractionNode

        can_persist = user_id is not None and sheet_id is not None

        ancestors = self._get_ancestors(target_node)
        nodes_to_run = ancestors + [target_node]
        execution_order = self.graph.get_execution_order()
        nodes_to_execute = [n for n in execution_order if n in nodes_to_run]

        entry_inputs: Dict[str, Dict[str, Any]] = {}
        for node_name in nodes_to_execute:
            node = self.graph.nodes[node_name]
            if node._input_components:
                node_inputs = {}
                for port_name in node._input_components:
                    input_node_name = f"{node_name}__{port_name}"
                    input_node_id = input_node_name.replace(" ", "_").replace("-", "_")
                    if input_node_id in input_values:
                        value = input_values[input_node_id].get("value")
                        if value is not None:
                            node_inputs[port_name] = value
                if node_inputs:
                    entry_inputs[node_name] = node_inputs
            elif isinstance(node, InteractionNode):
                value = input_values.get(node_name, "")
                port = node._input_ports[0] if node._input_ports else "input"
                entry_inputs[node_name] = {port: value}

        existing_results = {}
        for node_name in nodes_to_execute:
            node = self.graph.nodes[node_name]
            node_id = node_name.replace(" ", "_").replace("-", "_")
            user_output = self._get_user_provided_output(node, node_id, input_values)
            if user_output is not None:
                existing_results[node_name] = user_output
                if can_persist:
                    self.state.save_result(sheet_id, node_name, user_output)
                continue

            if node_name == target_node:
                continue

            if can_persist:
                if node_name in selected_results:
                    cached = self.state.get_result_by_index(
                        sheet_id, node_name, selected_results[node_name]
                    )
                else:
                    cached = self.state.get_latest_result(sheet_id, node_name)
                if cached is not None:
                    existing_results[node_name] = self._convert_urls_to_file_values(
                        cached
                    )

        self.executor.results = dict(existing_results)

        node_results = {}
        node_statuses = {}

        try:
            for node_name in nodes_to_execute:
                if node_name in existing_results:
                    result = existing_results[node_name]
                    result = self._apply_item_list_edits(
                        node_name, result, item_list_values
                    )
                    node_results[node_name] = result
                    self.executor.results[node_name] = result
                    node_statuses[node_name] = "completed"
                    continue

                node_statuses[node_name] = "running"
                user_input = entry_inputs.get(node_name, {})

                yield {
                    "type": "node_started",
                    "started_node": node_name,
                    "run_id": run_id,
                }

                import time

                start_time = time.time()
                result = await asyncio.to_thread(
                    self.executor.execute_node, node_name, user_input
                )
                elapsed_ms = (time.time() - start_time) * 1000

                result = self._apply_item_list_edits(
                    node_name, result, item_list_values
                )
                self.executor.results[node_name] = result
                node_results[node_name] = result
                node_statuses[node_name] = "completed"

                if can_persist:
                    self.state.save_result(sheet_id, node_name, result)

                graph_data = self._build_graph_data(
                    node_results, node_statuses, input_values, {}, sheet_id
                )
                graph_data["type"] = "node_complete"
                graph_data["completed_node"] = node_name
                graph_data["run_id"] = run_id
                graph_data["execution_time_ms"] = elapsed_ms
                yield graph_data

        except Exception as e:
            if nodes_to_execute:
                current_idx = len(node_results)
                if current_idx < len(nodes_to_execute):
                    current_node = nodes_to_execute[current_idx]
                    node_statuses[current_node] = "error"
                    node_results[current_node] = {"error": str(e)}

            graph_data = self._build_graph_data(
                node_results, node_statuses, input_values, {}, sheet_id
            )
            graph_data["type"] = "error"
            graph_data["run_id"] = run_id
            graph_data["error"] = str(e)
            yield graph_data

    def run(
        self, host: str = "127.0.0.1", port: int = 7860, share: bool = False, **kwargs
    ):
        import secrets
        import threading

        import uvicorn

        self.graph._validate_edges()

        if share:
            server_thread = threading.Thread(
                target=lambda: uvicorn.run(
                    self.app, host=host, port=port, log_level="warning", **kwargs
                ),
                daemon=True,
            )
            server_thread.start()

            import time

            time.sleep(1)

            from gradio.networking import setup_tunnel

            share_token = secrets.token_urlsafe(32)
            share_url = setup_tunnel(
                local_host=host,
                local_port=port,
                share_token=share_token,
                share_server_address=None,
                share_server_tls_certificate=None,
            )
            print(f"\n  daggr running at http://{host}:{port}")
            print(f"  Public URL: {share_url}")
            print(
                "\n  This share link expires in 1 week. For permanent hosting, deploy to Hugging Face Spaces.\n"
            )

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
        else:
            print(f"\n  daggr running at http://{host}:{port}\n")
            uvicorn.run(self.app, host=host, port=port, **kwargs)
