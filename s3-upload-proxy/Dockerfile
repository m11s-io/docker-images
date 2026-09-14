FROM node:26.8.2-alpine@sha256:ef24c5053d50fdc3e4e56eb4e7ddb7861874ab0fdc797046ba897581deb8e868
RUN npm install -g @m11s-io/s3-upload-proxy@0.1.3
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
