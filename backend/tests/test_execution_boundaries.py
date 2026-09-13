"""Real sockets, issued credentials and isolated containers; no fabricated business input."""
import asyncio
import json
import os
import shlex
import tempfile
from pathlib import Path

import pytest

from agentteam.runtime.checks import json_schema_check
from agentteam.runtime.sandbox import run_command, docker_available
from agentteam.runtime.webtools import FetchDenied, PublicNetworkBackend
from .test_server_security import EVIDENCE, provision


async def test_network_backend_refuses_actual_private_listener_and_schema_fetch(tmp_path):
    received = []
    async def connection(reader, writer):
        received.append(True); writer.close(); await writer.wait_closed()
    server = await asyncio.start_server(connection, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    try:
        with pytest.raises(FetchDenied, match='non-public'):
            await PublicNetworkBackend().connect_tcp('127.0.0.1', port, timeout=1)
        # A remote reference attached to an actual schema must not initiate an
        # independent network path bypassing the research transport.
        schema_path = Path(__file__).resolve().parents[1] / 'agentteam/schemas/team-plan.schema.json'
        schema = json.loads(schema_path.read_text()); schema['$ref'] = f'http://127.0.0.1:{port}/schema'
        actual = json.loads((EVIDENCE / 'thinking-interruption.json').read_text())['plan']
        assert json_schema_check(json.dumps(actual).encode(), schema)['status'] == 'blocked'
        await asyncio.sleep(0.01)
        assert received == []
    finally:
        server.close(); await server.wait_closed()


async def test_secured_work_refuses_host_readable_fallback(tmp_path):
    _, keys = provision(tmp_path)
    prior = os.environ.get('AGENTTEAM_SANDBOX')
    os.environ['AGENTTEAM_SANDBOX'] = 'subprocess'
    try:
        # Only reads an actual newly-issued verification credential, never a
        # user's existing secret. The command must not be launched at all.
        command = 'cat ' + shlex.quote(str(tmp_path / 'maintainer.key'))
        result = await run_command(command, tmp_path / 'workspace', require_container=True)
        assert result.denied and result.exit_code is None and result.stdout == ''
        assert keys['maintainer'] not in repr(result)
    finally:
        if prior is None: os.environ.pop('AGENTTEAM_SANDBOX', None)
        else: os.environ['AGENTTEAM_SANDBOX'] = prior


async def test_actual_container_cancellation_removes_owned_process_and_caps_output():
    if not await docker_available(refresh=True):
        pytest.skip('actual Docker daemon required; CI provides it')
    cache = Path.home() / '.cache'; cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='agentteam-boundary-', dir=cache) as directory:
        workspace = Path(directory)
        prior = os.environ.get('AGENTTEAM_SANDBOX'); os.environ['AGENTTEAM_SANDBOX'] = 'docker'
        task = None
        try:
            # Output the project's actual source repeatedly to exercise streaming
            # capture. No synthetic record or fabricated model response is used.
            source = Path(__file__).resolve().parents[2] / 'docs/PRODUCTION_PLAN.md'
            (workspace / source.name).write_bytes(source.read_bytes())
            result = await run_command('python3 -c "from pathlib import Path; import sys; sys.stdout.write(Path(\'PRODUCTION_PLAN.md\').read_text()*1000)"',
                                       workspace, timeout=30, max_output=2000, require_container=True)
            assert result.exit_code == 0 and len(result.stdout) < 2400 and 'discarded' in result.stdout
            task = asyncio.create_task(run_command('python3 -c "from pathlib import Path; import socket,time; Path(\'container-id\').write_text(socket.gethostname()); time.sleep(300)"',
                                                   workspace, timeout=300, require_container=True))
            async with asyncio.timeout(20):
                while not (workspace / 'container-id').exists():
                    await asyncio.sleep(0.05)
            container_id = (workspace / 'container-id').read_text()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            check = await asyncio.create_subprocess_exec('docker', 'inspect', container_id, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await check.wait()
            assert check.returncode != 0, 'owned sandbox container survived cancellation'
        finally:
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if prior is None: os.environ.pop('AGENTTEAM_SANDBOX', None)
            else: os.environ['AGENTTEAM_SANDBOX'] = prior
