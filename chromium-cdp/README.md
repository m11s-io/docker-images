# m11s/chromium-cdp

Headless Chromium with the Chrome DevTools Protocol (CDP) listener on port
`9222`. It is intended for a colocated DSH container to reach at
`http://chromium:9222` over a private Docker network.

## Security

CDP grants full browser control. Do not publish port `9222` to the host or to
an external network. In routine deployments, keep this image on a private
Docker network and let only DSH consume the endpoint.

## Diagnostic run

For an image-only diagnostic, run Chromium without publishing CDP:

```bash
docker run --rm --detach --name chromium-cdp-diagnostic --network none \
  m11s/chromium-cdp:latest
docker logs chromium-cdp-diagnostic
docker rm --force chromium-cdp-diagnostic
```

The diagnostic container has no network connectivity and does not make CDP
available to the host. Use the DeepSeek Harness Compose deployment when DSH
needs to connect to Chromium over its private network.
