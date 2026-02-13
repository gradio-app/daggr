"""Node types for daggr graphs.

This module defines the various node types that can be used in a daggr graph:
- Node: Abstract base class for all nodes
- GradioNode: Wraps a Gradio Space or endpoint
- InferenceNode: Wraps a Hugging Face Inference API model
- FnNode: Wraps a Python function
- InteractionNode: Represents user interaction points
"""

from __future__ import annotations

import inspect
import warnings
from abc import ABC
from collections.abc import Callable
from typing import Any

from daggr._utils import suggest_similar
from daggr.port import ItemList, Port, PortNamespace, is_port

_FILE_TYPE_COMPONENTS = {
    "Image",
    "Audio",
    "Video",
    "File",
    "Gallery",
    "ImageEditor",
    "ImageSlider",
}


def _warn_if_type_set(component: Any, port_name: str) -> None:
    constructor_args = getattr(component, "_constructor_args", None)
    if not constructor_args:
        return
    comp_type = constructor_args[0].get("type")
    if comp_type is None:
        return
    class_name = type(component).__name__
    if class_name not in _FILE_TYPE_COMPONENTS:
        return
    if comp_type != "filepath":
        warnings.warn(
            f"Gradio component {class_name}(type={comp_type!r}) on port '{port_name}': "
            f"daggr ignores the `type` parameter. All file data is passed as file path "
            f"strings regardless of this setting.",
            stacklevel=4,
        )


def _is_gradio_component(obj: Any) -> bool:
    if obj is None:
        return False
    class_name = obj.__class__.__name__
    module = getattr(obj.__class__, "__module__", "")
    return "gradio" in module or class_name in (
        "Textbox",
        "TextArea",
        "Audio",
        "Image",
        "JSON",
        "Markdown",
        "Number",
        "Checkbox",
        "Dropdown",
        "Radio",
        "Slider",
        "File",
        "Video",
        "Gallery",
        "Chatbot",
        "Text",
    )


