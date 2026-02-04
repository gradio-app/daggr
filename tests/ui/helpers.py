import os
import socket
import threading
import time

import uvicorn
from playwright.sync_api import Page

from daggr import Graph
from daggr.server import DaggrServer


def find_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass

    def run_in_thread(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        start = time.time()
        while not self.started:
            time.sleep(0.01)
            if time.time() - start > 10:
                raise RuntimeError("Server failed to start")

    def close(self):
        self.should_exit = True
        self.thread.join(timeout=5)


def launch_daggr_server(graph: Graph, temp_db: str) -> tuple[TestServer, str]:
    os.environ["DAGGR_DB_PATH"] = temp_db
    port = find_available_port()
    server = DaggrServer(graph)
    config = uvicorn.Config(
        app=server.app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    test_server = TestServer(config)
    test_server.run_in_thread()
    url = f"http://127.0.0.1:{port}"
    return test_server, url


def wait_for_graph_load(page: Page, timeout: int = 15000):
    page.wait_for_function(
        """() => {
            const status = document.querySelector('.connection-status');
            if (status) return false;
            const nodes = document.querySelectorAll('.node');
            return nodes.length > 0;
        }""",
        timeout=timeout,
    )
