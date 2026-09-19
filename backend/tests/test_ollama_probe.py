import json
import httpx
from agentteam.providers.openai_compat_driver import OpenAICompatDriver

async def test_local_probe_is_deterministic_and_checks_tool_arguments():
    bodies=[]
    def handler(request):
        bodies.append(json.loads(request.content))
        message={'tool_calls':[{'id':'p','function':{'name':'ping','arguments':'{"ok":false}'}}]} if len(bodies)==1 else {'content':'{"ok":true}'}
        return httpx.Response(200,json={'model':'local','choices':[{'message':message,'finish_reason':'stop'}]})
    driver=OpenAICompatDriver('local',None,'http://127.0.0.1:11434/v1',driver='ollama')
    await driver.client.aclose()
    driver.client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        probe=await driver.probe('local')
        assert not probe.ok and not probe.tool_calling and probe.json_schema
        assert all(b['temperature']==0 for b in bodies)
    finally:await driver.aclose()
