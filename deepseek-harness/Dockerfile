FROM node:24-bookworm@sha256:6dac556d980b7f0e5498d08f08cee0ca67798b4ad6c23964a9214920e67758d0 AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends git python3 make g++ ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/deepseek-ai/deepseek-harness.git /opt/deepseek-harness \
    && git -C /opt/deepseek-harness checkout 0d1f50007f

RUN corepack enable \
    && corepack prepare pnpm@11.7.0 --activate

WORKDIR /opt/deepseek-harness

RUN pnpm install --frozen-lockfile \
    && pnpm run build

FROM node:24-bookworm@sha256:6dac556d980b7f0e5498d08f08cee0ca67798b4ad6c23964a9214920e67758d0

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 dsh \
    && useradd --system --uid 10001 --gid dsh --create-home dsh \
    && mkdir -p /workspace /home/dsh/.dsh \
    && chown -R dsh:dsh /workspace /home/dsh

COPY --from=build --chown=dsh:dsh /opt/deepseek-harness /opt/deepseek-harness
COPY --chown=dsh:dsh entrypoint.sh /usr/local/bin/dsh-entrypoint
RUN chmod 0755 /usr/local/bin/dsh-entrypoint

ENV DSH_HOME=/home/dsh/.dsh

USER dsh
WORKDIR /workspace
EXPOSE 3080
ENTRYPOINT ["/usr/local/bin/dsh-entrypoint"]
