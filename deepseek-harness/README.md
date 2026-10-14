# m11s/deepseek-harness

DeepSeek Harness (DSH) web runtime, with an optional browser provider attached
to a separate Chromium CDP container. The DSH image does not install Chromium.

This image pins upstream `dsh-v0.2.0-rc.2` (a release candidate, not an alpha)
at commit `639ed015397290b3745d163aafe02ffee4aa3f84`. It uses Node 24
Bookworm and the upstream pnpm `11.7.0` pin. The build includes the native
Landlock launcher and system addon; sandbox availability still depends on
the host kernel.

GitHub builds AMD64 and ARM64 on separate native runners using Docker's
pinned GitHub Builder workflow, then combines them into one image manifest.
Each platform has an isolated cache of final-image layers. The Docker build
checks non-root startup, browser plugin activation, authenticated HTML, and
shutdown before publication. Git history and upstream development-only
snapshots, docs, website, and benchmarks are omitted from the runtime.

## Run

Set a DeepSeek API key, then start the deployment:

```sh
export DEEPSEEK_API_KEY=...
docker compose up
```

Open <http://localhost:3080>. The `dsh-home` named volume persists DSH state
at `/home/dsh/.dsh`; `./workspace` is mounted at `/workspace` for project
files. Local Compose pulls the published
`m11s/deepseek-harness:0.2.0-rc.2` image; it never builds the DSH source
image locally. The companion Chromium image may still be built locally.

The Compose example starts Chromium privately for browser features. It does
not publish CDP port `9222`; DSH connects over the Compose network at
`http://chromium:9222`. Chromium's own sandbox is retained. Its Compose
service uses `seccomp=unconfined` so Docker Desktop permits Chromium's sandbox
namespace setup.

## Separate Chromium deployments

When Chromium runs outside this Compose project, set
`DSH_BROWSER_CDP_ENDPOINT` to its reachable CDP endpoint. For example:

```sh
DSH_BROWSER_CDP_ENDPOINT=http://browser.internal:9222 docker compose up
```

The browser provider is optional; DSH can be used without browser automation.
