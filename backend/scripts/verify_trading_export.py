"""Verify real adopted trading-design downloads against persisted, reviewed bytes."""
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

out = Path(os.environ.get("QUALITY_OUT", "artifacts/product-quality/trading-team"))
env = json.loads((out / "environment.json").read_text())
base = os.environ.get("QUALITY_BASE", env["base"])
run_id = (out / "run-id.txt").read_text().strip()
with urlopen(f"{base}/api/runs/{run_id}") as response:
    run = json.load(response)
assert run["status"] == "completed", "Run is not complete"
expected = {"architecture.md", "decisions.md"}
verified = []
with ZipFile(out / "selected-browser.zip") as archive:
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["selection"] == "adopted" and manifest["run_id"] == run_id
    assert {a["artifact_id"] for a in manifest["artifacts"]} == expected
    assert len(manifest["artifacts"]) == len(expected)
    for entry in manifest["artifacts"]:
        raw = archive.read(entry["path"])
        digest = hashlib.sha256(raw).hexdigest()
        artifact = next(a for a in run["artifacts"] if a["artifact_id"] == entry["artifact_id"]
                        and a["revision"] == entry["revision"])
        assert digest == entry["sha256"] == artifact["sha256"]
        assert run["artifact_selection"][entry["artifact_id"]]["revision"] == entry["revision"]
        persisted = Path(env["data_dir"]) / "runs" / artifact["storage_path"]
        assert raw == persisted.read_bytes()
        task = next(t for t in run["tasks"] if t["spec"]["id"] == artifact["task_id"])
        review = task["review"]
        assert review and review["results"] and all(r["status"] == "pass" for r in review["results"])
        ref = {"artifact_id": entry["artifact_id"], "revision": entry["revision"], "sha256": digest}
        assert ref in review["target_artifacts"]
        verified.append(ref)
result = {"status": "PASS", "run_id": run_id, "verified": verified,
          "scope": "Persisted adoption, exact ZIP bytes and bound model review; not an independent content verdict"}
(out / "verified-export.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False, indent=2))
