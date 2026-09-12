"""CLI: serve | validate | probe | run."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .api.service import AppService
from .config.loader import DEFAULT_CONFIG_YAML, load_config_text
from .contracts import RunInputs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="agentteam")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="start the API + UI server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--data-dir", default=None)
    v = sub.add_parser("validate", help="validate a config file (default: data/agents.yaml)")
    v.add_argument("path", nargs="?")
    pr = sub.add_parser("probe", help="run a real capability probe against a connection (costs a few hundred tokens)")
    pr.add_argument("connection", nargs="?")
    pr.add_argument("--model")
    pr.add_argument("--data-dir", default=None)
    q = sub.add_parser("quickstart", help="probe the default connection if needed, then serve and open the browser")
    q.add_argument("--port", type=int, default=8787)
    q.add_argument("--data-dir", default=None)
    q.add_argument("--no-browser", action="store_true")
    r = sub.add_parser("run", help="run one request end to end and print the report path")
    r.add_argument("goal")
    r.add_argument("--url", action="append", default=[])
    r.add_argument("--text", default="")
    r.add_argument("--budget", type=float, default=None)
    r.add_argument("--data-dir", default=None)
    args = p.parse_args(argv)

    if args.cmd == "serve":
        import uvicorn
        from .api.app import create_app
        svc = AppService(args.data_dir)
        uvicorn.run(create_app(svc), host=args.host, port=args.port, log_level="info")
        return 0
    if args.cmd == "validate":
        path = Path(args.path) if args.path else Path("data/agents.yaml")
        text = path.read_text(encoding="utf-8") if path.is_file() else DEFAULT_CONFIG_YAML
        cfg = load_config_text(text)
        print(json.dumps({"ok": True, "profile": cfg.profile_name, "agents": [a.id for a in cfg.agents],
                          "connections": [c.id for c in cfg.connections]}, ensure_ascii=False))
        return 0
    if args.cmd == "probe":
        return asyncio.run(_probe(args))
    if args.cmd == "quickstart":
        return _quickstart(args)
    if args.cmd == "run":
        return asyncio.run(_run(args))
    return 1


async def _probe(args) -> int:
    from .providers.registry import ProviderRegistry
    svc = await AppService(args.data_dir).start()
    try:
        cid = args.connection or svc.config.defaults.connection_id
        model = args.model or svc.config.defaults.model
        reg = ProviderRegistry(svc.config)
        try:
            res = await reg.adapter(cid).probe(model)
        finally:
            await reg.aclose()
        print(json.dumps(res.__dict__, default=lambda o: o.__dict__, ensure_ascii=False, indent=1))
        cfg = svc.config.model_copy(deep=True)
        c = cfg.connection(cid)
        c.capability_check = "passed" if res.ok else "failed"
        c.capability_detail = {"model_requested": res.model_requested, "model_reported": res.model_reported,
                               "tool_calling": res.tool_calling, "json_schema": res.json_schema, "error": res.error}
        await svc.save_config(cfg, f"probe {cid}:{model}")
        return 0 if res.ok else 2
    finally:
        await svc.stop()


async def _run(args) -> int:
    svc = await AppService(args.data_dir).start()
    try:
        run, problems = await svc.manager.create_run(args.goal, RunInputs(text=args.text, urls=args.url), budget_usd=args.budget)
        if problems:
            print(json.dumps({"blocked": problems}, ensure_ascii=False, indent=1))
            return 2
        print(f"run_id={run.run_id}")
        svc.manager.start(run.run_id)
        run = await svc.manager.wait(run.run_id)
        final = await svc.artifacts.get(run.run_id, "final-report.md")
        print(json.dumps({"status": run.status, "usage": run.usage.model_dump(),
                          "report": str(svc.artifacts.root / final.storage_path) if final else None}, ensure_ascii=False, indent=1))
        return 0 if run.status == "completed" else 1
    finally:
        await svc.stop()


if __name__ == "__main__":
    sys.exit(main())


def _quickstart(args) -> int:
    """First run in one command: probe (real call) → serve → open the browser."""
    import shutil
    import threading
    import webbrowser
    import uvicorn
    from .api.app import create_app

    async def _prepare() -> tuple[AppService, bool]:
        svc = await AppService(args.data_dir).start()
        cid = svc.config.defaults.connection_id
        conn = svc.config.connection(cid)
        ok = conn is not None and conn.capability_check == "passed"
        if not ok and conn is not None:
            if conn.driver == "claude_cli" and shutil.which("claude") is None:
                print("claude CLI not found. Install Claude Code (https://claude.com/claude-code), run `claude` once to log in, then retry.")
            else:
                print(f"Probing connection {cid} ({conn.driver}) with model {svc.config.defaults.model} — one small real call…", flush=True)
                from .providers.registry import ProviderRegistry
                reg = ProviderRegistry(svc.config)
                try:
                    res = await reg.adapter(cid).probe(svc.config.defaults.model)
                except Exception as e:  # keep going: the UI shows the structured reason
                    res = None
                    print(f"probe failed: {e}")
                finally:
                    await reg.aclose()
                if res is not None:
                    cfg = svc.config.model_copy(deep=True)
                    c = cfg.connection(cid)
                    c.capability_check = "passed" if res.ok else "failed"
                    c.capability_detail = {"model_requested": res.model_requested, "model_reported": res.model_reported,
                                           "tool_calling": res.tool_calling, "json_schema": res.json_schema, "error": res.error}
                    await svc.save_config(cfg, "quickstart probe")
                    ok = res.ok
                    print(f"probe: {'passed' if res.ok else 'failed'} (model reported: {res.model_reported}) {res.error or ''}")
        await svc.stop()
        return svc, ok

    svc, ok = asyncio.run(_prepare())
    url = f"http://127.0.0.1:{args.port}"
    print(f"Agent Team → {url}  ({'ready' if ok else 'open Settings to fix the connection'})", flush=True)
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(AppService(args.data_dir)), host="127.0.0.1", port=args.port, log_level="warning")
    return 0
