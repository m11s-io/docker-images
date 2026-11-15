# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b
# droast global ignore=DF036 reason="The digest-pinned official Caddy base supplies the startup command."
#
# Caddy 2 with the caddy-dns/cloudflare DNS provider module built in, so
# Caddy can complete Let's Encrypt DNS-01 challenges against Cloudflare
# directly. Needed for certs on hostnames that aren't internet-reachable
# (e.g. *.internal.example.com), where HTTP-01 can't work.
#
# Upstream reference: github.com/caddy-dns/cloudflare

ARG CADDY_BASE_IMAGE=caddy:2.11.7-alpine@sha256:e70b164da81ef698b3ad19af799ea6086ce6d9e48ed4079eb9fe26f6fbf14ee5
FROM caddy:2.11.7-builder-alpine@sha256:ef9b65adf9a224770c6d5f6d1ae1bf99bc3caaa78d8c4bae3ea949ee6984f301 AS builder

ARG CADDY_BASE_IMAGE
# renovate: datasource=github-tags depName=caddy-dns/cloudflare
ARG CLOUDFLARE_VERSION=v0.2.4
RUN CADDY_RELEASE="${CADDY_BASE_IMAGE#caddy:}" \
    && CADDY_RELEASE="${CADDY_RELEASE%%-alpine*}" \
    && xcaddy build "v${CADDY_RELEASE}" \
    --with "github.com/caddy-dns/cloudflare@${CLOUDFLARE_VERSION}"

FROM ${CADDY_BASE_IMAGE}

COPY --from=builder /usr/bin/caddy /usr/bin/caddy

USER 10001:10001
