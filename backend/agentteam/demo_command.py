"""One-command first proof: real Agent Team UI, synthetic provider-free work record."""
from __future__ import annotations

import argparse
import asyncio
import tempfile
import threading
import webbrowser
from pathlib import Path

from .api.app import create_app
from .api.service import AppService
from .demo import seed_offline_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentteam-demo",
        description="Open a synthetic offline Agent Team run in the real local UI. No model/API key/external action is used.",
    )
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data-dir", type=Path, help="persist the synthetic demo here; default is a temporary directory")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    if args.data_dir:
        args.data_dir.mkdir(parents=True, exist_ok=True)
        return _serve(args.data_dir, args.port, args.no_browser)
    with tempfile.TemporaryDirectory(prefix="agentteam-demo-") as temp:
        return _serve(Path(temp), args.port, args.no_browser)


def _seed(data_dir: Path) -> str:
    async def prepare() -> str:
        service = await AppService(data_dir).start()
        try:
            return await seed_offline_demo(service)
        finally:
            await service.stop()

    return asyncio.run(prepare())


def _serve(data_dir: Path, port: int, no_browser: bool) -> int:
    import uvicorn

    run_id = _seed(data_dir)
    url = f"http://127.0.0.1:{port}/"
    print("Agent Team — 30-second offline demo")
    print("REAL UI / SYNTHETIC WORK RECORD / MODEL CALLS 0 / EXTERNAL ACTIONS 0")
    print(f"demo_run={run_id}")
    print(f"open={url}")
    print("The seeded run is explicitly marked synthetic_offline_demo in its report and event log.")
    if not no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(AppService(data_dir)), host="127.0.0.1", port=port, log_level="warning", proxy_headers=False, access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
