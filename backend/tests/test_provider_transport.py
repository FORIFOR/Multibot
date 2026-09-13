"""Real HTTP transport and connection-drop drill; no replacement model replies."""
import asyncio
import os

from agentteam.api.service import AppService
from agentteam.providers.openai_compat_driver import OpenAICompatDriver
from .test_observer import credentials, listening_socket, running
from .test_server_security import PROFILE


async def test_local_provider_http_transport_ignores_ambient_proxy(tmp_path):
    sock = listening_socket(); origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
    access = credentials(tmp_path, origin)
    svc = AppService(tmp_path / 'data', config_yaml=PROFILE.read_text(), access_file=access)
    intercepted = []
    async def drop_connection(reader, writer):
        # Actual proxy-address connection failure, not a fake HTTP/model reply.
        # Never retain or print the request or the real issued access key.
        intercepted.append(True); writer.close(); await writer.wait_closed()
    proxy = await asyncio.start_server(drop_connection, '127.0.0.1', 0)
    proxy_url = f'http://127.0.0.1:{proxy.sockets[0].getsockname()[1]}'
    variables = {k: proxy_url for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')}
    variables.update(NO_PROXY='', no_proxy='')
    old = {k: os.environ.get(k) for k in variables}
    driver = None
    try:
        async with running(svc, sock):
            os.environ.update(variables)
            driver = OpenAICompatDriver('ollama', (tmp_path / 'maintainer.key').read_text().strip(), origin, driver='ollama')
            # Verify the provider's real HTTP client against the actual secured
            # API. This transport check makes no LLM call or quality claim.
            response = await driver.client.get(origin + '/api/auth/me')
            assert response.status_code == 200 and response.json()['subject'] == 'maintainer'
            assert intercepted == []
    finally:
        if driver: await driver.aclose()
        for key, value in old.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        proxy.close(); await proxy.wait_closed()
