FROM node:26.11.1-alpine@sha256:143494b1da2945f061539253adc65e4f1569ddf07da2d384c022c791a9d90a4a
RUN npm install -g @m11s-io/s3-upload-proxy@0.1.3
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
