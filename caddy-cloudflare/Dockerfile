# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
#
# Caddy 2 with the caddy-dns/cloudflare DNS provider module built in, so
# Caddy can complete Let's Encrypt DNS-01 challenges against Cloudflare
# directly. Needed for certs on hostnames that aren't internet-reachable
# (e.g. *.internal.example.com), where HTTP-01 can't work.
#
# Upstream reference: github.com/caddy-dns/cloudflare

FROM caddy:2-builder-alpine@sha256:1a1689db91cfb390b2d856a1b3774e796852822cd723fa54c475b272f82bb4b7 AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:2-alpine@sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
