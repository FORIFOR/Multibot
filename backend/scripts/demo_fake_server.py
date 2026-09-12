"""UI smoke server backed by the scripted FAKE provider. Not a real LLM. Every run is labelled provider_kind=fake.

    AGENTTEAM_ALLOW_FAKE_PROVIDER=1 .venv/bin/python scripts/demo_fake_server.py --port 8788
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))
os.environ["AGENTTEAM_ALLOW_FAKE_PROVIDER"] = "1"

import uvicorn  # noqa: E402

from agentteam.api.app import create_app  # noqa: E402
from agentteam.api.service import AppService  # noqa: E402
from agentteam.providers.fake_driver import FakeProvider  # noqa: E402
from conftest import FAKE_CONFIG, default_script  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8788)
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()
    data = args.data_dir or tempfile.mkdtemp(prefix="agentteam-fake-")
    svc = AppService(data, fake_adapters={"fake": FakeProvider(default_script)}, config_yaml=FAKE_CONFIG, approval_wait_seconds=5)
    print(f"[demo] FAKE provider server. data_dir={data}", flush=True)
    uvicorn.run(create_app(svc), host="127.0.0.1", port=args.port, log_level="warning")
