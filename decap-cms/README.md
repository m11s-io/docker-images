# m11s/decap-cms

Nginx-based Docker image that serves [Decap CMS](https://decapcms.org/) with a custom S3/MinIO media library plugin.

## What this is

Decap CMS is a pure frontend SPA — there is no server. It runs entirely in the browser and talks directly to the GitLab API to read/write Markdown files. Authentication uses GitLab PKCE OAuth (no client secret required).

This image packages:
- The Decap CMS HTML entrypoint
- The [`@m11s-io/decap-cms-media-library-s3`](https://www.npmjs.com/package/@m11s-io/decap-cms-media-library-s3) plugin (loaded via unpkg)
- nginx to serve the static files
- A startup script that generates per-tenant `config.yml` files from a `tenants.json` or environment variables

## S3 media library plugin

Decap CMS has no built-in S3/MinIO support. The `@m11s-io/decap-cms-media-library-s3` plugin fills that gap.

When an editor clicks the media button, the plugin opens a file picker, POSTs the selected file to an `upload_url` endpoint, and inserts the returned public URL into the content. The upload endpoint is a separate service you run alongside the CMS (e.g. a small Express proxy that signs and forwards to MinIO).

The plugin is loaded as an IIFE before Decap initialises (`window.CMS_MANUAL_INIT = true`), registered with `CMS.registerMediaLibrary`, then `CMS.init()` is called manually. This ordering is required because Decap auto-initialises synchronously on script load and would fail to find the plugin otherwise.

## Multi-tenant mode

Mount a `tenants.json` at `/etc/decap/tenants.json`. The entrypoint generates a separate `config.yml` and nginx root per hostname.

```json
[
  {
    "hostname": "cms.example.com",
    "gitlabRepo": "myorg/myrepo",
    "gitlabBranch": "main",
    "gitlabAppId": "abc123",
    "uploadUrl": "https://upload.example.com/upload"
  },
  {
    "hostname": "cms.other.com",
    "gitlabRepo": "myorg/other",
    "gitlabBranch": "main",
    "gitlabAppId": "def456",
    "uploadUrl": "https://upload.other.com/upload"
  }
]
```

nginx uses a `map $host $tenant_root` directive to route each hostname to its generated static directory. One container, many tenants.

## Single-tenant mode

If no `tenants.json` is present, configure via environment variables:

```bash
docker run -p 80:80 \
  -e GITLAB_REPO=myorg/myrepo \
  -e GITLAB_BRANCH=main \
  -e GITLAB_APP_ID=abc123 \
  -e UPLOAD_URL=https://upload.example.com/upload \
  m11s/decap-cms:latest-s3
```

The CMS is then available at `http://localhost/admin/`.

## GitLab OAuth setup

Create a GitLab OAuth application (User Settings → Applications):
- **Redirect URI**: `http(s)://<your-cms-host>/admin/`
- **Scopes**: `api`
- **PKCE**: enabled (no secret needed)

Use the Application ID as `GITLAB_APP_ID` / `gitlabAppId`.

## config.yml

The default `config.yml.template` defines a single `posts` collection. For custom collections, mount your own `config.yml.template` at `/etc/decap/config.yml.template` using the same `${VAR}` placeholders, or provide complete per-tenant configs via a mounted directory.
