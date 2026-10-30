# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b

FROM debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium=156.0.8078.47-1~deb12u1 chromium-sandbox=156.0.8078.47-1~deb12u1 ca-certificates=20250419~deb12u2 nginx-light=1.22.1-9+deb12u10 tini=0.19.0-1+b3 bash=5.2.15-2+b13 curl=7.88.1-10+deb12u15 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 chromium \
    && useradd --system --uid 10001 --gid chromium --create-home chromium

COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /usr/local/bin/chromium-cdp
RUN chmod 0755 /usr/local/bin/chromium-cdp

USER chromium
EXPOSE 9222
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl --fail --silent --show-error --max-time 3 --output /dev/null http://127.0.0.1:9222/json/version || exit 1
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/chromium-cdp"]
