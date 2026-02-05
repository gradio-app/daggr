import pytest

from daggr import FnNode, Graph, InteractionNode
from daggr.port import ItemList, Port, ScatteredPort


class TestComponentTypeWarning:
    def test_warns_when_type_explicitly_set(self):
        import gradio as gr

        with pytest.warns(UserWarning, match="daggr ignores the `type` parameter"):
            FnNode(
                lambda image: image,
                inputs={"image": gr.Image(type="numpy")},
                outputs={"output": None},
            )

    def test_no_warning_when_type_not_set(self):
        import warnings

        import gradio as gr

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            FnNode(
                lambda image: image,
                inputs={"image": gr.Image(label="Input")},
                outputs={"output": None},
            )


class TestFnNode:
    def test_creates_from_function(self):
        def my_func(x: str, y: int) -> dict:
            return {"result": f"{x}-{y}"}

        node = FnNode(my_func)
        assert node._name == "my_func"
        assert "x" in node._input_ports
        assert "y" in node._input_ports
        assert "output" in node._output_ports

    def test_custom_name(self):
        def process(data):
            return {"out": data}

        node = FnNode(process, name="CustomProcessor")
        assert node._name == "CustomProcessor"

    def test_explicit_inputs(self):
        def process(a, b, c):
            return {"out": a + b + c}

        node = FnNode(process, inputs={"a": "fixed_value", "b": None})
        assert "a" in node._input_ports
        assert "b" in node._input_ports
        assert node._fixed_inputs["a"] == "fixed_value"

    def test_invalid_input_raises_error(self):
        def process(text):
            return {"out": text}

        with pytest.raises(ValueError) as exc:
            FnNode(process, inputs={"wrong_name": "value"})
        assert "wrong_name" in str(exc.value)

    def test_item_list_output(self):
        def generate_items(prompt):
            return {"items": [{"text": "a"}, {"text": "b"}]}

        node = FnNode(generate_items, outputs={"items": ItemList(text=None)})
        assert "items" in node._output_ports
        assert "items" in node._item_list_schemas
        assert "text" in node._item_list_schemas["items"]


class TestInteractionNode:
    def test_default_ports(self):
        node = InteractionNode()
        assert "input" in node._input_ports
        assert "output" in node._output_ports

    def test_custom_interaction_type(self):
        node = InteractionNode(interaction_type="approve")
        assert node._interaction_type == "approve"


class TestPort:
    def test_port_access(self):
        def process(x):
            return {"y": x}

        node = FnNode(process)
        port = node.x
        assert isinstance(port, Port)
        assert port.name == "x"
        assert port.node is node

    def test_scattered_port(self):
        def process(x):
            return {"items": [1, 2, 3]}

        node = FnNode(process, outputs={"items": None})
        scattered = node.items.each
        assert isinstance(scattered, ScatteredPort)
        assert scattered.name == "items"

    def test_scattered_port_with_key(self):
        def process(x):
            return {"items": [{"a": 1}, {"a": 2}]}

        node = FnNode(process, outputs={"items": ItemList(a=None)})
        scattered = node.items.a
        assert isinstance(scattered, ScatteredPort)
        assert scattered.item_key == "a"


class TestGraphConstruction:
    def test_requires_name(self):
        with pytest.raises(ValueError):
            Graph(name="")
        with pytest.raises(ValueError):
            Graph(name=None)

    def test_persist_key_derived_from_name(self):
        graph = Graph(name="My Cool App!")
        assert graph.persist_key == "my_cool_app"

    def test_persist_key_disabled(self):
        graph = Graph(name="Test", persist_key=False)
        assert graph.persist_key is None

    def test_persist_key_custom(self):
        graph = Graph(name="Display Name", persist_key="custom_key")
        assert graph.persist_key == "custom_key"

    def test_add_nodes_from_init(self):
        def step_a(x):
            return {"output": x}

        def step_b(y):
            return {"output": y}

        n1 = FnNode(step_a)
        n2 = FnNode(step_b, inputs={"y": n1.output})
        graph = Graph("test", nodes=[n2])
        assert "step_a" in graph.nodes
        assert "step_b" in graph.nodes

    def test_cycle_detection(self):
        def step_a(x):
            return {"out": x}

        def step_b(y):
            return {"out": y}

        n1 = FnNode(step_a)
        n2 = FnNode(step_b)
        graph = Graph("test", nodes=[n1, n2])
        graph.edge(n1.out, n2.y)
        with pytest.raises(ValueError, match="cycle"):
            graph.edge(n2.out, n1.x)

    def test_execution_order(self):
        def a(x):
            return {"output": x}

        def b(y):
            return {"output": y}

        def c(z):
            return {"output": z}

        n1 = FnNode(a, name="first")
        n2 = FnNode(b, name="second")
        n3 = FnNode(c, name="third")
        graph = Graph("test", nodes=[n1, n2, n3])
        graph.edge(n1.output, n2.y)
        graph.edge(n2.output, n3.z)
        order = graph.get_execution_order()
        assert order.index("first") < order.index("second")
        assert order.index("second") < order.index("third")

    def test_get_connections(self):
        def a(x):
            return {"output": x}

        def b(y):
            return {"output": y}

        n1 = FnNode(a)
        n2 = FnNode(b, inputs={"y": n1.output})
        graph = Graph("test", nodes=[n2])
        connections = graph.get_connections()
        assert len(connections) == 1
        assert connections[0] == ("a", "output", "b", "y")
