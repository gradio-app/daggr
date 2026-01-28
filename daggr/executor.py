from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from daggr.graph import Graph


class FileValue(str):
    """A string subclass that marks a value as a file URL/path from Gradio output."""

    pass


class SequentialExecutor:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.clients: dict[str, Any] = {}
        self.results: dict[str, Any] = {}
        self.scattered_results: dict[str, list[Any]] = {}
        self.selected_variants: dict[str, int] = {}

    def _get_client_for_gradio_node(self, gradio_node, cache_key: str):
        from daggr import _client_cache

        if cache_key in self.clients:
            return self.clients[cache_key]

        if gradio_node._run_locally:
            from daggr.local_space import get_local_client

            client = get_local_client(gradio_node)
            if client is not None:
                self.clients[cache_key] = client
                return client

        client = _client_cache.get_client(gradio_node._src)
        if client is None:
            from gradio_client import Client

            from daggr.state import get_daggr_files_dir

            client = Client(
                gradio_node._src,
                download_files=get_daggr_files_dir(),
                verbose=False,
            )
            _client_cache.set_client(gradio_node._src, client)

        self.clients[cache_key] = client
        return client

    def _get_client(self, node_name: str):
        from daggr.node import ChoiceNode, GradioNode

        node = self.graph.nodes[node_name]

        if isinstance(node, ChoiceNode):
            variant_idx = self.selected_variants.get(node_name, 0)
            variant = node._variants[variant_idx]
            if isinstance(variant, GradioNode):
                cache_key = f"{node_name}__variant_{variant_idx}"
                return self._get_client_for_gradio_node(variant, cache_key)
            return None

        if not isinstance(node, GradioNode):
            return None

        return self._get_client_for_gradio_node(node, node_name)

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
        self, node_name: str, skip_scattered: bool = False
    ) -> dict[str, Any]:
        inputs = {}

        for edge in self.graph._edges:
            if edge.target_node._name == node_name:
                if skip_scattered and edge.is_scattered:
                    continue

                source_name = edge.source_node._name
                source_output = edge.source_port
                target_input = edge.target_port

                if source_name in self.results:
                    source_result = self.results[source_name]

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

    def _execute_single_node(self, node_name: str, inputs: dict[str, Any]) -> Any:
        from daggr.node import (
            ChoiceNode,
            FnNode,
            GradioNode,
            InferenceNode,
            InteractionNode,
        )

        node = self.graph.nodes[node_name]

        if isinstance(node, ChoiceNode):
            variant_idx = self.selected_variants.get(node_name, 0)
            variant = node._variants[variant_idx]
            return self._execute_variant_node(node_name, variant, inputs)

        all_inputs = {}
        for port_name, value in node._fixed_inputs.items():
            all_inputs[port_name] = value() if callable(value) else value
        for port_name, component in node._input_components.items():
            if hasattr(component, "value") and component.value is not None:
                all_inputs[port_name] = component.value
        all_inputs.update(inputs)

        if isinstance(node, GradioNode):
            client = self._get_client(node_name)
            if client:
                api_name = node._api_name or "/predict"
                if not api_name.startswith("/"):
                    api_name = "/" + api_name
                call_inputs = {
                    k: self._wrap_file_input(v)
                    for k, v in all_inputs.items()
                    if k in node._input_ports
                }
                raw_result = client.predict(api_name=api_name, **call_inputs)
                result = self._map_gradio_result(node, raw_result)
            else:
                result = None

        elif isinstance(node, FnNode):
            fn_kwargs = {}
            for port_name in node._input_ports:
                if port_name in all_inputs:
                    fn_kwargs[port_name] = all_inputs[port_name]
            raw_result = node._fn(**fn_kwargs)
            result = self._map_fn_result(node, raw_result)

        elif isinstance(node, InferenceNode):
            from huggingface_hub import InferenceClient

            client = InferenceClient(model=node._model)
            input_value = all_inputs.get(
                "input",
                all_inputs.get(node._input_ports[0]) if node._input_ports else None,
            )
            result = client.text_generation(input_value) if input_value else None

        elif isinstance(node, InteractionNode):
            result = all_inputs.get(
                "input",
                all_inputs.get(node._input_ports[0]) if node._input_ports else None,
            )

        else:
            result = None

        return result

    def _execute_variant_node(
        self, node_name: str, variant, inputs: dict[str, Any]
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
            client = self._get_client(node_name)
            if client:
                api_name = variant._api_name or "/predict"
                if not api_name.startswith("/"):
                    api_name = "/" + api_name
                call_inputs = {
                    k: self._wrap_file_input(v)
                    for k, v in all_inputs.items()
                    if k in variant._input_ports
                }
                raw_result = client.predict(api_name=api_name, **call_inputs)
                result = self._map_gradio_result(variant, raw_result)
            else:
                result = None

        elif isinstance(variant, FnNode):
            fn_kwargs = {}
            for port_name in variant._input_ports:
                if port_name in all_inputs:
                    fn_kwargs[port_name] = all_inputs[port_name]
            raw_result = variant._fn(**fn_kwargs)
            result = self._map_fn_result(variant, raw_result)

        elif isinstance(variant, InferenceNode):
            from huggingface_hub import InferenceClient

            client = InferenceClient(model=variant._model)
            input_value = all_inputs.get(
                "input",
                all_inputs.get(variant._input_ports[0])
                if variant._input_ports
                else None,
            )
            result = client.text_generation(input_value) if input_value else None

        else:
            result = None

        return result

    def _wrap_file_input(self, value: Any) -> Any:
        if isinstance(value, FileValue):
            from gradio_client import handle_file

            return handle_file(str(value))
        return value

    def _extract_file_urls(self, data: Any) -> Any:
        from gradio_client.utils import is_file_obj_with_meta, traverse

        def extract_url(file_obj: dict) -> FileValue:
            if "url" in file_obj and file_obj["url"]:
                return FileValue(file_obj["url"])
            return FileValue(file_obj.get("path", ""))

        return traverse(data, extract_url, is_file_obj_with_meta)

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
                    result[port_name] = self._extract_file_urls(raw_result[i])
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

        if isinstance(raw_result, dict):
            return raw_result
        elif isinstance(raw_result, (list, tuple)):
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

    def execute_node(
        self, node_name: str, user_inputs: dict[str, Any] | None = None
    ) -> Any:
        node = self.graph.nodes[node_name]
        scattered_edges = self._get_scattered_input_edges(node_name)

        if scattered_edges:
            result = self._execute_scattered_node(
                node_name, scattered_edges, user_inputs
            )
        else:
            inputs = self._prepare_inputs(node_name)
            if user_inputs:
                if isinstance(user_inputs, dict):
                    inputs.update(user_inputs)
                else:
                    if node._input_ports:
                        inputs[node._input_ports[0]] = user_inputs
                    else:
                        inputs["input"] = user_inputs

            try:
                result = self._execute_single_node(node_name, inputs)
            except Exception as e:
                raise RuntimeError(f"Error executing node '{node_name}': {e}")

        self.results[node_name] = result
        return result

    def _execute_scattered_node(
        self,
        node_name: str,
        scattered_edges: list,
        user_inputs: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]:
        first_edge = scattered_edges[0]
        source_name = first_edge.source_node._name
        source_port = first_edge.source_port

        source_result = self.results.get(source_name)
        if source_result is None:
            items = []
        elif isinstance(source_result, dict) and source_port in source_result:
            items = source_result[source_port]
        else:
            items = source_result

        if not isinstance(items, list):
            items = [items]

        context_inputs = self._prepare_inputs(node_name, skip_scattered=True)
        if user_inputs:
            context_inputs.update(user_inputs)

        results = []
        for item in items:
            item_inputs = dict(context_inputs)
            for edge in scattered_edges:
                target_port = edge.target_port
                item_key = edge.item_key
                if item_key and isinstance(item, dict):
                    item_inputs[target_port] = item.get(item_key)
                else:
                    item_inputs[target_port] = item

            try:
                item_result = self._execute_single_node(node_name, item_inputs)
                results.append(item_result)
            except Exception as e:
                results.append({"error": str(e)})

        self.scattered_results[node_name] = results
        return {"_scattered_results": results, "_items": items}

    def execute_scattered_item(
        self, node_name: str, item_index: int, inputs: dict[str, Any] | None = None
    ) -> Any:
        scattered_edges = self._get_scattered_input_edges(node_name)
        if not scattered_edges:
            raise ValueError(f"Node '{node_name}' does not have a scattered input")

        first_edge = scattered_edges[0]
        source_name = first_edge.source_node._name
        source_port = first_edge.source_port

        source_result = self.results.get(source_name)
        if source_result is None:
            items = []
        elif isinstance(source_result, dict) and source_port in source_result:
            items = source_result[source_port]
        else:
            items = source_result

        if not isinstance(items, list):
            items = [items]

        if item_index < 0 or item_index >= len(items):
            raise IndexError(f"Item index {item_index} out of range")

        item = items[item_index]
        context_inputs = self._prepare_inputs(node_name, skip_scattered=True)
        if inputs:
            context_inputs.update(inputs)

        item_inputs = dict(context_inputs)
        for edge in scattered_edges:
            target_port = edge.target_port
            item_key = edge.item_key
            if item_key and isinstance(item, dict):
                item_inputs[target_port] = item.get(item_key)
            else:
                item_inputs[target_port] = item

        result = self._execute_single_node(node_name, item_inputs)

        if node_name in self.scattered_results:
            self.scattered_results[node_name][item_index] = result

        return result

    def execute_all(self, entry_inputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        execution_order = self.graph.get_execution_order()
        self.results = {}

        for node_name in execution_order:
            user_input = entry_inputs.get(node_name, {})
            self.execute_node(node_name, user_input)

        return self.results
