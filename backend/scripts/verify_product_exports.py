"""Verify browser-selected ZIP bytes and exercise the stdlib client against loopback."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('http_example', ROOT / 'examples/http_client.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    assert urlsplit(args.url).hostname in ('localhost','127.0.0.1')
    selected=json.loads((args.evidence/'selected-run.json').read_text())
    with zipfile.ZipFile(args.evidence/'selected-browser.zip') as archive:
        manifest=json.loads(archive.read('manifest.json'))
        for artifact in manifest['artifacts']:
            assert hashlib.sha256(archive.read(artifact['path'])).hexdigest()==artifact['sha256']
            assert selected['artifact_selection'][artifact['artifact_id']]['revision']==artifact['revision']
    client=module.AgentTeamHTTP(args.url)
    current=client.run(selected['run_id'])
    assert current['artifact_selection']==selected['artifact_selection']
    output=args.evidence/'selected-sdk.zip'
    sdk_manifest=client.save_selected(selected['run_id'],output)
    assert sdk_manifest==manifest
    result={'status':'PASS','browser_manifest':manifest,'sdk_manifest':sdk_manifest,
            'current_selection':current['artifact_selection'],'sdk_output':str(output)}
    (args.evidence/'verified-exports.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
