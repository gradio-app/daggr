from __future__ import annotations

import inspect
import warnings
from abc import ABC
from typing import Any, Callable, Dict, List, Optional

from daggr.port import ItemList, Port, PortNamespace, is_port


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


def _get_component_label(component: Any, fallback: str) -> str:
    if hasattr(component, "label") and component.label:
        return component.label
    return fallback


def _is_component_visible(component: Any) -> bool:
    if hasattr(component, "visible"):
        return component.visible
    return True


class Node(ABC):
    _id_counter = 0

    def __init__(self, name: Optional[str] = None):
        self._id = Node._id_counter
        Node._id_counter += 1
        self._name = name or ""
        self._input_ports: List[str] = []
        self._output_ports: List[str] = []
        self._input_components: Dict[str, Any] = {}
        self._output_components: Dict[str, Any] = {}
        self._item_list_schemas: Dict[str, Dict[str, Any]] = {}
        self._fixed_inputs: Dict[str, Any] = {}
        self._port_connections: Dict[str, Any] = {}

    def __getattr__(self, name: str) -> Port:
        if name.startswith("_"):
            raise AttributeError(name)
        return Port(self, name)

    def __dir__(self) -> List[str]:
        base = ["_name", "_inputs", "_outputs", "_input_ports", "_output_ports"]
        return base + self._input_ports + self._output_ports

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

    def _get_visible_output_components(self) -> List[Any]:
        return [
            comp
            for port, comp in self._output_components.items()
            if _is_component_visible(comp)
        ]

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self._name})"


class GradioNode(Node):
    _name_counters: Dict[str, int] = {}

    def __init__(
        self,
        space_or_url: str,
        api_name: Optional[str] = None,
        name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name)
        self._src = space_or_url
        self._api_name = api_name

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

    def _process_inputs(self, inputs: Dict[str, Any]):
        for port_name, value in inputs.items():
            self._input_ports.append(port_name)
            if is_port(value):
                self._port_connections[port_name] = value
            elif _is_gradio_component(value):
                self._input_components[port_name] = value
            else:
                self._fixed_inputs[port_name] = value

    def _process_outputs(self, outputs: Dict[str, Any]):
        for port_name, component in outputs.items():
            self._output_ports.append(port_name)
            if _is_gradio_component(component):
                self._output_components[port_name] = component


class InferenceNode(Node):
    def __init__(
        self,
        model: str,
        name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name)
        self._model = model

        if not self._name:
            self._name = self._model.split("/")[-1]

        if inputs:
            self._process_inputs(inputs)
        else:
            self._input_ports = ["input"]

        if outputs:
            self._process_outputs(outputs)
        else:
            self._output_ports = ["output"]

        self._validate_ports()

    def _process_inputs(self, inputs: Dict[str, Any]):
        for port_name, value in inputs.items():
            self._input_ports.append(port_name)
            if is_port(value):
                self._port_connections[port_name] = value
            elif _is_gradio_component(value):
                self._input_components[port_name] = value
            else:
                self._fixed_inputs[port_name] = value

    def _process_outputs(self, outputs: Dict[str, Any]):
        for port_name, component in outputs.items():
            self._output_ports.append(port_name)
            if _is_gradio_component(component):
                self._output_components[port_name] = component


class FnNode(Node):
    def __init__(
        self,
        fn: Callable,
        name: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name)
        self._fn = fn

        if not self._name:
            self._name = self._fn.__name__

        if inputs:
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

    def _process_inputs(self, inputs: Dict[str, Any]):
        for port_name, value in inputs.items():
            self._input_ports.append(port_name)
            if is_port(value):
                self._port_connections[port_name] = value
            elif _is_gradio_component(value):
                self._input_components[port_name] = value
            else:
                self._fixed_inputs[port_name] = value

    def _process_outputs(self, outputs: Dict[str, Any]):
        for port_name, component in outputs.items():
            self._output_ports.append(port_name)
            if isinstance(component, ItemList):
                self._item_list_schemas[port_name] = component.schema
            elif _is_gradio_component(component):
                self._output_components[port_name] = component


class InteractionNode(Node):
    def __init__(
        self,
        name: Optional[str] = None,
        interaction_type: str = "generic",
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
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

    def _process_inputs(self, inputs: Dict[str, Any]):
        for port_name, value in inputs.items():
            self._input_ports.append(port_name)
            if is_port(value):
                self._port_connections[port_name] = value
            elif _is_gradio_component(value):
                self._input_components[port_name] = value
            else:
                self._fixed_inputs[port_name] = value

    def _process_outputs(self, outputs: Dict[str, Any]):
        for port_name, component in outputs.items():
            self._output_ports.append(port_name)
            if _is_gradio_component(component):
                self._output_components[port_name] = component
