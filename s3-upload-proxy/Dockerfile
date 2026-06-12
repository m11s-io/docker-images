FROM node:26.3.0-alpine
RUN npm install -g @m11s-io/s3-upload-proxy@0.1.2
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
