FROM node:26.9.0-alpine@sha256:dbaa92e5758cbbcf85d65d5403fdb530fe3442cbe8c6dbfb7ef23365450d5070
RUN npm install -g @m11s-io/s3-upload-proxy@0.1.3
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
