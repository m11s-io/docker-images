# caddy-cloudflare

Caddy 2 with the [`caddy-dns/cloudflare`](https://github.com/caddy-dns/cloudflare)
DNS provider module built in, so Caddy can complete Let's Encrypt DNS-01
challenges against a Cloudflare-hosted zone itself. DNS-01 only needs a TXT
record during issuance — it doesn't require the hostname being certified to
resolve publicly — so this is what lets an internal-only hostname (e.g.
`app.internal.example.com`) get a real Let's Encrypt cert with automatic
renewal, no separate ACME client needed.

## Usage

```caddyfile
app.internal.example.com {
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }
    reverse_proxy backend.internal.example.com:9000
}
```

`CF_API_TOKEN` needs `Zone:Read` and `DNS:Edit` scoped to the target zone.

## Runtime user and mounted files

The image runs as UID/GID `10001:10001` and inherits the official Caddy startup
command: `caddy run --config /etc/caddy/Caddyfile --adapter caddyfile`.

Mount a Caddyfile readable by UID `10001`. Persistent `/data/caddy` and
`/config/caddy` storage must be writable by that user, including existing
certificate keys and ACME account files when migrating from a root deployment.
Check host ACLs as well as Unix modes; Synology ACLs can deny access even when
numeric ownership appears correct. Keep private keys and environment files
restricted rather than making them readable by everyone.

Ports above 1024 need no privileged-port capability. Binding ports 80/443 depends
on the host's port policy and allowed Linux capabilities; verify those settings
for the target runtime, especially with host networking.

## Versioning

Publish tags follow `CADDY_BASE_IMAGE` in the Dockerfile, replacing `-alpine`
with `-cloudflare`. The compiled binary explicitly uses that Caddy release. The Cloudflare
plugin is pinned separately and tracked by Renovate. Plugin and base digest
updates republish the version alias and produce a new source commit tag.
