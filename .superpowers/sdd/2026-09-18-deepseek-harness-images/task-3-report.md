# Task 3 report: DeepSeek Harness runtime and Compose attachment

## Outcome

Implemented the DeepSeek Harness runtime and Compose attachment. The source
Dockerfile remains available for GitHub Actions to build the pinned upstream
checkout, while local Compose pulls `m11s/deepseek-harness:0.1.6-alpha.1` and
does not define a DSH `build` field.

The DSH entrypoint writes an attachment-mode browser provider overlay using
`http://chromium:9222` by default and binds the web UI to `0.0.0.0:3080`.
Compose exposes only the UI port; Chromium has no published CDP port and uses
`seccomp=unconfined`.

## Files delivered

- `deepseek-harness/Dockerfile`: pinned, multi-stage source build for CI.
- `deepseek-harness/entrypoint.sh`: Cordis overlay and web launcher.
- `deepseek-harness/compose.yaml`: published DSH image plus local Chromium
  build service.
- `deepseek-harness/README.md`: local-run, persistence, workspace, optional
  browser, and separate-CDP guidance.
- `deepseek-harness/tests/validate.sh`: verifies rendered DSH has no build
  field and source Compose pins the published image.

## RED evidence

Before modifying `compose.yaml`, I extended `deepseek-harness/tests/validate.sh`
with the two revised assertions, then ran:

```sh
DEEPSEEK_API_KEY=placeholder sh deepseek-harness/tests/validate.sh
```

Observed result:

```text
validate_exit=1
```

The pre-change Compose configuration contained `dsh.build: .` and
`image: m11s/deepseek-harness:local`, so the new assertions failed as intended.

## GREEN evidence

After removing `dsh.build` and pinning the published image, I ran:

```sh
DEEPSEEK_API_KEY=placeholder sh deepseek-harness/tests/validate.sh
DEEPSEEK_API_KEY=placeholder docker compose -f deepseek-harness/compose.yaml config
```

Observed results:

```text
validate_exit=0
config_exit=0
```

The rendered `dsh` service contains
`image: m11s/deepseek-harness:0.1.6-alpha.1` and no `build` field. Its only
published port is `3080`; Chromium has no published CDP port.

## Static checks

```sh
sh -n deepseek-harness/entrypoint.sh
sh -n deepseek-harness/tests/validate.sh
git diff --check
```

All three commands exited 0. No `docker build` command was run for the DSH
source image; the placeholder API key was used only to satisfy Compose
environment expansion during rendering.