class Node(ABC):
    """Abstract base class for all nodes in a daggr graph.

    Nodes represent processing steps in a DAG. Each node has named input and
    output ports that can be connected to form a data processing pipeline.

    Ports can be accessed as attributes: `node.port_name` returns a Port object.

    Args:
        name: Optional display name for the node. If not provided, a name will
            be auto-generated based on the node type.
    """

    _id_counter = 0

    def __init__(self, name: str | None = None, embed_inputs: bool = False):
        self._id = Node._id_counter
        Node._id_counter += 1
        self._name = name or ""
        self._name_explicitly_set = bool(name)
        self._embed_inputs = embed_inputs
        self._input_ports: list[str] = []
        self._output_ports: list[str] = []
        self._input_components: dict[str, Any] = {}
        self._output_components: dict[str, Any] = {}
        self._item_list_schemas: dict[str, dict[str, Any]] = {}
        self._fixed_inputs: dict[str, Any] = {}
        self._port_connections: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def embed_inputs(self) -> bool:
        return self._embed_inputs

    @name.setter
    def name(self, value: str) -> None:
        self._name = value
        self._name_explicitly_set = True

    def __getattr__(self, name: str) -> Port:
        if name.startswith("_"):
            raise AttributeError(name)
        return Port(self, name)

    def __dir__(self) -> list[str]:
        base = [
            "_name",
            "_inputs",
            "_outputs",
            "_input_ports",
            "_embed_inputs",
            "_output_ports",
        ]
        return base + self._input_ports + self._output_ports

    def __or__(self, other: Node) -> ChoiceNode:
        """Combine two nodes as alternatives using the | operator.

        Returns a ChoiceNode that lets users pick which variant to run.

        Example:
            >>> tts = GradioNode("space1/tts", ...) | GradioNode("space2/tts", ...)
            >>> # tts.audio works regardless of which variant is selected
        """
        if isinstance(other, ChoiceNode):
            return ChoiceNode([self] + other._variants, name=self._name)
        return ChoiceNode([self, other], name=self._name)

    @property
    def _inputs(self) -> PortNamespace:
        return PortNamespace(self, self._input_ports)

    @property
    def _outputs(self) -> PortNamespace:
        return PortNamespace(self, self._output_ports)

    def _default_output_port(self) -> Port:
        if self._output_ports:
            return Port(self, self._output_ports[0])
        return Port(self, "output")

    def _default_input_port(self) -> Port:
        if self._input_ports:
            return Port(self, self._input_ports[0])
        return Port(self, "input")

    def _validate_ports(self):
        all_ports = set(self._input_ports + self._output_ports)
        underscore_ports = [p for p in all_ports if p.startswith("_")]
        if underscore_ports:
            warnings.warn(
                f"Port names {underscore_ports} start with underscore. "
                f"Use node._inputs.{underscore_ports[0]} or node._outputs.{underscore_ports[0]} to access."
            )

    def _process_inputs(self, inputs: dict[str, Any]) -> None:
        for port_name, value in inputs.items():
            self._input_ports.append(port_name)
            if is_port(value):
                self._port_connections[port_name] = value
            elif _is_gradio_component(value):
                _warn_if_type_set(value, port_name)
                self._input_components[port_name] = value
            else:
                self._fixed_inputs[port_name] = value

    def _process_outputs(self, outputs: dict[str, Any]) -> None:
        for port_name, component in outputs.items():
            self._output_ports.append(port_name)
            if component is not None and _is_gradio_component(component):
                _warn_if_type_set(component, port_name)
                self._output_components[port_name] = component

    def test(self, **inputs) -> dict[str, Any]:
        """Test-run this node in isolation and return the raw result.

        If no inputs are provided, auto-generates example values using:
        - Gradio component's .example_value() method
        - Port's associated output component's .example_value()
        - Callable inputs are called
        - Fixed values are used directly

        Args:
            **inputs: Override inputs for the test run.

        Returns:
            Dict mapping output port names to their values.

        Example:
            >>> tts = GradioNode("mrfakename/MeloTTS", api_name="/synthesize", ...)
            >>> result = tts.test(text="Hello world", speaker="EN-US")
            >>> # Returns: {"audio": "/path/to/audio.wav"}
            >>>
            >>> # Or with auto-generated example values:
            >>> result = tts.test()
        """
        from daggr import Graph
        from daggr.executor import SequentialExecutor

        if not inputs:
            inputs = self._generate_example_inputs()

        graph = Graph("_test", nodes=[self], persist_key=False)
        executor = SequentialExecutor(graph)
        return executor.execute_node(self._name, inputs)

    def _generate_example_inputs(self) -> dict[str, Any]:
        """Generate example values for all input ports."""
        examples = {}

        # From input components (Gradio components)
        for port_name, comp in self._input_components.items():
            if hasattr(comp, "example_value"):
                examples[port_name] = comp.example_value()

        # From fixed inputs (constants, callables, or port connections)
        for port_name, source in self._fixed_inputs.items():
            if callable(source):
                examples[port_name] = source()
            else:
                examples[port_name] = source

        # From port connections (use the connected port's output component)
        for port_name, port in self._port_connections.items():
            if is_port(port):
                comp = port._node._output_components.get(port._port_name)
                if comp and hasattr(comp, "example_value"):
                    examples[port_name] = comp.example_value()

        return examples

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self._name})"


