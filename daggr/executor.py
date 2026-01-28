"""Executor for daggr graphs.

This module provides the AsyncExecutor for running graph nodes with proper
concurrency control and session isolation.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from daggr.graph import Graph
    from daggr.session import ExecutionSession


class FileValue(str):
    """A string subclass that marks a value as a file URL/path from Gradio output."""

    pass


def _download_file(url: str) -> str:
    import hashlib
    from pathlib import Path
    from urllib.parse import urlparse

    import httpx

    from daggr.state import get_daggr_files_dir

    parsed = urlparse(url)
    ext = Path(parsed.path).suffix or ".bin"
    url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
    filename = f"{url_hash}{ext}"

    files_dir = get_daggr_files_dir()
    local_path = files_dir / filename

    if not local_path.exists():
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            local_path.write_bytes(response.content)

    return str(local_path)


def _postprocess_inference_result(task: str | None, result: Any) -> Any:
    """Unwrap HF Inference Client result objects to get the actual data."""
    import uuid

    from daggr.state import get_daggr_files_dir

    if result is None:
        return None

    if task == "automatic-speech-recognition":
        return getattr(result, "text", result)
    elif task == "translation":
        return getattr(result, "translation_text", result)
    elif task == "summarization":
        return getattr(result, "summary_text", result)
    elif task in (
        "audio-classification",
        "image-classification",
        "text-classification",
    ):
        if isinstance(result, list) and result:
            return {item.label: item.score for item in result if hasattr(item, "label")}
        return result
    elif task == "image-to-text":
        return getattr(result, "generated_text", result)
    elif task == "question-answering":
        if hasattr(result, "answer"):
            return result.answer
        return result
    elif task in ("text-to-speech", "text-to-audio"):
        if isinstance(result, bytes):
            file_path = get_daggr_files_dir() / f"{uuid.uuid4()}.wav"
            file_path.write_bytes(result)
            return str(file_path)
        return result
    elif task in ("text-to-image", "image-to-image"):
        if isinstance(result, dict):
            if "images" in result:
                result = result["images"][0] if result["images"] else result
            elif "image" in result:
                result = result["image"]
        if hasattr(result, "save"):
            file_path = get_daggr_files_dir() / f"{uuid.uuid4()}.png"
            result.save(file_path)
            return str(file_path)
        return result

    return result


def _call_inference_task(client: Any, task: str | None, inputs: dict[str, Any]) -> Any:
    primary_input = None
    if task in (
        "image-to-image",
        "image-classification",
        "image-to-text",
        "object-detection",
        "image-segmentation",
        "visual-question-answering",
        "document-question-answering",
    ):
        primary_input = inputs.get("image")
    elif task in (
        "automatic-speech-recognition",
        "audio-classification",
        "audio-to-audio",
    ):
        primary_input = inputs.get("audio")

    if primary_input is None:
        primary_input = next(iter(inputs.values()), None) if inputs else None

    if primary_input is None:
        return None

    task_method_map = {
        "text-generation": "text_generation",
        "text2text-generation": "text_generation",
        "text-to-image": "text_to_image",
        "image-to-image": "image_to_image",
        "image-to-text": "image_to_text",
        "image-to-video": "image_to_video",
        "text-to-video": "text_to_video",
        "text-to-speech": "text_to_speech",
        "text-to-audio": "text_to_audio",
        "automatic-speech-recognition": "automatic_speech_recognition",
        "audio-to-audio": "audio_to_audio",
        "audio-classification": "audio_classification",
        "image-classification": "image_classification",
        "object-detection": "object_detection",
        "image-segmentation": "image_segmentation",
        "translation": "translation",
        "summarization": "summarization",
        "feature-extraction": "feature_extraction",
        "fill-mask": "fill_mask",
        "question-answering": "question_answering",
        "table-question-answering": "table_question_answering",
        "sentence-similarity": "sentence_similarity",
        "zero-shot-classification": "zero_shot_classification",
        "zero-shot-image-classification": "zero_shot_image_classification",
        "document-question-answering": "document_question_answering",
        "visual-question-answering": "visual_question_answering",
    }

    method_name = (
        task_method_map.get(task, "text_generation") if task else "text_generation"
    )
    method = getattr(client, method_name, None)

    file_input_tasks = {
        "image-to-image",
        "image-classification",
        "image-to-text",
        "object-detection",
        "image-segmentation",
        "visual-question-answering",
        "document-question-answering",
        "automatic-speech-recognition",
        "audio-classification",
        "audio-to-audio",
    }

    if task in file_input_tasks and isinstance(primary_input, str):
        primary_input = _read_file_as_bytes(primary_input)

    try:
        if method is None:
            result = client.text_generation(primary_input)
        elif task in ("image-to-image",):
            prompt = inputs.get("prompt", "")
            result = method(primary_input, prompt=prompt)
        elif task in ("visual-question-answering", "document-question-answering"):
            question = inputs.get("question", inputs.get("prompt", ""))
            result = method(primary_input, question=question)
        else:
            result = method(primary_input)
    except KeyError as e:
        raise RuntimeError(
            f"Provider returned unexpected response format for task '{task}'. "
            f"Missing key: {e}. This model may require a specific provider "
            f"(e.g., 'model_name:fal-ai' or 'model_name:replicate')."
        ) from e

    return _postprocess_inference_result(task, result)


def _read_file_as_bytes(file_path: str) -> bytes:
    """Read a file path or data URL as bytes."""
    import base64
    from pathlib import Path

    if file_path.startswith("data:"):
        try:
            _, encoded = file_path.split(",", 1)
            return base64.b64decode(encoded)
        except Exception:
            pass

    path = Path(file_path)
    if path.exists():
        return path.read_bytes()

    return file_path


class AsyncExecutor:
    """Async executor for graph nodes.
    
    This executor is stateless - all state is held in the ExecutionSession.
    It handles concurrency control:
    - GradioNode/InferenceNode: run concurrently (external API calls)
    - FnNode: sequential by default, configurable via concurrent/concurrency_group
    """

    def __init__(self, graph: Graph):
        self.graph = graph

    def _get_client_for_gradio_node(
        self, session: ExecutionSession, gradio_node, cache_key: str
    ):
        from daggr import _client_cache

        token_cache_key = f"{cache_key}__token_{hash(session.hf_token or '')}"
        if token_cache_key in session.clients:
            return session.clients[token_cache_key]

        if gradio_node._run_locally:
            from daggr.local_space import get_local_client

            client = get_local_client(gradio_node)
            if client is not None:
                session.clients[token_cache_key] = client
                return client

        if session.hf_token:
            from gradio_client import Client

            client = Client(
                gradio_node._src,
                download_files=False,
                verbose=False,
                hf_token=session.hf_token,
            )
        else:
            client = _client_cache.get_client(gradio_node._src)
            if client is None:
                from gradio_client import Client

                client = Client(
                    gradio_node._src,
                    download_files=False,
                    verbose=False,
                )
                _client_cache.set_client(gradio_node._src, client)

        session.clients[token_cache_key] = client
        return client

    def _get_client(self, session: ExecutionSession, node_name: str):
        from daggr.node import ChoiceNode, GradioNode

        node = self.graph.nodes[node_name]

        if isinstance(node, ChoiceNode):
            variant_idx = session.selected_variants.get(node_name, 0)
            variant = node._variants[variant_idx]
            if isinstance(variant, GradioNode):
                cache_key = f"{node_name}__variant_{variant_idx}"
                return self._get_client_for_gradio_node(session, variant, cache_key)
            return None

        if not isinstance(node, GradioNode):
            return None

        return self._get_client_for_gradio_node(session, node, node_name)

    def _get_scattered_input_edges(self, node_name: str) -> list:
        scattered = []
        for edge in self.graph._edges:
            if edge.target_node._name == node_name and edge.is_scattered:
                scattered.append(edge)
        return scattered

    def _get_gathered_input_edges(self, node_name: str) -> list:
        gathered = []
        for edge in self.graph._edges:
            if edge.target_node._name == node_name and edge.is_gathered:
                gathered.append(edge)
        return gathered

    def _prepare_inputs(
        self, session: ExecutionSession, node_name: str, skip_scattered: bool = False
    ) -> dict[str, Any]:
        inputs = {}

        for edge in self.graph._edges:
            if edge.target_node._name == node_name:
                if skip_scattered and edge.is_scattered:
                    continue

                source_name = edge.source_node._name
                source_output = edge.source_port
                target_input = edge.target_port

                if source_name in session.results:
                    source_result = session.results[source_name]

                    if (
                        edge.is_gathered
                        and isinstance(source_result, dict)
                        and "_scattered_results" in source_result
                    ):
                        scattered_results = source_result["_scattered_results"]
                        extracted = []
                        for item_result in scattered_results:
                            if (
                                isinstance(item_result, dict)
                                and source_output in item_result
                            ):
                                extracted.append(item_result[source_output])
                            else:
                                extracted.append(item_result)
                        inputs[target_input] = extracted
                    elif (
                        isinstance(source_result, dict)
                        and source_output in source_result
                    ):
                        inputs[target_input] = source_result[source_output]
                    elif isinstance(source_result, (list, tuple)):
                        try:
                            output_idx = int(
                                source_output.replace("output_", "").replace(
                                    "output", "0"
                                )
                            )
                            if 0 <= output_idx < len(source_result):
                                inputs[target_input] = source_result[output_idx]
                        except (ValueError, TypeError):
                            if len(source_result) > 0:
                                inputs[target_input] = source_result[0]
                    else:
                        inputs[target_input] = source_result

        return inputs

    def _execute_single_node_sync(
        self, session: ExecutionSession, node_name: str, inputs: dict[str, Any]
    ) -> Any:
        """Synchronous node execution (called from thread pool for FnNode)."""
        from daggr.node import (
            ChoiceNode,
            FnNode,
            GradioNode,
            InferenceNode,
            InteractionNode,
        )

        node = self.graph.nodes[node_name]

        if isinstance(node, ChoiceNode):
            variant_idx = session.selected_variants.get(node_name, 0)
            variant = node._variants[variant_idx]
            return self._execute_variant_node_sync(session, node_name, variant, inputs)

        all_inputs = {}
        for port_name, value in node._fixed_inputs.items():
            all_inputs[port_name] = value() if callable(value) else value
        for port_name, component in node._input_components.items():
            if hasattr(component, "value") and component.value is not None:
                all_inputs[port_name] = component.value
        all_inputs.update(inputs)

        if isinstance(node, GradioNode):
            client = self._get_client(session, node_name)
            if client:
                api_name = node._api_name or "/predict"
                if not api_name.startswith("/"):
                    api_name = "/" + api_name
                call_inputs = {
                    k: self._wrap_file_input(v)
                    for k, v in all_inputs.items()
                    if k in node._input_ports
                }
                if node._preprocess:
                    call_inputs = node._preprocess(call_inputs)
                raw_result = client.predict(api_name=api_name, **call_inputs)
                if node._postprocess:
                    raw_result = self._apply_postprocess(node._postprocess, raw_result)
                result = self._map_gradio_result(node, raw_result)
            else:
                result = None

        elif isinstance(node, FnNode):
            fn_kwargs = {}
            for port_name in node._input_ports:
                if port_name in all_inputs:
                    fn_kwargs[port_name] = all_inputs[port_name]
            if node._preprocess:
                fn_kwargs = node._preprocess(fn_kwargs)
            raw_result = node._fn(**fn_kwargs)
            if node._postprocess:
                raw_result = self._apply_postprocess(node._postprocess, raw_result)
            result = self._map_fn_result(node, raw_result)

        elif isinstance(node, InferenceNode):
            from huggingface_hub import InferenceClient

            if not node._task_fetched:
                node._fetch_model_info()
            client = InferenceClient(
                model=node._model_name_for_hub,
                provider=node._provider,
                token=session.hf_token,
            )
            inference_inputs = {
                k: v for k, v in all_inputs.items() if k in node._input_ports
            }
            raw_result = _call_inference_task(client, node._task, inference_inputs)
            result = self._map_inference_result(node, raw_result)

        elif isinstance(node, InteractionNode):
            result = all_inputs.get(
                "input",
                all_inputs.get(node._input_ports[0]) if node._input_ports else None,
            )

        else:
            result = None

        return result

    def _execute_variant_node_sync(
        self,
        session: ExecutionSession,
        node_name: str,
        variant,
        inputs: dict[str, Any],
    ) -> Any:
        from daggr.node import FnNode, GradioNode, InferenceNode

        all_inputs = {}
        for port_name, value in variant._fixed_inputs.items():
            all_inputs[port_name] = value() if callable(value) else value
        for port_name, component in variant._input_components.items():
            if hasattr(component, "value") and component.value is not None:
                all_inputs[port_name] = component.value
        all_inputs.update(inputs)

        if isinstance(variant, GradioNode):
            client = self._get_client(session, node_name)
            if client:
                api_name = variant._api_name or "/predict"
                if not api_name.startswith("/"):
                    api_name = "/" + api_name
                call_inputs = {
                    k: self._wrap_file_input(v)
                    for k, v in all_inputs.items()
                    if k in variant._input_ports
                }
                if variant._preprocess:
                    call_inputs = variant._preprocess(call_inputs)
                raw_result = client.predict(api_name=api_name, **call_inputs)
                if variant._postprocess:
                    raw_result = self._apply_postprocess(
                        variant._postprocess, raw_result
                    )
                result = self._map_gradio_result(variant, raw_result)
            else:
                result = None

        elif isinstance(variant, FnNode):
            fn_kwargs = {}
            for port_name in variant._input_ports:
                if port_name in all_inputs:
                    fn_kwargs[port_name] = all_inputs[port_name]
            if variant._preprocess:
                fn_kwargs = variant._preprocess(fn_kwargs)
            raw_result = variant._fn(**fn_kwargs)
            if variant._postprocess:
                raw_result = self._apply_postprocess(variant._postprocess, raw_result)
            result = self._map_fn_result(variant, raw_result)

        elif isinstance(variant, InferenceNode):
            from huggingface_hub import InferenceClient

            if not variant._task_fetched:
                variant._fetch_model_info()
            client = InferenceClient(
                model=variant._model_name_for_hub,
                provider=variant._provider,
                token=session.hf_token,
            )
            inference_inputs = {
                k: v for k, v in all_inputs.items() if k in variant._input_ports
            }
            raw_result = _call_inference_task(client, variant._task, inference_inputs)
            result = self._map_inference_result(variant, raw_result)

        else:
            result = None

        return result

    async def execute_node(
        self,
        session: ExecutionSession,
        node_name: str,
        user_inputs: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a single node with proper concurrency control."""
        from daggr.node import FnNode, GradioNode, InferenceNode

        node = self.graph.nodes[node_name]
        scattered_edges = self._get_scattered_input_edges(node_name)

        if scattered_edges:
            result = await self._execute_scattered_node(
                session, node_name, scattered_edges, user_inputs
            )
        else:
            inputs = self._prepare_inputs(session, node_name)
            if user_inputs:
                if isinstance(user_inputs, dict):
                    inputs.update(user_inputs)
                else:
                    if node._input_ports:
                        inputs[node._input_ports[0]] = user_inputs
                    else:
                        inputs["input"] = user_inputs

            try:
                if isinstance(node, (GradioNode, InferenceNode)):
                    result = await asyncio.to_thread(
                        self._execute_single_node_sync, session, node_name, inputs
                    )
                elif isinstance(node, FnNode):
                    semaphore = await session.concurrency.get_semaphore(
                        node._concurrent,
                        node._concurrency_group,
                        node._max_concurrent,
                    )
                    if semaphore:
                        async with semaphore:
                            result = await asyncio.to_thread(
                                self._execute_single_node_sync,
                                session,
                                node_name,
                                inputs,
                            )
                    else:
                        result = await asyncio.to_thread(
                            self._execute_single_node_sync, session, node_name, inputs
                        )
                else:
                    result = await asyncio.to_thread(
                        self._execute_single_node_sync, session, node_name, inputs
                    )
            except Exception as e:
                raise RuntimeError(f"Error executing node '{node_name}': {e}")

        session.results[node_name] = result
        return result

    async def _execute_scattered_node(
        self,
        session: ExecutionSession,
        node_name: str,
        scattered_edges: list,
        user_inputs: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]:
        from daggr.node import FnNode, GradioNode, InferenceNode

        first_edge = scattered_edges[0]
        source_name = first_edge.source_node._name
        source_port = first_edge.source_port

        source_result = session.results.get(source_name)
        if source_result is None:
            items = []
        elif isinstance(source_result, dict) and source_port in source_result:
            items = source_result[source_port]
        else:
            items = source_result

        if not isinstance(items, list):
            items = [items]

        context_inputs = self._prepare_inputs(session, node_name, skip_scattered=True)
        if user_inputs:
            context_inputs.update(user_inputs)

        node = self.graph.nodes[node_name]

        async def execute_item(item, idx):
            item_inputs = dict(context_inputs)
            for edge in scattered_edges:
                target_port = edge.target_port
                item_key = edge.item_key
                if item_key and isinstance(item, dict):
                    item_inputs[target_port] = item.get(item_key)
                else:
                    item_inputs[target_port] = item

            try:
                if isinstance(node, (GradioNode, InferenceNode)):
                    return await asyncio.to_thread(
                        self._execute_single_node_sync, session, node_name, item_inputs
                    )
                elif isinstance(node, FnNode):
                    semaphore = await session.concurrency.get_semaphore(
                        node._concurrent,
                        node._concurrency_group,
                        node._max_concurrent,
                    )
                    if semaphore:
                        async with semaphore:
                            return await asyncio.to_thread(
                                self._execute_single_node_sync,
                                session,
                                node_name,
                                item_inputs,
                            )
                    else:
                        return await asyncio.to_thread(
                            self._execute_single_node_sync,
                            session,
                            node_name,
                            item_inputs,
                        )
                else:
                    return await asyncio.to_thread(
                        self._execute_single_node_sync, session, node_name, item_inputs
                    )
            except Exception as e:
                return {"error": str(e)}

        if isinstance(node, (GradioNode, InferenceNode)):
            tasks = [execute_item(item, i) for i, item in enumerate(items)]
            results = await asyncio.gather(*tasks)
        else:
            results = []
            for i, item in enumerate(items):
                result = await execute_item(item, i)
                results.append(result)

        session.scattered_results[node_name] = list(results)
        return {"_scattered_results": list(results), "_items": items}

    def _wrap_file_input(self, value: Any) -> Any:
        from gradio_client import handle_file

        if isinstance(value, FileValue):
            return handle_file(str(value))

        if isinstance(value, str) and value.startswith("data:"):
            file_path = self._save_data_url_to_file(value)
            if file_path:
                return handle_file(file_path)

        return value

    def _save_data_url_to_file(self, data_url: str) -> str | None:
        """Convert a base64 data URL to a file and return the path."""
        import base64
        import uuid

        from daggr.state import get_daggr_files_dir

        if not data_url.startswith("data:"):
            return None

        try:
            header, encoded = data_url.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]
            ext_map = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/jpg": ".jpg",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "audio/wav": ".wav",
                "audio/mpeg": ".mp3",
                "audio/mp3": ".mp3",
                "audio/ogg": ".ogg",
                "audio/webm": ".webm",
                "video/mp4": ".mp4",
                "video/webm": ".webm",
            }
            ext = ext_map.get(media_type, ".bin")
            data = base64.b64decode(encoded)
            file_path = get_daggr_files_dir() / f"{uuid.uuid4()}{ext}"
            file_path.write_bytes(data)
            return str(file_path)
        except Exception:
            return None

    def _apply_postprocess(self, postprocess, raw_result: Any) -> Any:
        if isinstance(raw_result, (list, tuple)):
            return postprocess(*raw_result)
        return postprocess(raw_result)

    def _extract_file_urls(self, data: Any) -> Any:
        from gradio_client.utils import is_file_obj_with_meta, traverse

        def download_and_wrap(file_obj: dict) -> FileValue:
            url = file_obj.get("url")
            if url:
                local_path = _download_file(url)
                return FileValue(local_path)
            path = file_obj.get("path", "")
            return FileValue(path)

        return traverse(data, download_and_wrap, is_file_obj_with_meta)

    def _map_gradio_result(self, node, raw_result: Any) -> dict[str, Any]:
        if raw_result is None:
            return {}

        raw_result = self._extract_file_urls(raw_result)

        output_ports = node._output_ports
        if not output_ports:
            return {"output": raw_result}

        if isinstance(raw_result, (list, tuple)):
            result = {}
            for i, port_name in enumerate(output_ports):
                if i < len(raw_result):
                    result[port_name] = raw_result[i]
                else:
                    result[port_name] = None
            return result
        elif len(output_ports) == 1:
            return {output_ports[0]: raw_result}
        else:
            return {output_ports[0]: raw_result}

    def _map_fn_result(self, node, raw_result: Any) -> dict[str, Any]:
        if raw_result is None:
            return {}

        output_ports = node._output_ports
        if not output_ports:
            return {"output": raw_result}

        if isinstance(raw_result, tuple):
            result = {}
            for i, port_name in enumerate(output_ports):
                if i < len(raw_result):
                    result[port_name] = raw_result[i]
                else:
                    result[port_name] = None
            return result
        else:
            return {output_ports[0]: raw_result}

    def _map_inference_result(self, node, raw_result: Any) -> dict[str, Any]:
        """Map inference API result to output ports."""
        if raw_result is None:
            return {}

        output_ports = node._output_ports
        if not output_ports:
            return {"output": raw_result}

        return {output_ports[0]: raw_result}

    async def execute_all(
        self, session: ExecutionSession, entry_inputs: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        execution_order = self.graph.get_execution_order()
        session.results = {}

        for node_name in execution_order:
            user_input = entry_inputs.get(node_name, {})
            await self.execute_node(session, node_name, user_input)

        return session.results


class SequentialExecutor:
    """Legacy synchronous executor for backwards compatibility.
    
    This wraps the AsyncExecutor for use in synchronous contexts like node.test().
    For production use, prefer AsyncExecutor with proper session management.
    """

    def __init__(self, graph: Graph, hf_token: str | None = None):
        from daggr.session import ExecutionSession

        self.graph = graph
        self._async_executor = AsyncExecutor(graph)
        self._session = ExecutionSession(graph, hf_token)

    @property
    def results(self) -> dict[str, Any]:
        return self._session.results

    @results.setter
    def results(self, value: dict[str, Any]):
        self._session.results = value

    @property
    def selected_variants(self) -> dict[str, int]:
        return self._session.selected_variants

    @selected_variants.setter
    def selected_variants(self, value: dict[str, int]):
        self._session.selected_variants = value

    def set_hf_token(self, token: str | None):
        self._session.set_hf_token(token)

    def execute_node(
        self, node_name: str, user_inputs: dict[str, Any] | None = None
    ) -> Any:
        """Synchronous wrapper around async execute_node."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._async_executor.execute_node(self._session, node_name, user_inputs)
            )
        finally:
            loop.close()

    def execute_all(self, entry_inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Synchronous wrapper around async execute_all."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._async_executor.execute_all(self._session, entry_inputs)
            )
        finally:
            loop.close()
