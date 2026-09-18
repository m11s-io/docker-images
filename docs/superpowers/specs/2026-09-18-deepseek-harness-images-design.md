# DeepSeek Harness Images Design

## Goal

Publish a DeepSeek Harness runtime image and a separate Chromium CDP image, with a Compose example that connects the runtime to the browser over a private Docker network.

## Architecture

`m11s/deepseek-harness` runs the DeepSeek Harness Web profile and includes the Playwright MCP browser-use provider but no browser executable. `m11s/chromium-cdp` runs headless Chromium with Chrome DevTools Protocol enabled. The runtime attaches to the browser through the service-local CDP endpoint `http://chromium:9222`.

GitHub Actions builds and publishes the DSH image from pinned upstream source. The Compose example pulls that published image rather than building DSH locally. It publishes the DSH Web UI only; Chromium's CDP port remains internal to the Compose network. A named volume persists DSH application state, and a bind mount exposes a user-selected workspace to the runtime.

## Components

- `deepseek-harness/Dockerfile`: a non-root Node runtime image that installs the pinned DSH packages and starts the Web profile from an entrypoint.
- `deepseek-harness/entrypoint.sh`: initializes a profile patch which enables the Playwright MCP browser provider in attachment mode, using `DSH_BROWSER_CDP_ENDPOINT`.
- `deepseek-harness/compose.yaml`: a runnable deployment that pulls the published DSH image and runs it with the companion Chromium service.
- `chromium-cdp/Dockerfile`: a non-root Debian-based Chromium image that starts headless Chromium with CDP bound to the container network.
- Per-image README files: describe configuration, mounts, persistence, and the fact that CDP must remain private.
- Root README and build workflow: enumerate and publish both images on linux/amd64 and linux/arm64.

## Data Flow

1. A user opens the DSH UI on the published DSH Web port.
2. The DSH agent loop starts browser-use through its Playwright MCP provider.
3. The provider attaches to the `chromium` service's CDP endpoint.
4. Chromium performs browser actions; DSH records resulting tool output in its session state.

## Security and Operating Constraints

- Chromium CDP is not published by Compose and must never be exposed to an untrusted network.
- The DSH image runs as a non-root user.
- No Docker socket is mounted.
- Secrets are provided at runtime, principally `DEEPSEEK_API_KEY`; they are not baked into images.
- The workspace mount is the only user project filesystem made available by the Compose example.
- The images target linux/amd64 and linux/arm64.

## Validation

- Dockerfiles build successfully for their declared platforms in CI.
- `docker compose config` validates the example and confirms Chromium has no published port.
- Documentation names the required `DEEPSEEK_API_KEY`, persisted state location, workspace mount, and private-CDP requirement.