class ChoiceNode(Node):
    """A node that wraps multiple alternative nodes.

    ChoiceNode allows users to select which variant to run from a set of
    alternatives. Created using the | operator between nodes.

    The output ports are the union of all variants' output ports, so downstream
    nodes can connect to any output that exists in at least one variant.

    Args:
        variants: List of Node objects that serve as alternatives.
        name: Optional display name. Defaults to the first variant's name.

    Example:
        >>> tts = GradioNode("space1/tts", ...) | GradioNode("space2/tts", ...)
        >>> # tts is a ChoiceNode with two variants
        >>> # tts.audio works regardless of which variant is selected
    """

    def __init__(
        self,
        variants: list[Node],
        name: str | None = None,
    ):
        if not variants:
            raise ValueError("ChoiceNode requires at least one variant")

        super().__init__(name)
        self._variants = variants
        self._selected_variant = 0

        if not self._name:
            self._name = variants[0]._name

        self._output_ports = self._compute_union_output_ports()
        self._output_components = self._compute_union_output_components()

        for variant in variants:
            for port_name, port in variant._port_connections.items():
                if port_name not in self._port_connections:
                    self._port_connections[port_name] = port

    def _compute_union_output_ports(self) -> list[str]:
        seen = set()
        ports = []
        for variant in self._variants:
            for port in variant._output_ports:
                if port not in seen:
                    seen.add(port)
                    ports.append(port)
        return ports

    def _compute_union_output_components(self) -> dict[str, Any]:
        components = {}
        for variant in self._variants:
            for port_name, comp in variant._output_components.items():
                if port_name not in components:
                    components[port_name] = comp
        return components

    def __or__(self, other: Node) -> ChoiceNode:
        if isinstance(other, ChoiceNode):
            return ChoiceNode(self._variants + other._variants, name=self._name)
        return ChoiceNode(self._variants + [other], name=self._name)

    def __repr__(self):
        variant_names = [v._name for v in self._variants]
        return f"ChoiceNode(name={self._name}, variants={variant_names})"


