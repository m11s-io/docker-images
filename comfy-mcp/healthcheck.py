"""Native MCP HTTP readiness check; it only performs initialization."""

from __future__ import annotations

import json
import os
import sys
from urllib.request import Request, urlopen


def main() -> None:
    if os.environ.get("COMFY_MCP_TRANSPORT", "stdio") == "stdio":
        return
    port = os.environ.get("COMFY_MCP_PORT", "8080")
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "healthcheck",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "container-healthcheck", "version": "1"},
            },
        }
    ).encode()
    request = Request(
        f"http://127.0.0.1:{port}/mcp",
        data=payload,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=3) as response:  # noqa: S310 - loopback health probe
        if response.status != 200:
            raise RuntimeError(f"unexpected MCP health response: {response.status}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"comfy-mcp health check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
