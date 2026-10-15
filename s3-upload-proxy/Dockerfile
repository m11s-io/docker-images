FROM node:26.12.0-alpine@sha256:6f08a523443ddedf52941874c203475b0ad503e859ad70cb26ab8be9a517dbd5
# renovate: datasource=npm depName=@m11s-io/s3-upload-proxy
ARG S3_UPLOAD_PROXY_VERSION=0.1.3
RUN npm install -g "@m11s-io/s3-upload-proxy@${S3_UPLOAD_PROXY_VERSION}"
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