class GradioNode(Node):
    """A node that wraps a Gradio Space or endpoint.

    GradioNode connects to a Hugging Face Space or any Gradio app and exposes
    its API as a node in the graph.

    Args:
        space_or_url: Hugging Face Space ID (e.g., "username/space-name") or
            a full URL to a Gradio app.
        api_name: The API endpoint to call (e.g., "/predict"). Defaults to "/predict".
        name: Optional display name for the node.
        inputs: Dict mapping input port names to Gradio components, Port connections,
            or fixed values.
        outputs: Dict mapping output port names to Gradio components for display.
        validate: Whether to validate the Space exists and has the specified endpoint.
        run_locally: If True, clone and run the Space locally instead of using the
            remote API.
        embed_inputs: If True, embeds the input UI components (sliders, textboxes)
            within the node's body instead of creating separate external Input nodes.
            Useful for parameter-heavy nodes to reduce graph clutter. Defaults to False.
    Example:
        >>> tts = GradioNode(
        ...     "mrfakename/MeloTTS",
        ...     api_name="/synthesize",
        ...     inputs={"text": gr.Textbox(), "speaker": "EN-US"},
        ...     outputs={"audio": gr.Audio()},
        ... )
    """

    _name_counters: dict[str, int] = {}

    def __init__(
        self,
        space_or_url: str,
        api_name: str | None = None,
        name: str | None = None,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        validate: bool = True,
        run_locally: bool = False,
        preprocess: Callable[[dict], dict] | None = None,
        postprocess: Callable[..., Any] | None = None,
        embed_inputs: bool = False,
    ):
        super().__init__(name, embed_inputs=embed_inputs)
        self._src = space_or_url
        self._api_name = api_name
        self._run_locally = run_locally
        self._local_url: str | None = None
        self._local_failed = False
        self._preprocess = preprocess
        self._postprocess = postprocess

        if validate:
            self._validate_space_format()

        if not self._name:
            base_name = self._src.split("/")[-1]
            if base_name not in GradioNode._name_counters:
                GradioNode._name_counters[base_name] = 0
                self._name = base_name
            else:
                GradioNode._name_counters[base_name] += 1
                self._name = f"{base_name}_{GradioNode._name_counters[base_name]}"

        self._process_inputs(inputs or {})
        self._process_outputs(outputs or {})
        self._validate_ports()

        if validate and not run_locally:
            self._validate_gradio_api(inputs or {}, outputs or {})

    def _validate_space_format(self) -> None:
        src = self._src
        if not ("/" in src or src.startswith("http://") or src.startswith("https://")):
            raise ValueError(
                f"Invalid space_or_url '{src}'. Expected format: 'username/space-name' "
                f"or a full URL like 'https://...'"
            )

    def _get_api_info(self) -> dict:
        from daggr import _client_cache

        cached = _client_cache.get_api_info(self._src)
        if cached is not None:
            return cached

        from gradio_client import Client

        client = _client_cache.get_client(self._src)
        if client is None:
            client = Client(self._src, download_files=False, verbose=False)
            _client_cache.set_client(self._src, client)

        api_info = client.view_api(return_format="dict", print_info=False)
        _client_cache.set_api_info(self._src, api_info)
        return api_info

    def _validate_gradio_api(
        self, inputs: dict[str, Any], outputs: dict[str, Any]
    ) -> None:
        from daggr import _client_cache

        api_name = self._api_name or "/predict"
        if not api_name.startswith("/"):
            api_name = "/" + api_name

        cache_key = (
            self._src,
            api_name,
            tuple(sorted(inputs.keys())),
            tuple(sorted(outputs.keys())) if outputs else (),
        )
        if _client_cache.is_validated(cache_key):
            return

        api_info = self._get_api_info()

        named_endpoints = api_info.get("named_endpoints", {})
        unnamed_endpoints = api_info.get("unnamed_endpoints", {})

        endpoint_info = None
        if api_name in named_endpoints:
            endpoint_info = named_endpoints[api_name]
        else:
            try:
                fn_index = int(api_name.lstrip("/"))
                if fn_index in unnamed_endpoints or str(fn_index) in unnamed_endpoints:
                    endpoint_info = unnamed_endpoints.get(
                        fn_index, unnamed_endpoints.get(str(fn_index))
                    )
            except ValueError:
                pass

        if endpoint_info is None:
            available = list(named_endpoints.keys())
            if unnamed_endpoints:
                available.extend([f"/{k}" for k in unnamed_endpoints.keys()])
            suggested = suggest_similar(api_name, set(available))
            msg = (
                f"API endpoint '{api_name}' not found in '{self._src}'. "
                f"Available endpoints: {available}"
            )
            if suggested:
                msg += f" Did you mean '{suggested}'?"
            raise ValueError(msg)

        params_info = endpoint_info.get("parameters", [])
        valid_params = {p.get("parameter_name", p["label"]) for p in params_info}
        input_params = set(inputs.keys())
        invalid_params = input_params - valid_params

        if invalid_params:
            suggestions = {}
            for inv in invalid_params:
                suggestion = suggest_similar(inv, valid_params)
                if suggestion:
                    suggestions[inv] = suggestion
            msg = (
                f"Invalid parameter(s) {invalid_params} for endpoint '{api_name}' "
                f"in '{self._src}'."
            )
            if suggestions:
                suggestion_str = ", ".join(
                    f"'{k}' -> '{v}'" for k, v in suggestions.items()
                )
                msg += f" Did you mean: {suggestion_str}?"
            msg += f" Valid parameters: {valid_params}"
            raise ValueError(msg)

        required_params = {
            p.get("parameter_name", p["label"])
            for p in params_info
            if not p.get("parameter_has_default", False)
        }
        provided_params = set(inputs.keys())
        missing_required = required_params - provided_params

        if missing_required:
            raise ValueError(
                f"Missing required parameter(s) {missing_required} for endpoint "
                f"'{api_name}' in '{self._src}'. These parameters have no default values."
            )

        api_returns = endpoint_info.get("returns", [])
        if outputs and api_returns and not self._postprocess:
            num_returns = len(api_returns)
            num_outputs = len(outputs)
            if num_outputs > num_returns:
                warnings.warn(
                    f"GradioNode '{self._name}' defines {num_outputs} outputs but "
                    f"endpoint '{api_name}' only returns {num_returns} value(s). "
                    f"Extra outputs will be None."
                )

        _client_cache.mark_validated(cache_key)


