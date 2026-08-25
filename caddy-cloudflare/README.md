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
