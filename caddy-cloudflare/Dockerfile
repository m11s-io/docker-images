# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#
# Caddy 2 with the caddy-dns/cloudflare DNS provider module built in, so
# Caddy can complete Let's Encrypt DNS-01 challenges against Cloudflare
# directly. Needed for certs on hostnames that aren't internet-reachable
# (e.g. *.internal.example.com), where HTTP-01 can't work.
#
# Upstream reference: github.com/caddy-dns/cloudflare

ARG CADDY_BASE_IMAGE=caddy:2.11.7-alpine@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f
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
