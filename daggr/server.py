from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import socket
from pathlib import Path
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import FastAPI, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from daggr.executor import AsyncExecutor
from daggr.session import ExecutionSession
from daggr.state import SessionState

if TYPE_CHECKING:
    from daggr.graph import Graph


INITIAL_PORT_VALUE = int(os.getenv("DAGGR_SERVER_PORT", "7860"))
TRY_NUM_PORTS = int(os.getenv("DAGGR_NUM_PORTS", "100"))


def _find_available_port(host: str, start_port: int) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + TRY_NUM_PORTS):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host if host != "0.0.0.0" else "127.0.0.1", port))
            s.close()
            return port
        except OSError:
            continue
    raise OSError(
        f"Cannot find empty port in range: {start_port}-{start_port + TRY_NUM_PORTS - 1}. "
        f"You can specify a different port by setting the DAGGR_SERVER_PORT environment variable "
        f"or passing the port parameter to launch()."
    )


class DaggrServer:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.executor = AsyncExecutor(graph)
        self.state = SessionState(db_path=os.environ.get("DAGGR_DB_PATH"))
        self.app = FastAPI(title=graph.name)
        self.connections: dict[str, WebSocket] = {}
        self._setup_routes()

    def _extract_token_from_header(self, authorization: str | None) -> str | None:
        if authorization and authorization.startswith("Bearer "):
            return authorization[7:]
        return None

    def _validate_hf_token(self, token: str) -> dict | None:
        try:
            from huggingface_hub import whoami

            info = whoami(token=token, cache=True)
            return {
                "username": info.get("name"),
                "fullname": info.get("fullname"),
                "avatar_url": info.get("avatarUrl"),
            }
        except Exception:
            return None

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
        async def get_user_info(authorization: str | None = Header(default=None)):
            browser_token = self._extract_token_from_header(authorization)
            if browser_token:
                hf_user = self._validate_hf_token(browser_token)
            else:
                hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            is_on_spaces = os.environ.get("SPACE_ID") is not None
            persistence_enabled = self.graph.persist_key is not None
            return {
                "hf_user": hf_user,
                "user_id": user_id,
                "is_on_spaces": is_on_spaces,
                "can_persist": user_id is not None and persistence_enabled,
            }

        @self.app.post("/api/auth/login")
        async def auth_login(request: Request):
            try:
                body = await request.json()
                token = body.get("token")
                if not token:
                    return JSONResponse({"error": "Token is required"}, status_code=400)
                hf_user = self._validate_hf_token(token)
                if not hf_user:
                    return JSONResponse({"error": "Invalid token"}, status_code=401)
                return {"hf_user": hf_user, "success": True}
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.app.post("/api/auth/logout")
        async def auth_logout():
            return {"success": True}

        @self.app.get("/api/sheets")
        async def list_sheets(authorization: str | None = Header(default=None)):
            if not self.graph.persist_key:
                return {"sheets": [], "user_id": None}
            browser_token = self._extract_token_from_header(authorization)
            if browser_token:
                hf_user = self._validate_hf_token(browser_token)
            else:
                hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            if not user_id:
                return JSONResponse(
                    {"error": "Login required to access sheets on Spaces"},
                    status_code=401,
                )
            sheets = self.state.list_sheets(user_id, self.graph.persist_key)
            return {"sheets": sheets, "user_id": user_id}

        @self.app.post("/api/sheets")
        async def create_sheet(
            request: Request, authorization: str | None = Header(default=None)
        ):
            if not self.graph.persist_key:
                return JSONResponse(
                    {"error": "Persistence is disabled for this graph"},
                    status_code=400,
                )
            browser_token = self._extract_token_from_header(authorization)
            if browser_token:
                hf_user = self._validate_hf_token(browser_token)
            else:
                hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            if not user_id:
                return JSONResponse(
                    {"error": "Login required to create sheets on Spaces"},
                    status_code=401,
                )
            body = await request.json()
            name = body.get("name")
            sheet_id = self.state.create_sheet(user_id, self.graph.persist_key, name)
            sheet = self.state.get_sheet(sheet_id)
            return {"sheet": sheet}

        @self.app.patch("/api/sheets/{sheet_id}")
        async def rename_sheet(
            sheet_id: str,
            request: Request,
            authorization: str | None = Header(default=None),
        ):
            browser_token = self._extract_token_from_header(authorization)
            if browser_token:
                hf_user = self._validate_hf_token(browser_token)
            else:
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
        async def delete_sheet(
            sheet_id: str, authorization: str | None = Header(default=None)
        ):
            browser_token = self._extract_token_from_header(authorization)
            if browser_token:
                hf_user = self._validate_hf_token(browser_token)
            else:
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
        async def get_sheet_state(
            sheet_id: str, authorization: str | None = Header(default=None)
        ):
            browser_token = self._extract_token_from_header(authorization)
            if browser_token:
                hf_user = self._validate_hf_token(browser_token)
            else:
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
            session = ExecutionSession(self.graph)
            session_id = data.get("session_id")
            input_values = data.get("inputs", {})
            selected_results = data.get("selected_results", {})
            return await self._execute_to_node(
                session, node_name, session_id, input_values, selected_results
            )

        @self.app.get("/api/schema")
        async def get_api_schema():
            return self.graph.get_api_schema()

        @self.app.post("/api/call")
        async def call_workflow(request: Request):
            return await self._execute_workflow_api(request, subgraph_id=None)

        @self.app.post("/api/call/{subgraph_id}")
        async def call_subgraph(subgraph_id: str, request: Request):
            return await self._execute_workflow_api(request, subgraph_id=subgraph_id)

        @self.app.websocket("/ws/{session_id}")
        async def websocket_endpoint(websocket: WebSocket, session_id: str):
            await websocket.accept()
            self.connections[session_id] = websocket

            hf_user = self._get_hf_user_info()
            user_id = self.state.get_effective_user_id(hf_user)
            current_sheet_id: str | None = None

            session = ExecutionSession(self.graph)
            running_tasks: set[asyncio.Task] = set()

            async def run_node_execution(
                node_name: str,
                sheet_id: str | None,
                input_values: dict,
                item_list_values: dict,
                selected_results: dict,
                run_id: str,
                user_id: str | None,
            ):
                try:
                    async for result in self._execute_to_node_streaming(
                        session,
                        node_name,
                        sheet_id,
                        input_values,
                        item_list_values,
                        selected_results,
                        run_id,
                        user_id,
                    ):
                        await websocket.send_json(result)
                except Exception as e:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "run_id": run_id,
                            "error": str(e),
                            "node": node_name,
                        }
                    )

            try:
                while True:
                    data = await websocket.receive_json()
                    action = data.get("action")

                    if "hf_token" in data:
                        browser_hf_token = data.get("hf_token")
                        old_user_id = user_id
                        if browser_hf_token:
                            hf_user = self._validate_hf_token(browser_hf_token)
                            user_id = self.state.get_effective_user_id(hf_user)
                            session.set_hf_token(browser_hf_token)
                        else:
                            hf_user = self._get_hf_user_info()
                            user_id = self.state.get_effective_user_id(hf_user)
                            session.set_hf_token(None)
                        if old_user_id != user_id:
                            session.clear_results()
                            current_sheet_id = None

                    if action == "run":
                        node_name = data.get("node_name")
                        input_values = data.get("inputs", {})
                        item_list_values = data.get("item_list_values", {})
                        selected_results = data.get("selected_results", {})
                        run_id = data.get("run_id")
                        sheet_id = data.get("sheet_id") or current_sheet_id

                        task = asyncio.create_task(
                            run_node_execution(
                                node_name,
                                sheet_id,
                                input_values,
                                item_list_values,
                                selected_results,
                                run_id,
                                user_id,
                            )
                        )
                        running_tasks.add(task)
                        task.add_done_callback(running_tasks.discard)

                    elif action == "get_graph":
                        try:
                            sheet_id = data.get("sheet_id")

                            persisted_inputs = {}
                            persisted_results: dict[str, list[Any]] = {}
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
                                    last_entry = results_list[-1]
                                    if (
                                        isinstance(last_entry, dict)
                                        and "result" in last_entry
                                    ):
                                        node_results[node_name] = last_entry["result"]
                                    else:
                                        node_results[node_name] = last_entry

                            graph_data = self._build_graph_data(
                                node_results=node_results,
                                input_values=persisted_inputs,
                            )
                            graph_data["session_id"] = session_id
                            graph_data["sheet_id"] = current_sheet_id
                            graph_data["user_id"] = user_id
                            graph_data["persisted_results"] = (
                                self._transform_persisted_results(persisted_results)
                            )
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
                                session.clear_results()
                                await websocket.send_json(
                                    {"type": "sheet_set", "sheet_id": sheet_id}
                                )

                    elif action == "save_variant_selection":
                        node_id = data.get("node_id")
                        variant_index = data.get("variant_index", 0)
                        if user_id and current_sheet_id and node_id is not None:
                            self.state.save_input(
                                current_sheet_id,
                                node_id,
                                "_selected_variant",
                                variant_index,
                            )
                            await websocket.send_json(
                                {
                                    "type": "variant_selection_saved",
                                    "node_id": node_id,
                                    "variant_index": variant_index,
                                }
                            )

            except WebSocketDisconnect:
                for task in running_tasks:
                    task.cancel()
                if session_id in self.connections:
                    del self.connections[session_id]
            except Exception as e:
                for task in running_tasks:
                    task.cancel()
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

        @self.app.get("/daggr-assets/{path:path}")
        async def serve_daggr_assets(path: str):
            assets_dir = Path(__file__).parent / "assets"
            file_path = assets_dir / path
            if file_path.exists():
                content_type, _ = mimetypes.guess_type(str(file_path))
                return FileResponse(file_path, media_type=content_type)
            return Response(status_code=404)

        @self.app.get("/file/{path:path}")
        async def serve_local_file(path: str):
            import tempfile

            from daggr.state import get_daggr_cache_dir

            if len(path) >= 2 and path[1] == ":":
                file_path = Path(path)
            else:
                file_path = Path("/") / path
            temp_dir = Path(tempfile.gettempdir()).resolve()
            daggr_cache = get_daggr_cache_dir().resolve()

            try:
                resolved = file_path.resolve()
                is_allowed = str(resolved).startswith(str(temp_dir)) or str(
                    resolved
                ).startswith(str(daggr_cache))
                if not is_allowed:
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

    def _get_node_url(self, node) -> str | None:
        from daggr.node import GradioNode, InferenceNode

        if isinstance(node, GradioNode):
            src = node._src
            if src.startswith("http://") or src.startswith("https://"):
                return src
            elif "/" in src:
                return f"https://huggingface.co/spaces/{src}"
        elif isinstance(node, InferenceNode):
            return f"https://huggingface.co/{node._model_name_for_hub}"
        return None

    def _get_node_type(self, node, node_name: str) -> str:
        from daggr.node import ChoiceNode

        type_map = {
            "FnNode": "FN",
            "TextInput": "INPUT",
            "ImageInput": "IMAGE",
            "ChooseOne": "SELECT",
            "Approve": "APPROVE",
            "GradioNode": "GRADIO",
            "InferenceNode": "MODEL",
            "InteractionNode": "ACTION",
            "ChoiceNode": "CHOICE",
        }
        if isinstance(node, ChoiceNode):
            return "CHOICE"
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

    def _is_running_locally(self, node) -> bool:
        from daggr.node import GradioNode

        if not isinstance(node, GradioNode):
            return False
        return bool(node._run_locally and node._local_url and not node._local_failed)

    def _build_variant_data(self, variant, input_values: dict) -> dict[str, Any]:
        from daggr.node import GradioNode

        variant_name = variant._name
        if isinstance(variant, GradioNode):
            variant_name = f"{variant._src}"
            if variant._api_name:
                variant_name += f" ({variant._api_name})"

        input_components = []
        for port_name, comp in variant._input_components.items():
            comp_data = self._serialize_component(comp, port_name)
            input_components.append(comp_data)

        output_components = []
        for port_name, comp in variant._output_components.items():
            if comp is None:
                continue
            visible = getattr(comp, "visible", True)
            if visible is False:
                continue
            comp_data = self._serialize_component(comp, port_name)
            output_components.append(comp_data)

        return {
            "name": variant_name,
            "input_components": input_components,
            "output_components": output_components,
        }

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

    def _serialize_component(self, comp, port_name: str) -> dict[str, Any]:
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
            choices = []
            for c in comp.choices:
                if isinstance(c, (tuple, list)) and len(c) >= 2:
                    choices.append([c[0], c[1]])
                else:
                    choices.append([str(c), c])
            props["choices"] = choices
        if hasattr(comp, "minimum"):
            props["minimum"] = comp.minimum
        if hasattr(comp, "maximum"):
            props["maximum"] = comp.maximum
        if hasattr(comp, "step"):
            props["step"] = comp.step

        return {
            "component": comp_class.lower(),
            "type": comp_type,
            "port_name": port_name,
            "props": props,
            "value": getattr(comp, "value", None),
        }

    def _file_to_url(self, value: Any) -> Any:
        if isinstance(value, str) and not value.startswith("/file/"):
            path = Path(value)
            if path.is_absolute() and path.exists():
                normalized = value.replace("\\", "/")
                if normalized.startswith("/"):
                    return f"/file{normalized}"
                return f"/file/{normalized}"
        return value

    def _validate_file_value(self, value: Any, comp_type: str) -> str | None:
        """Validate that a value is appropriate for a file-type component.
        Returns an error message if invalid, None if valid."""
        if value is None:
            return None
        if isinstance(value, str):
            return None
        if isinstance(value, dict):
            if "url" in value or "path" in value:
                return None
            keys = list(value.keys())
            if keys:
                return (
                    f"Expected a file path string for {comp_type}, but got a dict "
                    f"with keys {keys}. If using postprocess, extract the path: "
                    f"e.g., `postprocess=lambda x: x['{keys[0]}']`"
                )
            return (
                f"Expected a file path string for {comp_type}, but got an empty dict."
            )
        return f"Expected a file path string for {comp_type}, but got {type(value).__name__}."

    def _process_audio_value(self, value: Any) -> Any:
        if isinstance(value, tuple) and len(value) == 2:
            sample_rate, audio_data = value
            if isinstance(sample_rate, int) and hasattr(audio_data, "shape"):
                import hashlib
                import wave

                import numpy as np

                from daggr.state import get_daggr_files_dir

                audio_array = np.array(audio_data)
                if audio_array.dtype in (np.float32, np.float64):
                    audio_array = (audio_array * 32767).astype(np.int16)
                elif audio_array.dtype != np.int16:
                    audio_array = audio_array.astype(np.int16)

                audio_hash = hashlib.md5(audio_array.tobytes()[:1024]).hexdigest()[:12]
                filename = f"audio_{audio_hash}.wav"
                files_dir = get_daggr_files_dir()
                file_path = files_dir / filename

                if not file_path.exists():
                    n_channels = (
                        1 if len(audio_array.shape) == 1 else audio_array.shape[1]
                    )
                    if len(audio_array.shape) > 1:
                        audio_array = audio_array.flatten()
                    with wave.open(str(file_path), "w") as wav_file:
                        wav_file.setnchannels(n_channels)
                        wav_file.setsampwidth(2)
                        wav_file.setframerate(sample_rate)
                        wav_file.writeframes(audio_array.tobytes())

                return self._file_to_url(str(file_path))
        return self._file_to_url(value)

    def _transform_file_paths(self, data: Any) -> Any:
        if isinstance(data, str):
            return self._file_to_url(data)
        elif isinstance(data, dict):
            return {k: self._transform_file_paths(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._transform_file_paths(item) for item in data]
        return data

    def _transform_persisted_results(
        self, persisted_results: dict[str, list[Any]]
    ) -> dict[str, list[Any]]:
        """Transform persisted results, handling both old format (just result)
        and new format (dict with result and inputs_snapshot)."""
        transformed: dict[str, list[Any]] = {}
        for node_name, results_list in persisted_results.items():
            transformed[node_name] = []
            for entry in results_list:
                if isinstance(entry, dict) and "result" in entry:
                    transformed[node_name].append(
                        {
                            "result": self._transform_file_paths(entry["result"]),
                            "inputs_snapshot": entry.get("inputs_snapshot"),
                        }
                    )
                else:
                    transformed[node_name].append(self._transform_file_paths(entry))
        return transformed

    def _build_input_components(self, node) -> list[dict[str, Any]]:
        if not node._input_components:
            return []
        return [
            self._serialize_component(comp, port_name)
            for port_name, comp in node._input_components.items()
        ]

    def _build_output_components(
        self, node, result: Any = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        if not node._output_components:
            return [], None

        components = []
        validation_error = None
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
                    value = self._process_audio_value(value)
                elif comp_type in ("image", "video", "file", "model3d"):
                    error = self._validate_file_value(value, comp_type)
                    if error and validation_error is None:
                        validation_error = error
                    value = self._file_to_url(value)
                comp_data["value"] = value
            components.append(comp_data)
        return components, validation_error

    def _build_scattered_items(
        self, node_name: str, result: Any = None
    ) -> list[dict[str, Any]]:
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
                    output = self._process_audio_value(output)
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
        self, schema: dict[str, Any]
    ) -> list[dict[str, Any]]:
        serialized = []
        for field_name, comp in schema.items():
            comp_data = self._serialize_component(comp, field_name)
            serialized.append(comp_data)
        return serialized

    def _build_item_list_items(
        self, node, port_name: str, result: Any = None
    ) -> list[dict[str, Any]]:
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
        self, node_name: str, result: Any, item_list_values: dict
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

    def _compute_node_depths(self) -> dict[str, int]:
        depths: dict[str, int] = {}
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

    def _get_hf_user_info(self) -> dict | None:
        try:
            from huggingface_hub import get_token, whoami

            token = get_token()
            if not token:
                return None

            info = whoami(cache=True)
            return {
                "username": info.get("name"),
                "fullname": info.get("fullname"),
                "avatar_url": info.get("avatarUrl"),
            }
        except Exception:
            return None

    def _build_graph_data(
        self,
        node_results: dict[str, Any] | None = None,
        node_statuses: dict[str, str] | None = None,
        input_values: dict[str, Any] | None = None,
        history: dict[str, dict[str, list[dict]]] | None = None,
        session_id: str | None = None,
        selected_results: dict[str, int] | None = None,
    ) -> dict:
        node_results = node_results or {}
        node_statuses = node_statuses or {}
        input_values = input_values or {}
        history = history or {}
        selected_results = selected_results or {}

        depths = self._compute_node_depths()

        synthetic_input_nodes: list[dict[str, Any]] = []
        synthetic_edges: list[dict[str, Any]] = []
        input_node_positions: dict[str, tuple] = {}

        component_to_input_node: dict[int, str] = {}
        creation_order = 0
        for node_name in self.graph.nodes:
            from daggr.node import ChoiceNode

            node = self.graph.nodes[node_name]

            if isinstance(node, ChoiceNode):
                continue

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

        nodes_by_depth: dict[int, list[str]] = {}
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

        def calc_component_height(comp_data: dict) -> int:
            lines = comp_data.get("props", {}).get("lines", 1)
            lines = min(lines, 6)
            return component_base_height + max(0, lines - 1) * line_height

        def calc_node_height(components: list[dict], num_ports: int = 1) -> int:
            comp_height = sum(calc_component_height(c) for c in components)
            port_height = max(num_ports, 1) * 22
            return base_node_height + port_height + comp_height

        all_input_nodes_sorted: list[dict] = []
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

        node_positions: dict[str, tuple] = {}
        for depth in range(max_depth + 1):
            depth_nodes = nodes_by_depth.get(depth, [])
            current_y = y_start
            for node_name in depth_nodes:
                node = self.graph.nodes[node_name]
                output_comps, _ = self._build_output_components(node)
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
            from daggr.node import ChoiceNode

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

            output_components, validation_error = self._build_output_components(
                node, result
            )
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
            is_local = self._is_running_locally(node)

            variants = None
            selected_variant = None
            if isinstance(node, ChoiceNode):
                variants = [
                    self._build_variant_data(v, input_values) for v in node._variants
                ]
                selected_variant = input_values.get(node_id, {}).get(
                    "_selected_variant", 0
                )

            nodes.append(
                {
                    "id": node_id,
                    "name": node_name,
                    "type": self._get_node_type(node, node_name),
                    "url": self._get_node_url(node),
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
                    "is_local": is_local,
                    "variants": variants,
                    "selected_variant": selected_variant,
                    "validation_error": validation_error,
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
            "selected_results": selected_results,
            "history": history,
            "session_id": session_id,
        }

    def _get_ancestors(self, node_name: str) -> list[str]:
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
        self, node, node_id: str, input_values: dict[str, Any]
    ) -> dict[str, Any] | None:
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

    async def _execute_to_node(
        self,
        session: ExecutionSession,
        target_node: str,
        session_id: str | None,
        input_values: dict[str, Any],
        selected_results: dict[str, int],
    ) -> dict:
        from daggr.node import ChoiceNode, InteractionNode

        if not session_id:
            session_id = self.state.create_session(self.graph.persist_key)

        for node_name, node in self.graph.nodes.items():
            if isinstance(node, ChoiceNode):
                node_id = node_name.replace(" ", "_").replace("-", "_")
                variant_idx = input_values.get(node_id, {}).get("_selected_variant", 0)
                session.selected_variants[node_name] = variant_idx

        ancestors = self._get_ancestors(target_node)
        nodes_to_run = ancestors + [target_node]
        execution_order = self.graph.get_execution_order()
        nodes_to_execute = [n for n in execution_order if n in nodes_to_run]

        entry_inputs: dict[str, dict[str, Any]] = {}
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

        for k, v in existing_results.items():
            if k not in session.results:
                session.results[k] = v

        if target_node in session.results:
            del session.results[target_node]

        node_results = {}
        node_statuses = {}

        for node_name in nodes_to_execute:
            if node_name in existing_results:
                node_results[node_name] = existing_results[node_name]
                node_statuses[node_name] = "completed"
                continue

            if node_name in session.results:
                node_results[node_name] = session.results[node_name]
                node_statuses[node_name] = "completed"
                continue

            node_statuses[node_name] = "running"
            user_input = entry_inputs.get(node_name, {})
            result = await self.executor.execute_node(session, node_name, user_input)
            node_results[node_name] = result
            node_statuses[node_name] = "completed"
            self.state.save_result(session_id, node_name, result)

        return self._build_graph_data(
            node_results, node_statuses, input_values, {}, session_id, selected_results
        )

    async def _execute_to_node_streaming(
        self,
        session: ExecutionSession,
        target_node: str,
        sheet_id: str | None,
        input_values: dict[str, Any],
        item_list_values: dict[str, Any],
        selected_results: dict[str, int],
        run_id: str,
        user_id: str | None = None,
    ):
        from daggr.node import ChoiceNode, InteractionNode

        can_persist = (
            user_id is not None
            and sheet_id is not None
            and self.graph.persist_key is not None
        )

        for node_name, node in self.graph.nodes.items():
            if isinstance(node, ChoiceNode):
                node_id = node_name.replace(" ", "_").replace("-", "_")
                variant_idx = input_values.get(node_id, {}).get("_selected_variant", 0)
                session.selected_variants[node_name] = variant_idx

        ancestors = self._get_ancestors(target_node)
        nodes_to_run = ancestors + [target_node]
        execution_order = self.graph.get_execution_order()
        nodes_to_execute = [n for n in execution_order if n in nodes_to_run]

        entry_inputs: dict[str, dict[str, Any]] = {}
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
                    snapshot = {
                        "inputs": input_values,
                        "selected_results": selected_results,
                    }
                    self.state.save_result(sheet_id, node_name, user_output, snapshot)
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

        for k, v in existing_results.items():
            if k not in session.results:
                session.results[k] = v

        if target_node in session.results:
            del session.results[target_node]

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
                    session.results[node_name] = result
                    node_statuses[node_name] = "completed"
                    continue

                if node_name in session.results:
                    result = session.results[node_name]
                    result = self._apply_item_list_edits(
                        node_name, result, item_list_values
                    )
                    node_results[node_name] = result
                    node_statuses[node_name] = "completed"
                    continue

                can_execute = await session.start_node_execution(node_name)
                if not can_execute:
                    if node_name == target_node:
                        return
                    await session.wait_for_node(node_name)
                    if node_name in session.results:
                        result = session.results[node_name]
                        result = self._apply_item_list_edits(
                            node_name, result, item_list_values
                        )
                        node_results[node_name] = result
                        node_statuses[node_name] = "completed"
                        continue

                try:
                    node_statuses[node_name] = "running"
                    user_input = entry_inputs.get(node_name, {})

                    yield {
                        "type": "node_started",
                        "started_node": node_name,
                        "run_id": run_id,
                    }

                    import time

                    start_time = time.time()
                    result = await self.executor.execute_node(
                        session, node_name, user_input
                    )
                    elapsed_ms = (time.time() - start_time) * 1000

                    result = self._apply_item_list_edits(
                        node_name, result, item_list_values
                    )
                    session.results[node_name] = result
                    node_results[node_name] = result
                    node_statuses[node_name] = "completed"

                    if can_persist:
                        current_count = self.state.get_result_count(sheet_id, node_name)
                        snapshot = {
                            "inputs": input_values,
                            "selected_results": selected_results,
                        }
                        self.state.save_result(sheet_id, node_name, result, snapshot)
                        selected_results[node_name] = current_count

                    graph_data = self._build_graph_data(
                        node_results,
                        node_statuses,
                        input_values,
                        {},
                        sheet_id,
                        selected_results,
                    )
                    graph_data["type"] = "node_complete"
                    graph_data["completed_node"] = node_name
                    graph_data["run_id"] = run_id
                    graph_data["execution_time_ms"] = elapsed_ms
                finally:
                    await session.finish_node_execution(node_name)
                yield graph_data

        except Exception as e:
            error_node = None
            if nodes_to_execute:
                current_idx = len(node_results)
                if current_idx < len(nodes_to_execute):
                    error_node = nodes_to_execute[current_idx]
                    node_statuses[error_node] = "error"
                    node_results[error_node] = {"error": str(e)}

            graph_data = self._build_graph_data(
                node_results,
                node_statuses,
                input_values,
                {},
                sheet_id,
                selected_results,
            )
            graph_data["type"] = "error"
            graph_data["run_id"] = run_id
            graph_data["error"] = str(e)
            graph_data["nodes_to_clear"] = nodes_to_execute
            if error_node:
                graph_data["node"] = error_node
                graph_data["completed_node"] = error_node
            yield graph_data

    async def _execute_workflow_api(
        self, request: Request, subgraph_id: str | None = None
    ) -> JSONResponse:
        from daggr.node import ChoiceNode

        try:
            body = await request.json()
        except Exception:
            body = {}

        input_values = body.get("inputs", {})
        session = ExecutionSession(self.graph)

        subgraphs = self.graph.get_subgraphs()
        output_node_names = set(self.graph.get_output_nodes())

        if subgraph_id is None:
            if len(subgraphs) > 1:
                return JSONResponse(
                    {
                        "error": "Multiple subgraphs detected. Please specify a subgraph_id.",
                        "available_subgraphs": [
                            f"subgraph_{i}" for i in range(len(subgraphs))
                        ],
                    },
                    status_code=400,
                )
            target_nodes = subgraphs[0] if subgraphs else set(self.graph.nodes.keys())
        else:
            if subgraph_id == "main" and len(subgraphs) == 1:
                target_nodes = subgraphs[0]
            elif subgraph_id.startswith("subgraph_"):
                try:
                    idx = int(subgraph_id.split("_")[1])
                    if idx < 0 or idx >= len(subgraphs):
                        return JSONResponse(
                            {"error": f"Subgraph '{subgraph_id}' not found"},
                            status_code=404,
                        )
                    target_nodes = subgraphs[idx]
                except (ValueError, IndexError):
                    return JSONResponse(
                        {"error": f"Invalid subgraph_id '{subgraph_id}'"},
                        status_code=400,
                    )
            else:
                return JSONResponse(
                    {"error": f"Subgraph '{subgraph_id}' not found"},
                    status_code=404,
                )

        for node_name, node in self.graph.nodes.items():
            if isinstance(node, ChoiceNode):
                node_id = node_name.replace(" ", "_").replace("-", "_")
                variant_idx = input_values.get(f"{node_id}___selected_variant", 0)
                session.selected_variants[node_name] = variant_idx

        execution_order = self.graph.get_execution_order()
        nodes_to_execute = [n for n in execution_order if n in target_nodes]

        entry_inputs: dict[str, dict[str, Any]] = {}
        for node_name in nodes_to_execute:
            node = self.graph.nodes[node_name]
            if node._input_components:
                node_inputs = {}
                for port_name in node._input_components:
                    input_node_id = f"{node_name}__{port_name}".replace(
                        " ", "_"
                    ).replace("-", "_")
                    if input_node_id in input_values:
                        node_inputs[port_name] = input_values[input_node_id]
                if node_inputs:
                    entry_inputs[node_name] = node_inputs

        session.results = {}
        node_results = {}

        try:
            for node_name in nodes_to_execute:
                user_input = entry_inputs.get(node_name, {})
                result = await self.executor.execute_node(
                    session, node_name, user_input
                )
                node_results[node_name] = result
        except Exception as e:
            return JSONResponse(
                {"error": f"Execution error in node '{node_name}': {str(e)}"},
                status_code=500,
            )

        outputs = {}
        for node_name in nodes_to_execute:
            if node_name in output_node_names and node_name in node_results:
                result = node_results[node_name]
                result = self._transform_file_paths(result)
                outputs[node_name] = result

        return JSONResponse({"outputs": outputs})

    def run(
        self,
        host: str | None = None,
        port: int | None = None,
        share: bool | None = None,
        open_browser: bool = True,
        **kwargs,
    ):
        import secrets
        import time
        import webbrowser

        import uvicorn
        from gradio.utils import colab_check, ipython_check

        if host is None:
            host = os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1")
        if port is None:
            port = int(os.environ.get("GRADIO_SERVER_PORT", "7860"))

        actual_port = _find_available_port(host, port)
        if actual_port != port:
            print(f"\n  Port {port} is in use, using {actual_port} instead.")

        self.graph._validate_edges()

        is_colab = colab_check()
        is_kaggle = os.environ.get("KAGGLE_KERNEL_RUN_TYPE") is not None
        is_notebook = is_colab or is_kaggle or ipython_check()

        if share is None:
            share = is_colab or is_kaggle

        if is_notebook or share:
            config = uvicorn.Config(
                app=self.app,
                host=host,
                port=actual_port,
                log_level="warning",
            )
            server = _Server(config)
            server.run_in_thread()

            local_url = f"http://{host}:{actual_port}"
            print(f"\n  daggr running at {local_url}")

            share_url = None
            if share:
                from gradio.networking import setup_tunnel

                share_token = secrets.token_urlsafe(32)
                share_url = setup_tunnel(
                    local_host=host,
                    local_port=actual_port,
                    share_token=share_token,
                    share_server_address=None,
                    share_server_tls_certificate=None,
                )
                print(f"  Public URL: {share_url}")
                print(
                    "\n  This share link expires in 1 week. For permanent hosting, deploy to Hugging Face Spaces.\n"
                )

            if is_colab or is_kaggle:
                from IPython.display import HTML, display

                url = share_url or local_url
                display(
                    HTML(f'<a href="{url}" target="_blank">Open daggr app: {url}</a>')
                )
            elif open_browser:
                webbrowser.open_new_tab(share_url or local_url)

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
                server.close()
        else:
            local_url = f"http://{host}:{actual_port}"
            print(f"\n  daggr running at {local_url}\n")
            if open_browser:
                import threading

                threading.Timer(0.5, lambda: webbrowser.open_new_tab(local_url)).start()
            uvicorn.run(self.app, host=host, port=actual_port, **kwargs)


class _Server(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    def run_in_thread(self):
        import threading
        import time

        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        start = time.time()
        while not self.started:
            time.sleep(1e-3)
            if time.time() - start > 5:
                raise RuntimeError(
                    "Server failed to start. Please check that the port is available."
                )

    def close(self):
        self.should_exit = True
        self.thread.join(timeout=5)
