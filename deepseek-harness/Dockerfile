FROM node:24-bookworm@sha256:14078204b6bb268c107ceff6d3c43f45a888105e5c2b18b14c32b3409d93a1b0 AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 make g++ musl-tools ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git init /opt/deepseek-harness \
    && git -C /opt/deepseek-harness remote add origin https://github.com/deepseek-ai/deepseek-harness.git \
    && git -C /opt/deepseek-harness fetch --depth=1 origin 639ed015397290b3745d163aafe02ffee4aa3f84 \
    && git -C /opt/deepseek-harness checkout --detach FETCH_HEAD

RUN corepack enable \
    && corepack prepare pnpm@11.7.0 --activate

WORKDIR /opt/deepseek-harness

RUN pnpm install --frozen-lockfile \
    && pnpm --dir native/system run build:native \
    && pnpm run build \
    && rm -rf .git .github .agents docs snapshots website benchmarks

FROM node:24-bookworm@sha256:14078204b6bb268c107ceff6d3c43f45a888105e5c2b18b14c32b3409d93a1b0

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
