"""Exercise both real MCP transports without submitting a ComfyUI job."""

import argparse
import asyncio
import json
import os
import socket
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


async def check_session(streams):
    async with ClientSession(*streams[:2]) as session:
        initialized = await session.initialize()
        assert initialized.server_info.name == "comfy-mcp", initialized
        tools = await session.list_tools()
        assert "server_info" in {tool.name for tool in tools.tools}
        result = await session.call_tool("server_info", {})
        assert not result.is_error, result
        info = json.loads(next(block.text for block in result.content if block.type == "text"))
        compatibility = info["compatibility"]
        assert compatibility["comfy_cli_version"] == "1.22.0", compatibility
        assert compatibility["envelope_schema_major"] == 1, compatibility


async def stop_process(process):
    if process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except TimeoutError:
            process.kill()
            await process.wait()


async def smoke(entrypoint):
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, HOME=home, COMFY_PROJECT=home,
                   COMFY_MCP_TRANSPORT="stdio", COMFY_CLI_MIN_VERSION="1.22.0",
                   COMFY_NO_TELEMETRY="1")
        params = StdioServerParameters(command=sys.executable, args=[entrypoint], env=env)
        async with stdio_client(params) as streams:
            await check_session(streams)
        print("stdio: initialize, tools/list, server_info passed", flush=True)

        with closing(socket.socket()) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env.update(COMFY_MCP_TRANSPORT="streamable-http", COMFY_MCP_PORT=str(port))
        process = await asyncio.create_subprocess_exec(sys.executable, entrypoint, env=env)
        try:
            # QEMU imports can take tens of seconds on the arm64 build.
            deadline = asyncio.get_running_loop().time() + 120
            while asyncio.get_running_loop().time() < deadline:
                if process.returncode is not None:
                    raise RuntimeError(f"HTTP server exited: {process.returncode}")
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection("127.0.0.1", port), timeout=1
                    )
                    writer.close()
                    await writer.wait_closed()
                    break
                except (OSError, TimeoutError):
                    pass
                await asyncio.sleep(0.1)
            else:
                raise TimeoutError("HTTP server did not become ready")
            async with streamable_http_client(f"http://127.0.0.1:{port}/mcp") as streams:
                await check_session(streams)
            healthcheck = Path(entrypoint).with_name("healthcheck.py")
            probe = await asyncio.create_subprocess_exec(sys.executable, str(healthcheck), env=env)
            try:
                assert await asyncio.wait_for(probe.wait(), timeout=10) == 0
            finally:
                await stop_process(probe)
            print("streamable-http: initialize, tools/list, server_info, healthcheck passed", flush=True)
        finally:
            await stop_process(process)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrypoint", default="/opt/comfy-mcp-image/entrypoint.py")
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(smoke(args.entrypoint), timeout=360))
