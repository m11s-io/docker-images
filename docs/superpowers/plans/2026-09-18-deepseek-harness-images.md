# DeepSeek Harness Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish separately deployable DeepSeek Harness and Chromium CDP images, plus a Compose example that attaches DSH browser tools to the private Chromium service.

**Architecture:** The DSH image builds the pinned DeepSeek Harness source in a Node 24 Debian builder and retains the built workspace plus its package graph in a non-root runtime image. Its entrypoint creates an idempotent Web profile overlay that binds the UI to the container network and mounts the Playwright MCP browser provider in CDP attachment mode. The Chromium image runs a non-root, headless Chromium process whose CDP listener is consumed only by the Compose network.

**Tech Stack:** Docker BuildKit, Debian Bookworm, Node.js 24, pnpm 11.7.0, DeepSeek Harness, Playwright MCP, Chromium, Docker Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-18-deepseek-harness-images-design.md`

## Global Constraints

- Build for `linux/amd64` and `linux/arm64`.
- Pin the DeepSeek Harness source revision and every base image digest used by the Dockerfiles.
- Run both images as non-root users.
- The DSH image contains no Chromium executable or Playwright-downloaded browser.
- Chromium CDP listens on container port `9222`, but Compose must not publish that port.
- The DSH Web UI is published at port `3080`; the profile overlay must set its `webserver` host to `0.0.0.0`.
- `DEEPSEEK_API_KEY` is runtime-only and never appears in an image layer, Compose value, or documentation example value.
- The browser provider uses attachment mode and reads `DSH_BROWSER_CDP_ENDPOINT`, defaulting to `http://chromium:9222`.
- The Compose example provides a named DSH-home volume and an explicit `./workspace` bind mount.
- Local Compose pulls `m11s/deepseek-harness:0.1.6-alpha.1`; it never builds the source-heavy DSH image.

---

### Task 1: Add a configuration-validation harness

**Files:**

- Create: `deepseek-harness/tests/validate.sh`

**Interfaces:**

- Consumes: `deepseek-harness/compose.yaml`, `deepseek-harness/Dockerfile`, `chromium-cdp/Dockerfile`, and `deepseek-harness/entrypoint.sh`.
- Produces: an executable shell check that returns nonzero when Compose publishes Chromium CDP, the images run as root, or the DSH image installs a browser binary.

- [ ] **Step 1: Write the failing validation harness**

```sh
#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file="$repo_root/deepseek-harness/compose.yaml"

test -f "$compose_file"
docker compose -f "$compose_file" config >"${TMPDIR:-/tmp}/deepseek-harness-compose.yaml"
! grep -A8 '^  chromium:' "${TMPDIR:-/tmp}/deepseek-harness-compose.yaml" | grep -q 'published:'
grep -q 'user: "10001:10001"' "$compose_file"
grep -q 'DSH_BROWSER_CDP_ENDPOINT' "$repo_root/deepseek-harness/entrypoint.sh"
grep -q "mode: attach" "$repo_root/deepseek-harness/entrypoint.sh"
! grep -qi 'playwright install\|chromium-browser\|apt-get install.*chromium' "$repo_root/deepseek-harness/Dockerfile"
grep -q '^USER chromium$' "$repo_root/chromium-cdp/Dockerfile"
```

- [ ] **Step 2: Run the harness and verify it fails because the image files do not exist**

Run: `sh deepseek-harness/tests/validate.sh`

Expected: FAIL at `test -f` because `deepseek-harness/compose.yaml` does not yet exist.

- [ ] **Step 3: Keep the harness executable**

Run: `chmod 0755 deepseek-harness/tests/validate.sh`

- [ ] **Step 4: Commit the red test harness**

```bash
git add deepseek-harness/tests/validate.sh
git commit -m "test: add DeepSeek Harness image validation"
```

### Task 2: Implement the Chromium CDP image

**Files:**

- Create: `chromium-cdp/Dockerfile`
- Create: `chromium-cdp/entrypoint.sh`
- Create: `chromium-cdp/README.md`

