# m11s/s3-upload-proxy

Minimal Node.js service that accepts multipart file uploads over HTTP and stores them in any S3-compatible object store (MinIO, Cloudflare R2, AWS S3).

## What this is

Browsers cannot upload directly to MinIO without exposing credentials. This proxy sits in between: it receives a `multipart/form-data` POST from the browser, signs and forwards the file to S3 using server-side credentials, and returns the public URL of the stored object.

It is the server-side counterpart to the [`@m11s-io/decap-cms-media-library-s3`](https://www.npmjs.com/package/@m11s-io/decap-cms-media-library-s3) browser plugin, but is otherwise generic — any frontend that can POST a file can use it.

Built from the [`@m11s-io/s3-upload-proxy`](https://www.npmjs.com/package/@m11s-io/s3-upload-proxy) npm package.

## API

```
POST /upload[/:tenant]
Content-Type: multipart/form-data

file=<binary>
```

Returns:

```json
{ "url": "https://minio.example.com/bucket/prefix/tenant/1234567890-filename.jpg" }
```

The optional `:tenant` path segment is appended to the key prefix, allowing one instance to serve multiple tenants without credential isolation.

## Configuration

All configuration is via environment variables:

| Variable        | Required | Description                                                        |
|-----------------|----------|--------------------------------------------------------------------|
| `S3_ENDPOINT`   | yes      | S3-compatible endpoint URL (e.g. `https://minio.example.com`)     |
| `S3_BUCKET`     | yes      | Bucket name                                                        |
| `S3_PUBLIC_URL` | yes      | Base URL for returned file URLs (e.g. `https://minio.example.com/bucket`) |
| `S3_ACCESS_KEY` | yes      | S3 access key                                                      |
| `S3_SECRET_KEY` | yes      | S3 secret key                                                      |
| `S3_REGION`     | no       | S3 region (default: `us-east-1`)                                   |
| `S3_KEY_PREFIX` | no       | Prefix prepended to all object keys (default: none)                |
| `PORT`          | no       | HTTP port to listen on (default: `8082`)                           |

## Example

```bash
docker run -p 8082:8082 \
  -e S3_ENDPOINT=https://minio.example.com \
  -e S3_BUCKET=my-bucket \
  -e S3_PUBLIC_URL=https://minio.example.com/my-bucket \
  -e S3_ACCESS_KEY=mykey \
  -e S3_SECRET_KEY=mysecret \
  -e S3_KEY_PREFIX=uploads \
  m11s/s3-upload-proxy:0.1.1
```

Upload a file:

```bash
curl -F "file=@photo.jpg" http://localhost:8082/upload/mytenant
# {"url":"https://minio.example.com/my-bucket/uploads/mytenant/1234567890-photo.jpg"}
```
