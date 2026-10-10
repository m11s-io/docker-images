FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587

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