**Interfaces:**

- Consumes: the `chromium` Compose service command and port `9222`.
- Produces: an OCI image that starts Chromium with CDP available to the Compose `dsh` service at `http://chromium:9222`.

- [ ] **Step 1: Write the minimal Chromium image and entrypoint**

```dockerfile
FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 chromium \
    && useradd --system --uid 10001 --gid chromium --create-home chromium

COPY entrypoint.sh /usr/local/bin/chromium-cdp
RUN chmod 0755 /usr/local/bin/chromium-cdp

USER chromium
EXPOSE 9222
ENTRYPOINT ["/usr/local/bin/chromium-cdp"]
```

```sh
#!/bin/sh
set -eu

exec chromium \
  --headless=new \
  --no-first-run \
  --no-default-browser-check \
  --disable-dev-shm-usage \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chromium-profile \
  about:blank
```

- [ ] **Step 2: Document the private-CDP deployment rule**

Document that `9222` grants browser control, must not be published, and is intended to be consumed by DSH over a private Docker network. Include an image-only run command for diagnostics that does not suggest publishing CDP in routine deployments.

- [ ] **Step 3: Run the validation harness and verify it progresses past the Chromium user assertion**

Run: `sh deepseek-harness/tests/validate.sh`

Expected: FAIL because the DSH image and Compose files still do not exist; it must no longer fail on the Chromium `USER` assertion.

- [ ] **Step 4: Build and smoke-test the Chromium image**

Run: `docker build --platform linux/amd64 -t m11s/chromium-cdp:test chromium-cdp && docker run --rm --detach --name chromium-cdp-test --network none m11s/chromium-cdp:test`

Expected: image builds and its container remains running. Stop it with `docker rm --force chromium-cdp-test` after checking logs.

- [ ] **Step 5: Commit the Chromium image**

```bash
git add chromium-cdp
git commit -m "feat: add Chromium CDP image"
```

### Task 3: Implement the DeepSeek Harness runtime and Compose attachment

**Files:**

- Create: `deepseek-harness/Dockerfile`
- Create: `deepseek-harness/entrypoint.sh`
- Create: `deepseek-harness/compose.yaml`
- Create: `deepseek-harness/README.md`

**Interfaces:**

- Consumes: `DSH_BROWSER_CDP_ENDPOINT`, `DEEPSEEK_API_KEY`, `/workspace`, and the `chromium` service alias.
- Produces: Web UI at host port `3080`; persistent DSH state in `/home/dsh/.dsh`; an attached Playwright MCP browser provider.

- [ ] **Step 1: Write the DSH multi-stage Dockerfile**

Use `node:24-bookworm@sha256:6dac556d980b7f0e5498d08f08cee0ca67798b4ad6c23964a9214920e67758d0` for both DSH stages. Install `git`, `python3`, `make`, and `g++`; clone `https://github.com/deepseek-ai/deepseek-harness.git` at `0d1f50007f`; activate pnpm `11.7.0`; run `pnpm install --frozen-lockfile` and `pnpm run build`. In the runtime stage, copy only the built checkout and runtime prerequisites, create the `dsh` user and `/workspace`, `/home/dsh/.dsh` directories under UID/GID `10001`, set `DSH_HOME=/home/dsh/.dsh`, expose `3080`, and execute `/usr/local/bin/dsh-entrypoint`.

- [ ] **Step 2: Write the entrypoint overlay and launcher**

```sh
#!/bin/sh
set -eu

: "${DSH_BROWSER_CDP_ENDPOINT:=http://chromium:9222}"
mkdir -p "$DSH_HOME"
cat >"$DSH_HOME/cordis.patch.yml" <<EOF
- id: webserver
  config:
    host: 0.0.0.0
    port: 3080
- insert:
    - name: '@deepseek-ai/dsh-browser-use'
    - name: '@deepseek-ai/dsh-experimental-browser-use-playwright-mcp'
      config:
        mode: attach
        endpoint: ${DSH_BROWSER_CDP_ENDPOINT}
EOF

exec node /opt/deepseek-harness/apps/cli/lib/bin.js web --no-open --trusted-host localhost:3080
```

