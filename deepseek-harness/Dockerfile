# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b

FROM node:26-bookworm@sha256:3b764117159bda01d2396391e7789b6a9106af9729cfd001ef55e98557868310 AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 make g++ musl-tools ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG DSH_REF=dsh-v0.2.0-rc.2
ARG DSH_COMMIT=639ed015397290b3745d163aafe02ffee4aa3f84
RUN git init /opt/deepseek-harness \
    && git -C /opt/deepseek-harness remote add origin https://github.com/deepseek-ai/deepseek-harness.git \
    && git -C /opt/deepseek-harness fetch --depth=1 origin "refs/tags/${DSH_REF}" \
    && test "$(git -C /opt/deepseek-harness rev-parse 'FETCH_HEAD^{commit}')" = "$DSH_COMMIT" \
    && git -C /opt/deepseek-harness checkout --detach FETCH_HEAD

# Node 25+ no longer bundles Corepack; install the pinned package manager directly.
RUN npm install --global pnpm@11.7.0

WORKDIR /opt/deepseek-harness

RUN pnpm install --frozen-lockfile \
    && pnpm --dir native/system run build:native \
    && pnpm run build \
    && rm -rf .git .github .agents docs snapshots website benchmarks

FROM node:26-bookworm@sha256:3b764117159bda01d2396391e7789b6a9106af9729cfd001ef55e98557868310

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 dsh \
    && useradd --system --uid 10001 --gid dsh --create-home dsh \
    && mkdir -p /workspace /home/dsh/.dsh \
    && chown -R dsh:dsh /workspace /home/dsh

COPY --from=build --chown=dsh:dsh /opt/deepseek-harness /opt/deepseek-harness
COPY --chown=dsh:dsh entrypoint.sh /usr/local/bin/dsh-entrypoint
# The profile resolver exposes the CLI dependency closure, not root devDependencies.
# These plugins are already installed and built from the pinned workspace.
RUN node --input-type=module -e 'import fs from "node:fs"; const path = "/opt/deepseek-harness/apps/cli/package.json"; const pkg = JSON.parse(fs.readFileSync(path, "utf8")); for (const name of ["@deepseek-ai/dsh-browser-use", "@deepseek-ai/dsh-experimental-browser-use-playwright-mcp"]) pkg.dependencies[name] = "workspace:*"; fs.writeFileSync(path, JSON.stringify(pkg, null, 2) + "\n");' \
    && chmod 0755 /usr/local/bin/dsh-entrypoint

ENV DSH_HOME=/home/dsh/.dsh

USER dsh
WORKDIR /workspace
EXPOSE 3080
ENTRYPOINT ["/usr/local/bin/dsh-entrypoint"]

# Validate the assembled runtime before either platform can be published.
RUN --mount=type=bind,source=tests/smoke.mjs,target=/tmp/dsh-smoke.mjs node /tmp/dsh-smoke.mjs
