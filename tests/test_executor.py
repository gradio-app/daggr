from daggr import FnNode, Graph
from daggr.executor import SequentialExecutor


class TestSequentialExecutor:
    def test_execute_single_fn_node(self):
        def double(x):
            return x * 2

        node = FnNode(double, inputs={"x": 5})
        graph = Graph("test", nodes=[node])
        executor = SequentialExecutor(graph)
        result = executor.execute_node("double", {})
        assert result["output"] == 10

    def test_execute_chain(self):
        def step1(x):
            return x + 1

        def step2(y):
            return y * 2

        n1 = FnNode(step1, inputs={"x": 10})
        n2 = FnNode(step2, inputs={"y": n1.output})
        graph = Graph("test", nodes=[n2])
        executor = SequentialExecutor(graph)
        executor.execute_node("step1", {})
        result = executor.execute_node("step2", {})
        assert result["output"] == 22

    def test_execute_all(self):
        def add_one(x):
            return x + 1

        def double(x):
            return x * 2

        n1 = FnNode(add_one, name="add_one", inputs={"x": 3})
        n2 = FnNode(double, name="double", inputs={"x": n1.output})
        graph = Graph("test", nodes=[n2])
        executor = SequentialExecutor(graph)
        results = executor.execute_all({})
        assert results["add_one"]["output"] == 4
        assert results["double"]["output"] == 8

    def test_fn_result_mapping_tuple(self):
        def multi_output(x):
            return (x, x * 2)

        node = FnNode(
            multi_output, inputs={"x": 5}, outputs={"first": None, "second": None}
        )
        graph = Graph("test", nodes=[node])
        executor = SequentialExecutor(graph)
        result = executor.execute_node("multi_output", {})
        assert result["first"] == 5
        assert result["second"] == 10

    def test_user_input_override(self):
        def process(text):
            return text.upper()

        node = FnNode(process, inputs={"text": "default"})
        graph = Graph("test", nodes=[node])
        executor = SequentialExecutor(graph)
        result = executor.execute_node("process", {"text": "hello"})
        assert result["output"] == "HELLO"

    def test_callable_fixed_input(self):
        counter = {"value": 0}

        def get_next():
            counter["value"] += 1
            return counter["value"]

        def process(x):
            return x

        node = FnNode(process, inputs={"x": get_next})
        graph = Graph("test", nodes=[node])
        executor = SequentialExecutor(graph)
        result1 = executor.execute_node("process", {})
        result2 = executor.execute_node("process", {})
        assert result1["output"] == 1
        assert result2["output"] == 2


class TestDownloadFileAuth:
    def test_sends_auth_header_when_token_provided(self, tmp_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio data"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        with (
            patch("httpx.Client", return_value=mock_client),
            patch("daggr.state.get_daggr_files_dir", return_value=tmp_path),
        ):
            result = _download_file(
                "https://my-private-space.hf.space/file=audio.wav",
                hf_token="hf_test_token_123",
            )

        mock_client.get.assert_called_once()
        _, kwargs = mock_client.get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer hf_test_token_123"
        assert result.endswith(".wav")

    def test_no_auth_header_without_token(self, tmp_path):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"public file data"

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        with (
            patch("httpx.Client", return_value=mock_client),
            patch("daggr.state.get_daggr_files_dir", return_value=tmp_path),
        ):
            _download_file("https://public-space.hf.space/file=image.png")

        mock_client.get.assert_called_once()
        _, kwargs = mock_client.get.call_args
        assert kwargs["headers"] == {}