class InferenceNode(Node):
    """A node that wraps a Hugging Face Inference API model.

    InferenceNode uses the Hugging Face Inference API to run models without
    needing to download them locally. The task type (text-generation, text-to-image,
    etc.) is automatically determined from the model's pipeline_tag on the Hub.

    Args:
        model: The Hugging Face model ID (e.g., "meta-llama/Llama-2-7b-chat-hf").
        name: Optional display name for the node.
        inputs: Dict mapping input port names to values or components.
        outputs: Dict mapping output port names to components.
        validate: Whether to validate the model exists on the Hub.
        preprocess: Optional function that receives the input dict and returns a
            modified dict before the inference call.
        postprocess: Optional function that receives the raw inference result and
            returns a transformed value before it is mapped to output ports.
        embed_inputs: If True, embeds the input UI components (sliders, textboxes)
            within the node's body instead of creating separate external Input nodes.
            Useful for parameter-heavy nodes to reduce graph clutter. Defaults to False.
    Example:
        >>> llm = InferenceNode("meta-llama/Llama-2-7b-chat-hf")
    """

    def __init__(
        self,
        model: str,
        name: str | None = None,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        validate: bool = True,
        preprocess: Callable[[dict], dict] | None = None,
        postprocess: Callable[..., Any] | None = None,
        embed_inputs: bool = False,
    ):
        super().__init__(name, embed_inputs=embed_inputs)
        self._model = model
        self._task: str | None = None
        self._task_fetched: bool = False
        self._preprocess = preprocess
        self._postprocess = postprocess

        if not self._name:
            # Strip provider tag (e.g., ":replicate") for display name
            self._name = self._model_name_for_hub.split("/")[-1]

        if inputs:
            self._process_inputs(inputs)
        else:
            self._input_ports = ["input"]

        if outputs:
            self._process_outputs(outputs)
        else:
            self._output_ports = ["output"]

        self._validate_ports()

        if validate:
            self._fetch_model_info()

    @property
    def _model_name_for_hub(self) -> str:
        """Return the model name without provider tags (e.g., ':replicate')."""
        # HF Inference Client allows tags like "model:provider" for routing
        # Strip these for Hub API calls and display
        return self._model.split(":")[0]

    @property
    def _provider(self) -> str | None:
        """Return the provider tag if specified (e.g., 'replicate' from 'model:replicate')."""
        parts = self._model.split(":")
        return parts[1] if len(parts) > 1 else None

    def _fetch_model_info(self) -> None:
        if self._task_fetched:
            return

        from daggr import _client_cache

        # Use model name without provider tag for Hub lookups
        hub_model = self._model_name_for_hub

        found_in_cache, cached = _client_cache.get_model_task(hub_model)
        if found_in_cache:
            if cached == "__NOT_FOUND__":
                raise ValueError(f"Model '{hub_model}' not found on Hugging Face Hub.")
            self._task = cached
            self._task_fetched = True
            return

        from huggingface_hub import model_info
        from huggingface_hub.utils import RepositoryNotFoundError

        try:
            info = model_info(hub_model)
            self._task = info.pipeline_tag
            _client_cache.set_model_task(hub_model, self._task)
            self._task_fetched = True
        except RepositoryNotFoundError:
            _client_cache.set_model_not_found(hub_model)
            raise ValueError(
                f"Model '{hub_model}' not found on Hugging Face Hub. "
                f"Please check the model name is correct (format: 'username/model-name')."
            )


