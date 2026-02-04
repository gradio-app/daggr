from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import socket
import sys
import tempfile
from pathlib import Path

INITIAL_PORT_VALUE = int(os.getenv("DAGGR_SERVER_PORT", "7860"))
TRY_NUM_PORTS = int(os.getenv("DAGGR_NUM_PORTS", "100"))


def _find_available_port(host: str, start_port: int) -> int:
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + TRY_NUM_PORTS):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host if host != "0.0.0.0" else "127.0.0.1", port))
            s.close()
            return port
        except OSError:
            continue
    raise OSError(
        f"Cannot find empty port in range: {start_port}-{start_port + TRY_NUM_PORTS - 1}. "
        f"You can specify a different port by setting the DAGGR_SERVER_PORT environment variable "
        f"or passing the --port parameter."
    )


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
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        _deploy_main()
        return

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
        "--delete-sheets",
        action="store_true",
        help="Delete all cached data (sheets, results, downloaded files) for this project and exit",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompts (use with --delete-sheets)",
    )
    parser.add_argument(
        "--state-db-path",
        help="Optional path to SQLite state database. Overrides DAGGR_DB_PATH env var. Defaults to HuggingFace cache.",
    )

    args = parser.parse_args()

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        sys.exit(1)

    if not script_path.suffix == ".py":
        print(f"Error: Script must be a Python file: {script_path}")
        sys.exit(1)

    if args.delete_sheets:
        _delete_sheets(script_path, force=args.force)
        sys.exit(0)

    watch_daggr = args.watch_daggr and not args.no_watch_daggr

    os.environ["DAGGR_SCRIPT_PATH"] = str(script_path)
    os.environ["DAGGR_HOST"] = args.host
    os.environ["DAGGR_PORT"] = str(args.port)
    if args.state_db_path:
        os.environ["DAGGR_DB_PATH"] = str(Path(args.state_db_path).resolve())

    if args.no_reload:
        _run_script(script_path, args.host, args.port)
    else:
        os.environ["DAGGR_HOT_RELOAD"] = "1"
        _run_with_reload(script_path, args.host, args.port, watch_daggr)


def _deploy_main():
    """Entry point for the deploy subcommand."""
    parser = argparse.ArgumentParser(
        prog="daggr deploy",
        description="Deploy a daggr app to Hugging Face Spaces",
    )
    parser.add_argument(
        "script",
        help="Path to the Python script containing the daggr Graph",
    )
    parser.add_argument(
        "--name",
        "-n",
        help="Space name (default: derived from Graph name)",
    )
    parser.add_argument(
        "--title",
        "-t",
        help="Display title for the Space (default: Graph name)",
    )
    parser.add_argument(
        "--org",
        "-o",
        help="Organization or username to deploy under (default: your HF account)",
    )
    parser.add_argument(
        "--private",
        "-p",
        action="store_true",
        help="Make the Space private",
    )
    parser.add_argument(
        "--hardware",
        default="cpu-basic",
        help="Hardware tier (default: cpu-basic). Options: cpu-basic, cpu-upgrade, t4-small, t4-medium, a10g-small, etc.",
    )
    parser.add_argument(
        "--secret",
        "-s",
        action="append",
        dest="secrets",
        metavar="KEY=VALUE",
        help="Add a secret (can be repeated). Example: --secret HF_TOKEN=xxx",
    )
    parser.add_argument(
        "--requirements",
        "-r",
        help="Path to requirements.txt (default: auto-detect or generate)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deployed without actually deploying",
    )

    args = parser.parse_args(sys.argv[2:])

    script_path = Path(args.script).resolve()
    if not script_path.exists():
        print(f"Error: Script not found: {script_path}")
        sys.exit(1)

    if not script_path.suffix == ".py":
        print(f"Error: Script must be a Python file: {script_path}")
        sys.exit(1)

    secrets = {}
    if args.secrets:
        for secret in args.secrets:
            if "=" not in secret:
                print(f"Error: Invalid secret format '{secret}'. Use KEY=VALUE")
                sys.exit(1)
            key, value = secret.split("=", 1)
            secrets[key] = value

    _deploy(
        script_path=script_path,
        name=args.name,
        title=args.title,
        org=args.org,
        private=args.private,
        hardware=args.hardware,
        secrets=secrets,
        requirements_path=args.requirements,
        dry_run=args.dry_run,
    )


def _extract_graph(script_path: Path):
    """Extract the Graph object from a script without running it."""
    from daggr.graph import Graph

    sys.path.insert(0, str(script_path.parent))

    original_launch = Graph.launch
    captured_graph = None

    def capture_launch(self, **kwargs):
        nonlocal captured_graph
        captured_graph = self

    Graph.launch = capture_launch

    try:
        spec = importlib.util.spec_from_file_location("__daggr_deploy__", script_path)
        if spec is None or spec.loader is None:
            print(f"Error: Could not load script: {script_path}")
            sys.exit(1)

        module = importlib.util.module_from_spec(spec)
        sys.modules["__daggr_deploy__"] = module
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

    return captured_graph


def _sanitize_space_name(name: str) -> str:
    """Convert a Graph name to a valid HF Space name."""
    sanitized = re.sub(r"[^a-zA-Z0-9\s-]", "", name)
    sanitized = re.sub(r"[\s_]+", "-", sanitized)
    sanitized = sanitized.lower().strip("-")
    return sanitized or "daggr-app"


