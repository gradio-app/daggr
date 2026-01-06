import gradio as gr
from typing import Dict, Any, List, Optional
from daggr.workflow import Workflow
from daggr.executor import SequentialExecutor


class UIGenerator:
    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.executor = SequentialExecutor(workflow)
        self.current_state: Dict[str, Any] = {}
        self.completed_nodes: set = set()

    def _create_node_ui(self, node_name: str) -> Dict[str, gr.Component]:
        node = self.workflow.nodes[node_name]
        components = {}

        if node.is_interaction_point or self.workflow.graph.in_degree(node_name) == 0:
            if node.inputs:
                for idx, param in enumerate(node.inputs):
                    param_name = param.get("label") or param.get("name") or f"input_{idx}"
                    param_type = param.get("type", "string")
                    param_label = param.get("label") or param.get("name") or param_name

                    if param_type in ["string", "text"]:
                        components[f"{node_name}_input_{param_name}"] = gr.Textbox(
                            label=f"{node.name}: {param_label}"
                        )
                    elif param_type in ["number", "float", "int"]:
                        components[f"{node_name}_input_{param_name}"] = gr.Number(
                            label=f"{node.name}: {param_label}"
                        )
                    else:
                        components[f"{node_name}_input_{param_name}"] = gr.Textbox(
                            label=f"{node.name}: {param_label}"
                        )
            else:
                components[f"{node_name}_input"] = gr.Textbox(
                    label=f"{node.name}: Input"
                )

        components[f"{node_name}_output"] = gr.HTML(
            value="",
            html_template="""
            <div class="node-output" data-node="${node_name}">
                <h3>${node_name}</h3>
                <div class="status">Pending</div>
                <div class="result">{{result}}</div>
            </div>
            """,
            css_template="""
            .node-output {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
                margin: 8px 0;
                background: #f9f9f9;
            }
            .node-output h3 {
                margin: 0 0 8px 0;
                color: #333;
            }
            .status {
                font-weight: bold;
                margin: 8px 0;
            }
            .result {
                margin-top: 8px;
                padding: 8px;
                background: white;
                border-radius: 4px;
            }
            """,
            node_name=node_name,
            result="",
        )

        return components

    def _format_result(self, result: Any) -> str:
        if result is None:
            return "<p>No output</p>"
        if isinstance(result, (list, tuple)):
            if len(result) == 0:
                return "<p>Empty result</p>"
            if len(result) == 1:
                return self._format_result(result[0])
            return f"<p>{len(result)} outputs</p>"
        if isinstance(result, dict):
            items = [f"<li><strong>{k}:</strong> {str(v)[:100]}</li>" for k, v in result.items()]
            return f"<ul>{''.join(items)}</ul>"
        result_str = str(result)
        if len(result_str) > 200:
            result_str = result_str[:200] + "..."
        return f"<p>{result_str}</p>"

    def _update_node_output(self, node_name: str, result: Any, status: str = "completed"):
        node = self.workflow.nodes[node_name]
        formatted_result = self._format_result(result)

        return gr.HTML(
            node_name=node_name,
            result=formatted_result,
            html_template="""
            <div class="node-output" data-node="${node_name}">
                <h3>${node_name}</h3>
                <div class="status status-${status}">${status}</div>
                <div class="result">{{result}}</div>
            </div>
            """,
            css_template="""
            .node-output {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 16px;
                margin: 8px 0;
                background: #f9f9f9;
            }
            .node-output h3 {
                margin: 0 0 8px 0;
                color: #333;
            }
            .status {
                font-weight: bold;
                margin: 8px 0;
            }
            .status-completed {
                color: #4caf50;
            }
            .status-pending {
                color: #ff9800;
            }
            .status-error {
                color: #f44336;
            }
            .result {
                margin-top: 8px;
                padding: 8px;
                background: white;
                border-radius: 4px;
            }
            """,
        )

    def _execute_workflow(self, *args):
        execution_order = self.workflow.get_execution_order()
        
        input_components_map = {}
        input_idx = 0
        for node_name in execution_order:
            node = self.workflow.nodes[node_name]
            if node.is_interaction_point or self.workflow.graph.in_degree(node_name) == 0:
                if node.inputs:
                    for idx, param in enumerate(node.inputs):
                        param_name = param.get("label") or param.get("name") or f"input_{idx}"
                        input_components_map[input_idx] = (node_name, param_name)
                        input_idx += 1
                else:
                    input_components_map[input_idx] = (node_name, None)
                    input_idx += 1

        input_values = {}
        for idx, arg_value in enumerate(args):
            if idx in input_components_map:
                node_name, param_name = input_components_map[idx]
                if node_name not in input_values:
                    input_values[node_name] = {}
                if param_name:
                    input_values[node_name][param_name] = arg_value
                else:
                    input_values[node_name] = arg_value

        outputs = []
        self.executor.results = {}

        try:
            for node_name in execution_order:
                node = self.workflow.nodes[node_name]
                user_input = input_values.get(node_name, {})
                if not isinstance(user_input, dict) and user_input is not None:
                    user_input = {"input": user_input}
                result = self.executor.execute_node(node_name, user_input)
                outputs.append(self._update_node_output(node_name, result, "completed"))
        except Exception as e:
            error_node = execution_order[len(self.executor.results)] if self.executor.results else execution_order[0]
            outputs.append(self._update_node_output(error_node, str(e), "error"))
            for remaining_node in execution_order[len(self.executor.results) + 1 :]:
                outputs.append(self._update_node_output(remaining_node, "", "pending"))

        while len(outputs) < len(execution_order):
            outputs.append(gr.HTML(value=""))

        return tuple(outputs)

    def generate_ui(self) -> gr.Blocks:
        with gr.Blocks(title=self.workflow.name) as demo:
            gr.Markdown(f"# {self.workflow.name}")

            execution_order = self.workflow.get_execution_order()
            input_components = []
            output_components = []

            for node_name in execution_order:
                node = self.workflow.nodes[node_name]
                node_ui = self._create_node_ui(node_name)

                if node.is_interaction_point or self.workflow.graph.in_degree(node_name) == 0:
                    for key, component in node_ui.items():
                        if "input" in key:
                            input_components.append(component)

                for key, component in node_ui.items():
                    if "output" in key:
                        output_components.append(component)

            if input_components:
                run_btn = gr.Button("Run Workflow", variant="primary")
                run_btn.click(
                    fn=self._execute_workflow,
                    inputs=input_components,
                    outputs=output_components,
                )
            else:
                gr.Markdown("No input nodes found in workflow")

        return demo

