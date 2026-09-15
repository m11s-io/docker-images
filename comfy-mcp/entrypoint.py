"""Select the image's stdio or SDK-native Streamable HTTP MCP transport."""

from __future__ import annotations

import argparse
import os

from comfy_mcp import server
from mcp.server.transport_security import TransportSecuritySettings

_TRANSPORTS = ("stdio", "streamable-http")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="comfy-mcp")
    parser.add_argument(
        "--transport",
        choices=_TRANSPORTS,
        default=os.environ.get("COMFY_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.environ.get("COMFY_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("COMFY_MCP_PORT", "8080")))
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.transport == "stdio":
        # Delegate to the upstream entry point unchanged so Desktop MCP clients
        # retain its startup, diagnostics, and stdin/stdout behavior.
        server.main([])
        return
    if not 1 <= args.port <= 65535:
        raise SystemExit("comfy-mcp: --port must be from 1 to 65535")

    # Kubernetes routes carry their own public Host header. The SDK otherwise
    # protects localhost-only servers by rejecting it before MCP initialization.
    # Ingress owns TLS, authentication, and host policy for this service.
    server.mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        streamable_http_path="/mcp",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )


if __name__ == "__main__":
    main()