def _deploy(
    script_path: Path,
    name: str | None,
    title: str | None,
    org: str | None,
    private: bool,
    hardware: str,
    secrets: dict[str, str],
    requirements_path: str | None,
    dry_run: bool,
):
    """Deploy a daggr app to Hugging Face Spaces."""
    import huggingface_hub
    from huggingface_hub import HfApi

    import daggr

    print("\n  Extracting Graph from script...")
    graph = _extract_graph(script_path)

    space_name = name or _sanitize_space_name(graph.name)
    space_title = title or graph.name

    print(f"  Graph name: {graph.name}")
    print(f"  Space name: {space_name}")
    print(f"  Space title: {space_title}")

    hf_api = HfApi()
    whoami = None
    login_needed = False

    try:
        whoami = hf_api.whoami()
        if whoami["auth"]["accessToken"]["role"] != "write":
            login_needed = True
    except Exception:
        login_needed = True

    if login_needed:
        print("\n  Need 'write' access token to create a Spaces repo.")
        huggingface_hub.login(add_to_git_credential=False)
        whoami = hf_api.whoami()

    username = whoami["name"]
    namespace = org or username
    repo_id = f"{namespace}/{space_name}"

    print(f"\n  Target: https://huggingface.co/spaces/{repo_id}")
    print(f"  Hardware: {hardware}")
    print(f"  Private: {private}")
    if secrets:
        print(f"  Secrets: {list(secrets.keys())}")

    local_imports = find_python_imports(script_path)
    print("\n  Files to upload:")
    print(f"    • app.py (from {script_path.name})")
    print("    • requirements.txt")
    print("    • README.md")
    for imp in local_imports:
        if imp.is_file():
            print(f"    • {imp.name}")
        else:
            print(f"    • {imp.name}/ (package)")

    if dry_run:
        print("\n  [Dry run] No changes made.")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        shutil.copy(script_path, tmpdir / "app.py")

        for imp in local_imports:
            if imp.is_file():
                shutil.copy(imp, tmpdir / imp.name)
            else:
                shutil.copytree(imp, tmpdir / imp.name)

        if requirements_path:
            req_path = Path(requirements_path)
            if not req_path.exists():
                print(f"Error: Requirements file not found: {req_path}")
                sys.exit(1)
            shutil.copy(req_path, tmpdir / "requirements.txt")

            with open(tmpdir / "requirements.txt", "r") as f:
                req_content = f.read()
            if "daggr" not in req_content:
                with open(tmpdir / "requirements.txt", "a") as f:
                    f.write(f"\ndaggr>={daggr.__version__}\n")
        else:
            script_dir = script_path.parent
            existing_req = script_dir / "requirements.txt"
            if existing_req.exists():
                shutil.copy(existing_req, tmpdir / "requirements.txt")
                with open(tmpdir / "requirements.txt", "r") as f:
                    req_content = f.read()
                if "daggr" not in req_content:
                    with open(tmpdir / "requirements.txt", "a") as f:
                        f.write(f"\ndaggr>={daggr.__version__}\n")
            else:
                with open(tmpdir / "requirements.txt", "w") as f:
                    f.write(f"daggr>={daggr.__version__}\n")

        readme_content = f"""---
title: {space_title}
emoji: 🔀
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: "{_get_gradio_version()}"
app_file: app.py
pinned: false
tags:
  - daggr
---

# {space_title}

This Space was deployed using [daggr](https://github.com/gradio-app/daggr).
"""
        with open(tmpdir / "README.md", "w") as f:
            f.write(readme_content)

        print("\n  Creating Space repository...")
        try:
            hf_api.create_repo(
                repo_id=repo_id,
                repo_type="space",
                space_sdk="gradio",
                space_hardware=hardware,
                private=private,
                exist_ok=True,
            )
        except Exception as e:
            print(f"Error creating repository: {e}")
            sys.exit(1)

        print("  Uploading files...")
        try:
            hf_api.upload_folder(
                repo_id=repo_id,
                repo_type="space",
                folder_path=str(tmpdir),
            )
        except Exception as e:
            print(f"Error uploading files: {e}")
            sys.exit(1)

        if secrets:
            print("  Adding secrets...")
            for secret_name, secret_value in secrets.items():
                try:
                    hf_api.add_space_secret(repo_id, secret_name, secret_value)
                except Exception as e:
                    print(f"  Warning: Could not add secret '{secret_name}': {e}")

    print(f"\n  ✓ Deployed to https://huggingface.co/spaces/{repo_id}")
    print("    The Space may take a few minutes to build and start.\n")


def _get_gradio_version() -> str:
    """Get the installed Gradio version."""
    try:
        import gradio

        return gradio.__version__
    except ImportError:
        return "5.0.0"


def _delete_sheets(script_path: Path, force: bool = False):
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
        print("Error: Graph has no persist_key (persistence is disabled)")
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

    if not force:
        try:
            response = (
                input("Are you sure you want to continue? [y/N] ").strip().lower()
            )
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

    actual_port = _find_available_port(host, port)
    if actual_port != port:
        print(f"\n  Port {port} is in use, using {actual_port} instead.")

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

    os.environ["DAGGR_PORT"] = str(actual_port)

    import threading
    import webbrowser

    def open_browser():
        import time

        time.sleep(1.0)
        webbrowser.open_new_tab(f"http://{host}:{actual_port}")

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(
        "daggr.cli:_create_app",
        factory=True,
        host=host,
        port=actual_port,
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
