# m11s/chromium-cdp

Headless Chromium with the Chrome DevTools Protocol (CDP) listener on port
`9222`. It is intended for a colocated DSH container to reach at
`http://chromium:9222` over a private Docker network.

The base is pinned to the October 5, 2026 Bookworm slim image. Chromium and
its sandbox package are installed from Debian's current repositories at build time.
Nginx exposes CDP on port `9222` and forwards to Chromium on loopback port
`9223`. Discovery responses advertise the external service authority so
clients can connect to the browser WebSocket from another container.
Both processes run as UID `10001`; Tini forwards signals and reaps children.

## Security

CDP grants full browser control. Do not publish port `9222` to the host or to
an external network. In routine deployments, keep this image on a private
Docker network and let only DSH consume the endpoint.

## Docker Desktop compatibility

The supplied DeepSeek Harness Compose deployment must run its `chromium`
service with Docker's `seccomp=unconfined` security option. Docker Desktop's
default seccomp profile blocks the namespace syscalls Chromium needs for its
own sandbox, causing Chromium to exit with status 133. This Docker setting
does not disable Chromium's sandbox; it allows Chromium to create the
namespaces that sandbox requires. The Compose example applies this setting.

## Verify the image

```sh
docker build -t m11s/chromium-cdp:local chromium-cdp
sh chromium-cdp/tests/smoke.sh m11s/chromium-cdp:local
```

The test uses a temporary private network and a separate Node 24 container
to verify HTTP discovery and a real CDP WebSocket command. Set
`CDP_TEST_CLIENT_IMAGE` to use another image containing Node 24 or newer.

## Diagnostic run

For an image-only diagnostic, run Chromium without publishing CDP:

```bash
docker run --rm --detach --name chromium-cdp-diagnostic --network none \
  --security-opt seccomp=unconfined \
  m11s/chromium-cdp:latest
docker logs chromium-cdp-diagnostic
docker rm --force chromium-cdp-diagnostic
```

The diagnostic container has no network connectivity and does not make CDP
available to the host. Use the DeepSeek Harness Compose deployment when DSH
needs to connect to Chromium over its private network.
