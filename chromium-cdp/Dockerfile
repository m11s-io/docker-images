FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-sandbox ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 chromium \
    && useradd --system --uid 10001 --gid chromium --create-home chromium

COPY entrypoint.sh /usr/local/bin/chromium-cdp
RUN chmod 0755 /usr/local/bin/chromium-cdp

USER chromium
EXPOSE 9222
ENTRYPOINT ["/usr/local/bin/chromium-cdp"]
