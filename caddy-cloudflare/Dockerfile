# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
#
# Caddy 2 with the caddy-dns/cloudflare DNS provider module built in, so
# Caddy can complete Let's Encrypt DNS-01 challenges against Cloudflare
# directly. Needed for certs on hostnames that aren't internet-reachable
# (e.g. *.internal.example.com), where HTTP-01 can't work.
#
# Upstream reference: github.com/caddy-dns/cloudflare

FROM caddy:2-builder-alpine@sha256:d6161a2c82fd58b3205048958fb6246d0c5d892beee8a47e90944610c4efd100 AS builder

RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare

FROM caddy:2-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