class FnNode(Node):
    """A node that wraps a Python function.

    FnNode allows you to use any Python function as a node in the graph.
    Input ports are automatically discovered from the function signature.

    Return values are mapped to output ports in order, just like GradioNode:
    - Single value: maps to the first output port
    - Tuple: each element maps to the corresponding output port in order

    Concurrency:
        By default, FnNodes execute sequentially (one at a time per session)
        to prevent resource contention. Use the concurrency parameters to
        allow parallel execution:

        - concurrent=True: Allow this node to run in parallel with others
        - concurrency_group: Group nodes that share a resource (e.g., GPU)
        - max_concurrent: Max parallel executions within a group (default: 1)

        Note: GradioNode and InferenceNode always run concurrently since they
        are external API calls. Prefer these over FnNode when possible.

    Args:
        fn: The Python function to wrap.
        name: Optional display name. Defaults to the function name.
        inputs: Optional dict to explicitly define input ports and their
            connections or UI components.
        outputs: Optional dict mapping output port names to UI components
            or ItemList schemas.
        concurrent: If True, allow parallel execution. Default: False.
        concurrency_group: Name of a group sharing a concurrency limit.
        max_concurrent: Max parallel executions in the group. Default: 1.
        embed_inputs: If True, embeds the input UI components (sliders, textboxes)
            within the node's body instead of creating separate external Input nodes.
            Useful for parameter-heavy nodes to reduce graph clutter. Defaults to False.

    Example:
        >>> def process_text(text: str) -> tuple[str, int]:
        ...     return text.upper(), len(text)
        >>> node = FnNode(
        ...     process_text,
        ...     outputs={"uppercase": gr.Textbox(), "length": gr.Number()}
        ... )

        >>> # Allow parallel execution
        >>> node = FnNode(my_func, concurrent=True)

        >>> # Share GPU with other nodes (max 2 concurrent)
        >>> node = FnNode(gpu_func, concurrency_group="gpu", max_concurrent=2)
    """

    def __init__(
        self,
        fn: Callable,
        name: str | None = None,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        preprocess: Callable[[dict], dict] | None = None,
        postprocess: Callable[..., Any] | None = None,
        concurrent: bool = False,
        concurrency_group: str | None = None,
        max_concurrent: int = 1,
        embed_inputs: bool = False,
    ):
        super().__init__(name, embed_inputs=embed_inputs)
        self._fn = fn
        self._preprocess = preprocess
        self._postprocess = postprocess
        self._concurrent = concurrent
        self._concurrency_group = concurrency_group
        self._max_concurrent = max_concurrent

        if not self._name:
            self._name = self._fn.__name__

        if inputs:
            self._validate_fn_inputs(inputs)
            self._process_inputs(inputs)
        else:
            self._discover_signature()

        if outputs:
            self._process_outputs(outputs)
        else:
            self._output_ports = ["output"]

        self._validate_ports()

    def _discover_signature(self):
        sig = inspect.signature(self._fn)
        self._input_ports = list(sig.parameters.keys())

    def _validate_fn_inputs(self, inputs: dict[str, Any]) -> None:
        sig = inspect.signature(self._fn)
        valid_params = set(sig.parameters.keys())
        provided_params = set(inputs.keys())
        invalid_params = provided_params - valid_params

        if invalid_params:
            suggestions = {}
            for inv in invalid_params:
                suggestion = suggest_similar(inv, valid_params)
                if suggestion:
                    suggestions[inv] = suggestion

            msg = (
                f"Invalid input(s) {invalid_params} for function '{self._fn.__name__}'."
            )
            if suggestions:
                suggestion_str = ", ".join(
                    f"'{k}' -> '{v}'" for k, v in suggestions.items()
                )
                msg += f" Did you mean: {suggestion_str}?"
            msg += f" Valid parameters: {valid_params}"
            raise ValueError(msg)

    def _process_outputs(self, outputs: dict[str, Any]) -> None:
        for port_name, component in outputs.items():
            self._output_ports.append(port_name)
            if component is None:
                continue
            if isinstance(component, ItemList):
                self._item_list_schemas[port_name] = component.schema
            elif _is_gradio_component(component):
                self._output_components[port_name] = component


class InteractionNode(Node):
    """A node representing a user interaction point in the graph.

    InteractionNodes pause execution and wait for user input before continuing.
    They are used for approval steps, selections, or other human-in-the-loop
    interactions.

    Args:
        name: Optional display name for the node.
        interaction_type: Type of interaction (e.g., "generic", "approve", "choose_one").
        inputs: Dict mapping input port names to components or connections.
        outputs: Dict mapping output port names to components.
    """

    def __init__(
        self,
        name: str | None = None,
        interaction_type: str = "generic",
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ):
        super().__init__(name)
        self._interaction_type = interaction_type

        if inputs:
            self._process_inputs(inputs)
        else:
            self._input_ports = ["input"]

        if outputs:
            self._process_outputs(outputs)
        else:
            self._output_ports = ["output"]

        if not self._name:
            self._name = f"interaction_{self._id}"

        self._validate_ports()
