# syntax=docker/dockerfile:1.28.0@sha256:bb22d9815c728170f72750f4e5b0d672e06176142e1d602c7e66c050100b7e5b

FROM node:26.12.1-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797
# renovate: datasource=npm depName=@m11s-io/s3-upload-proxy
ARG S3_UPLOAD_PROXY_VERSION=0.1.3
RUN npm install -g "@m11s-io/s3-upload-proxy@${S3_UPLOAD_PROXY_VERSION}"
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
