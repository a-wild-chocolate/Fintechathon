import asyncio,json,sys
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client,StdioServerParameters
async def main():
    params=StdioServerParameters(command=sys.executable,args=['-m','tradex_rag.mcp_server'])
    async with stdio_client(params) as streams:
        async with ClientSession(streams[0],streams[1]) as session:
            await session.initialize()
            tools=await session.list_tools()
            result=await session.call_tool('search_knowledge',{'query':'RCEP 原产地证明 发票','market':'JP','limit':3})
            report={'tools':[t.name for t in tools.tools],'search_is_error':result.is_error,'result':result.model_dump(mode='json')}
            Path('docs/mcp_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
            print(json.dumps({'tools':report['tools'],'search_is_error':report['search_is_error']},ensure_ascii=False))
            assert not result.is_error
asyncio.run(main())
