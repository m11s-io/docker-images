FROM node:26.12.1-alpine@sha256:40cd011b55415bc894e45b02fdd5a5dfde056921b7d23a64c74f80497af48797
# renovate: datasource=npm depName=@m11s-io/s3-upload-proxy
ARG S3_UPLOAD_PROXY_VERSION=0.1.3
RUN npm install -g "@m11s-io/s3-upload-proxy@${S3_UPLOAD_PROXY_VERSION}"
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
