FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-sandbox ca-certificates nginx-light tini bash \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 chromium \
    && useradd --system --uid 10001 --gid chromium --create-home chromium

COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /usr/local/bin/chromium-cdp
RUN chmod 0755 /usr/local/bin/chromium-cdp

USER chromium
EXPOSE 9222
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/chromium-cdp"]
