# m11s/comfy-mcp

[Comfy MCP](https://github.com/Comfy-Org/comfy-mcp) packaged as a stdio Docker
MCP server. It drives a separately deployed ComfyUI instance through the
[`comfy-cli`](https://github.com/Comfy-Org/comfy-cli) binary; this image does
not contain ComfyUI, CUDA, models, or a browser UI.

## Tags

| Tag | Use |
| --- | --- |
| `latest` | Current Comfy MCP image |
| `0.1.0` | Pinned release using comfy-mcp `0.10.0` and comfy-cli `1.20.0` |

## Docker MCP Toolkit

Copy the included server definition into Docker MCP Toolkit's local catalog,
then create and configure a profile:

```bash
mkdir -p ~/.docker/mcp/catalogs
cp comfy-mcp/server.yaml ~/.docker/mcp/catalogs/comfy-mcp.yaml
docker mcp profile create --name comfyui \
  --server file://comfy-mcp.yaml
docker mcp profile config comfyui \
  --set comfy-mcp.comfy_local_url=http://host.docker.internal:8188
docker mcp client connect --global --profile comfyui codex
```

Docker Desktop's **MCP Toolkit → Profiles** view now shows the `comfyui`
profile. The final command connects that profile to Codex; substitute another
supported client when needed.

For a local development cluster, first make ComfyUI available to Docker
Desktop's host:

```bash
kubectl -n comfyui port-forward svc/comfyui 8188:8188
```

`COMFY_LOCAL_URL` is the recommended target for a local port-forward. The
container needs no published port: MCP traffic is carried over standard input
and output by Docker MCP Toolkit.

For an agent running inside Kubernetes, set `COMFYUI_URL` to the private
service address instead and allow that workload through ComfyUI's network
policy:

```text
http://comfyui.comfyui.svc.cluster.local:8188
```

## State and safety

The container runs as an unprivileged user. Mount a writable volume at
`/workspace` when project configuration, submitted-job state, or downloaded
outputs must survive a container restart. Manage models and custom nodes through
the ComfyUI deployment, not through this MCP container.

Comfy MCP is licensed by Comfy Org under AGPL-3.0-or-later or a commercial
license. Review the upstream licensing terms before deploying it as a hosted
service.
