from typing import Dict, Any, List, Optional
from gradio_client import Client


class SequentialExecutor:
    def __init__(self, workflow):
        self.workflow = workflow
        self.clients: Dict[str, Client] = {}
        self.results: Dict[str, Any] = {}

    def _get_client(self, node_name: str) -> Client:
        if node_name not in self.clients:
            node = self.workflow.nodes[node_name]
            self.clients[node_name] = Client(node.src)
        return self.clients[node_name]

    def _prepare_inputs(self, node_name: str) -> Dict[str, Any]:
        node = self.workflow.nodes[node_name]
        inputs = {}

        for source_name, source_output, target_name, target_input in self.workflow.connections:
            if target_name == node_name:
                if source_name in self.results:
                    source_result = self.results[source_name]
                    if isinstance(source_result, dict) and source_output in source_result:
                        inputs[target_input] = source_result[source_output]
                    elif isinstance(source_result, (list, tuple)):
                        try:
                            output_idx = int(source_output)
                            if 0 <= output_idx < len(source_result):
                                inputs[target_input] = source_result[output_idx]
                        except (ValueError, TypeError):
                            if len(source_result) > 0:
                                inputs[target_input] = source_result[0]
                    else:
                        inputs[target_input] = source_result

        return inputs

    def execute_node(self, node_name: str, user_inputs: Optional[Dict[str, Any]] = None) -> Any:
        node = self.workflow.nodes[node_name]
        client = self._get_client(node_name)

        inputs = self._prepare_inputs(node_name)
        
        if user_inputs:
            if isinstance(user_inputs, dict):
                inputs.update(user_inputs)
            else:
                if not inputs and node.inputs:
                    param_info = node.inputs[0]
                    param_name = param_info.get("label") or param_info.get("name") or "input"
                    inputs[param_name] = user_inputs
                elif not inputs:
                    inputs["input"] = user_inputs

        if not inputs and node.inputs:
            param_info = node.inputs[0]
            param_name = param_info.get("label") or param_info.get("name") or "input"
            if user_inputs and not isinstance(user_inputs, dict):
                inputs[param_name] = user_inputs

        try:
            if inputs:
                result = client.predict(**inputs)
            else:
                result = client.predict()
            self.results[node_name] = result
            return result
        except Exception as e:
            raise RuntimeError(f"Error executing node '{node_name}': {e}")

    def execute_all(self, entry_inputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        execution_order = self.workflow.get_execution_order()
        self.results = {}

        for node_name in execution_order:
            user_input = entry_inputs.get(node_name, {})
            self.execute_node(node_name, user_input)

        return self.results

