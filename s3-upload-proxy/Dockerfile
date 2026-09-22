FROM node:26.10.0-alpine@sha256:0b36e8c136b94cd4fcf02188228e76c31ad5872eef3fec8cbd2eee500cfd9e80
RUN npm install -g @m11s-io/s3-upload-proxy@0.1.3
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
