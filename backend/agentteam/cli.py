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
    auth = sub.add_parser('access', help='issue, rotate or revoke an installation access key')
    auth.add_argument('--file', type=Path, required=True)
    auth.add_argument('--subject', required=True)
    auth.add_argument('--role', choices=['admin', 'operator', 'viewer', 'auditor'], default='operator')
    auth.add_argument('--credential-file', type=Path)
    auth.add_argument('--organization')
    auth.add_argument('--public-origin')
    auth.add_argument('--revoke', action='store_true')
    observer = sub.add_parser('observe', help='collect audit and readiness outside the application using an auditor key')
    observer.add_argument('--url', required=True)
    observer.add_argument('--private-backend', help='optional loopback HTTP backend; preserves the configured public Host')
    observer.add_argument('--credential-file', type=Path, required=True)
    observer.add_argument('--state-dir', type=Path, required=True)
    observer.add_argument('--interval', type=int, default=30)
    observer.add_argument('--once', action='store_true')
    purge = sub.add_parser('purge', help='preview or apply offline deletion of explicitly selected run data')
    purge.add_argument('--source', type=Path, required=True)
    purge.add_argument('--run-id', action='append', default=[])
    purge.add_argument('--before', help='exclusive UTC completion-date cutoff, YYYY-MM-DD; terminal runs only')
    purge.add_argument('--resume', action='store_true', help='finish an already recorded deletion')
    purge.add_argument('--apply', action='store_true', help='perform deletion; omitted means preview only')
    for command in ('seal-backup', 'unseal-backup'):
        enc = sub.add_parser(command, help='encrypt or verify/decrypt a snapshot with the age CLI')
        enc.add_argument('--source', type=Path, required=True)
        enc.add_argument('--destination', type=Path, required=True)
        enc.add_argument('--age-bin', default='age')
        if command == 'seal-backup':
            enc.add_argument('--recipients-file', type=Path, required=True)
        else:
            enc.add_argument('--identity-file', type=Path, required=True)
            enc.add_argument('--expected-sha256', required=True, help='SHA-256 from a separately trusted inventory')
            enc.add_argument('--max-bytes', type=int, default=10 * 1024**3)
    for command in ('backup', 'restore', 'verify-backup'):
        op = sub.add_parser(command, help='offline snapshot operation; existing destinations are never overwritten')
        op.add_argument('--source', type=Path, required=True)
        if command != 'verify-backup':
            op.add_argument('--destination', type=Path, required=True)
    args = p.parse_args(argv)
    if args.cmd == 'observe':
        import time
        from .operations.observer import Observer
        if not 5 <= args.interval <= 86400:
            p.error('--interval must be between 5 and 86400 seconds')
        collector = Observer(args.url, args.credential_file, args.state_dir, private_backend=args.private_backend)
        try:
            while True:
                result = collector.collect()
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if args.once:
                    return 0 if result['state'] == 'healthy' else 2
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0
    if args.cmd in ('seal-backup', 'unseal-backup'):
        from .operations.encrypted_backup import seal, unseal
        result = (seal(args.source, args.destination, args.recipients_file, age_bin=args.age_bin)
                  if args.cmd == 'seal-backup' else unseal(args.source, args.destination, args.identity_file,
                  expected_sha256=args.expected_sha256, age_bin=args.age_bin, max_bytes=args.max_bytes))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == 'purge':
        from .operations.retention import plan, purge
        if args.resume and not args.apply:
            p.error('--resume requires --apply')
        result = purge(args.source, run_ids=args.run_id, before=args.before, resume=args.resume) if args.apply else plan(args.source, run_ids=args.run_id, before=args.before)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "serve":
        import uvicorn
        from .api.app import create_app
        svc = AppService(args.data_dir)
        if args.host not in ('127.0.0.1', 'localhost', '::1') and not svc.access.enabled:
            p.error('binding outside loopback requires AGENTTEAM_ACCESS_FILE')
        uvicorn.run(create_app(svc), host=args.host, port=args.port, log_level="info", proxy_headers=False, access_log=False)
        return 0
    if args.cmd == 'access':
        from .security.accounts import issue_key
        if not args.revoke and args.credential_file is None:
            p.error('--credential-file is required; keys are never printed to stdout')
        issue_key(args.file, args.subject, args.role, args.credential_file or args.file,
                  organization=args.organization, public_origin=args.public_origin, revoke=args.revoke)
        print('access key revoked' if args.revoke else f'access key saved to {args.credential_file}')
        return 0
    if args.cmd in ('backup', 'restore', 'verify-backup'):
        from .operations.backup import backup, restore, verify
        result = verify(args.source) if args.cmd == 'verify-backup' else {'backup': backup, 'restore': restore}[args.cmd](args.source, args.destination)
        print(json.dumps(result, ensure_ascii=False, indent=2))
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


def _probe_hint(error: str) -> str | None:
    """A one-line next step for the most common first-run failures."""
    e = error.lower()
    if "not logged in" in e or "/login" in e:
        return "Run `claude` once in a terminal and log in, then retry."
    if "not found on path" in e:
        return "Install Claude Code (https://claude.com/claude-code) or set AGENTTEAM_CLAUDE_BIN to the binary."
    if "api key" in e or "authentication" in e or "401" in e:
        return "Set the API key the connection references (see api_key_ref in Settings)."
    return None


async def _probe(args) -> int:
    from .providers.registry import ProviderRegistry
    svc = await AppService(args.data_dir).start()
    try:
        cid = args.connection or svc.config.defaults.connection_id
        model = args.model or svc.config.defaults.model
        from .providers.base import ProviderError
        reg = ProviderRegistry(svc.config)
        try:
            res = await reg.adapter(cid).probe(model)
        except ProviderError as e:  # e.g. claude CLI not on PATH: a structured reason, not a traceback
            print(json.dumps({"ok": False, "connection": cid, "model_requested": model, "error": f"{e.kind}: {e}",
                              "hint": _probe_hint(str(e))}, ensure_ascii=False, indent=1))
            return 2
        finally:
            await reg.aclose()
        out = dict(res.__dict__)
        if not res.ok and res.error:
            out["hint"] = _probe_hint(res.error)
        print(json.dumps(out, default=lambda o: o.__dict__, ensure_ascii=False, indent=1))
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
                    if not res.ok and res.error and _probe_hint(res.error):
                        print(_probe_hint(res.error))
        await svc.stop()
        return svc, ok

    svc, ok = asyncio.run(_prepare())
    url = f"http://127.0.0.1:{args.port}"
    print(f"Agent Team → {url}  ({'ready' if ok else 'open Settings to fix the connection'})", flush=True)
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(AppService(args.data_dir)), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
