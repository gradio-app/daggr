from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path


def find_python_imports(file_path: Path) -> list[Path]:
    """Find local Python files imported by the given file."""
    imports = []
    try:
        with open(file_path) as f:
            content = f.read()

        import ast

        tree = ast.parse(content)

        file_dir = file_path.parent

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_path = file_dir / f"{alias.name.replace('.', '/')}.py"
                    if module_path.exists():
                        imports.append(module_path)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_path = file_dir / f"{node.module.replace('.', '/')}.py"
                    if module_path.exists():
                        imports.append(module_path)
                    package_init = (
                        file_dir / node.module.replace(".", "/") / "__init__.py"
                    )
                    if package_init.exists():
                        imports.append(package_init.parent)
    except Exception:
        pass
    return imports


def main():
    parser = argparse.ArgumentParser(
        prog="daggr",
        description="Run a daggr app with hot reload",
    )
    parser.add_argument(
        "script",
        help="Path to the Python script containing the daggr Graph",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="Port to bind to (default: 7860)",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload",
    )
    parser.add_argument(
        "--watch-daggr",
        action="store_true",
        default=True,
        help="Watch daggr source for changes (default: True, useful for development)",
    )
    parser.add_argument(
        "--no-watch-daggr",
        action="store_true",
        help="Don't watch daggr source for changes",
    )
    parser.add_argument(
        "--reset-cache",
        action="store_true",
        help="Delete all cached data (sheets, results, downloaded files) for this project and exit",
    )

    args = parser.parse_args()

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        sys.exit(1)

    if not script_path.suffix == ".py":
        print(f"Error: Script must be a Python file: {script_path}")
        sys.exit(1)

    if args.reset_cache:
        _reset_cache(script_path)
        sys.exit(0)

    watch_daggr = args.watch_daggr and not args.no_watch_daggr

    os.environ["DAGGR_SCRIPT_PATH"] = str(script_path)
    os.environ["DAGGR_HOST"] = args.host
    os.environ["DAGGR_PORT"] = str(args.port)

    if args.no_reload:
        _run_script(script_path, args.host, args.port)
    else:
        os.environ["DAGGR_HOT_RELOAD"] = "1"
        _run_with_reload(script_path, args.host, args.port, watch_daggr)


def _reset_cache(script_path: Path):
    """Delete all cached data for the project defined in the script."""
    import sqlite3

    from daggr.graph import Graph
    from daggr.state import get_daggr_cache_dir

    sys.path.insert(0, str(script_path.parent))

    original_launch = Graph.launch
    captured_graph = None

    def capture_launch(self, **kwargs):
        nonlocal captured_graph
        captured_graph = self

    Graph.launch = capture_launch

    try:
        spec = importlib.util.spec_from_file_location("__daggr_reset__", script_path)
        if spec is None or spec.loader is None:
            print(f"Error: Could not load script: {script_path}")
            sys.exit(1)

        module = importlib.util.module_from_spec(spec)
        sys.modules["__daggr_reset__"] = module
        spec.loader.exec_module(module)
    finally:
        Graph.launch = original_launch

    if captured_graph is None:
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, Graph):
                captured_graph = obj
                break

    if captured_graph is None:
        print(f"Error: No Graph found in {script_path}")
        sys.exit(1)

    persist_key = captured_graph.persist_key
    if not persist_key:
        print(f"Error: Graph has no persist_key (persistence is disabled)")
        sys.exit(1)

    cache_dir = get_daggr_cache_dir()
    db_path = cache_dir / "sessions.db"

    if not db_path.exists():
        print(f"No cache found for project '{persist_key}'")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        "SELECT sheet_id FROM sheets WHERE graph_name = ?",
        (persist_key,),
    )
    sheet_ids = [row[0] for row in cursor.fetchall()]

    if not sheet_ids:
        print(f"No cached data found for project '{persist_key}'")
        conn.close()
        return

    print(f"\nProject: {persist_key}")
    print(f"This will delete {len(sheet_ids)} sheet(s) and all associated data.")
    print(f"Cache location: {cache_dir}\n")

    try:
        response = input("Are you sure you want to continue? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        conn.close()
        return

    if response not in ("y", "yes"):
        print("Aborted.")
        conn.close()
        return

    for sheet_id in sheet_ids:
        cursor.execute("DELETE FROM node_inputs WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM node_results WHERE sheet_id = ?", (sheet_id,))
        cursor.execute("DELETE FROM sheets WHERE sheet_id = ?", (sheet_id,))

    conn.commit()
    conn.close()

    print(f"\n✓ Deleted {len(sheet_ids)} sheet(s) for project '{persist_key}'")


def _run_script(script_path: Path, host: str, port: int):
    """Run the script directly without reload."""
    spec = importlib.util.spec_from_file_location("__daggr_main__", script_path)
    if spec is None or spec.loader is None:
        print(f"Error: Could not load script: {script_path}")
        sys.exit(1)

    sys.path.insert(0, str(script_path.parent))

    module = importlib.util.module_from_spec(spec)
    sys.modules["__daggr_main__"] = module
    spec.loader.exec_module(module)


def _run_with_reload(script_path: Path, host: str, port: int, watch_daggr: bool):
    """Run the script with uvicorn hot reload."""
    import uvicorn

    reload_dirs = [str(script_path.parent)]

    local_imports = find_python_imports(script_path)
    for imp in local_imports:
        imp_dir = str(imp if imp.is_dir() else imp.parent)
        if imp_dir not in reload_dirs:
            reload_dirs.append(imp_dir)

    if watch_daggr:
        daggr_dir = Path(__file__).parent
        daggr_src = str(daggr_dir)
        if daggr_src not in reload_dirs:
            reload_dirs.append(daggr_src)

    reload_includes = ["*.py"]

    print("\n  daggr dev server starting...")
    print("  Watching for changes in:")
    for d in reload_dirs:
        print(f"    • {d}")
    print()

    uvicorn.run(
        "daggr.cli:_create_app",
        factory=True,
        host=host,
        port=port,
        reload=True,
        reload_dirs=reload_dirs,
        reload_includes=reload_includes,
        log_level="warning",
    )


def _create_app():
    """Factory function for uvicorn to create the FastAPI app."""
    import importlib.util
    import sys
    from pathlib import Path

    from daggr.graph import Graph
    from daggr.server import DaggrServer

    script_path = Path(os.environ["DAGGR_SCRIPT_PATH"])

    if str(script_path.parent) not in sys.path:
        sys.path.insert(0, str(script_path.parent))

    modules_to_remove = [m for m in sys.modules if m.startswith("__daggr_user_script_")]
    for m in modules_to_remove:
        del sys.modules[m]

    module_name = f"__daggr_user_script_{id(script_path)}__"

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script: {script_path}")

    original_launch = Graph.launch
    captured_graph = None
    launch_kwargs = {}

    def capture_launch(self, **kwargs):
        nonlocal captured_graph, launch_kwargs
        captured_graph = self
        launch_kwargs = kwargs

    Graph.launch = capture_launch

    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        Graph.launch = original_launch

    if captured_graph is None:
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, Graph):
                captured_graph = obj
                break

    if captured_graph is None:
        raise RuntimeError(
            f"No Graph found in {script_path}. "
            "Make sure your script defines a Graph and calls graph.launch() "
            "or has a Graph instance at module level."
        )

    captured_graph._validate_edges()
    server = DaggrServer(captured_graph)

    print(
        f"\n  daggr running at http://{os.environ['DAGGR_HOST']}:{os.environ['DAGGR_PORT']}\n"
    )

    return server.app


if __name__ == "__main__":
    main()