Replace the heredoc interpolation only if DSH configuration requires quoted scalars; retain attachment mode, loopback-free Web binding, and the startup host-trust allowance.

- [ ] **Step 3: Write the Compose example**

```yaml
services:
  dsh:
    image: m11s/deepseek-harness:0.1.6-alpha.1
    environment:
      DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:?set DEEPSEEK_API_KEY in the environment}
      DSH_BROWSER_CDP_ENDPOINT: http://chromium:9222
    ports:
      - "3080:3080"
    volumes:
      - dsh-home:/home/dsh/.dsh
      - ./workspace:/workspace
    depends_on:
      chromium:
        condition: service_started
    user: "10001:10001"

  chromium:
    build: ../chromium-cdp
    image: m11s/chromium-cdp:local
    shm_size: 1gb
    security_opt:
      - seccomp=unconfined
    user: "10001:10001"

volumes:
  dsh-home:
```

- [ ] **Step 4: Document configuration and supported use**

Document the required key, `docker compose up`, `http://localhost:3080`, the persistent state volume, workspace mount, and that the browser feature is optional and has no Chromium installation in the DSH image. State that Compose pulls the published DSH image and builds no DSH source locally. Document `DSH_BROWSER_CDP_ENDPOINT` for deployments where Chromium is separate from Compose.

- [ ] **Step 5: Run the validation harness and verify it passes**

Run: `sh deepseek-harness/tests/validate.sh`

Expected: PASS; Compose renders successfully, Chromium has no published port, and the provider is configured in attachment mode.

- [ ] **Step 6: Build and configuration-smoke the DSH image**

Run: `docker build --platform linux/amd64 -t m11s/chromium-cdp:local chromium-cdp && docker compose -f deepseek-harness/compose.yaml config`

Expected: Chromium builds and rendered configuration lists only DSH port `3080` under published ports; the DSH service has no `build` field and uses the published `m11s/deepseek-harness:0.1.6-alpha.1` image.

- [ ] **Step 7: Commit the DSH deployment**

```bash
git add deepseek-harness
git commit -m "feat: add DeepSeek Harness browser deployment"
```

### Task 4: Publish the images through repository CI

**Files:**

- Modify: `.github/workflows/build.yaml`
- Modify: `README.md`

**Interfaces:**

- Consumes: `deepseek-harness/**` and `chromium-cdp/**` path changes.
- Produces: `m11s/deepseek-harness` and `m11s/chromium-cdp` multi-architecture Docker Hub tags.

- [ ] **Step 1: Extend changed-path filtering and manual-dispatch choices**

Add `deepseek-harness` and `chromium-cdp` to the workflow path triggers, `paths-filter` outputs, workflow-dispatch image choices, and matrix selection logic.

- [ ] **Step 2: Add multi-architecture build matrix rows**

Add rows with `platforms: linux/amd64,linux/arm64`, repositories `m11s/deepseek-harness` and `m11s/chromium-cdp`, tags `m11s/deepseek-harness:0.1.6-alpha.1` and `m11s/chromium-cdp:bookworm-20260824`, and matching `latest` tags. Keep the existing Buildx cache settings.

- [ ] **Step 3: Add both images to the public catalog README**

Add a row for each image, short descriptions that distinguish the runtime from the browser, and `docker pull` examples using their `latest` tags.

- [ ] **Step 4: Re-run static validation**

Run: `sh deepseek-harness/tests/validate.sh && git diff --check && git status --short`

Expected: validation passes, `git diff --check` prints nothing, and status shows only the intended CI and README changes.

- [ ] **Step 5: Commit publishing metadata**

```bash
git add .github/workflows/build.yaml README.md
git commit -m "ci: publish DeepSeek Harness images"
```
