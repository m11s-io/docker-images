FROM node:26.12.0-alpine@sha256:6f08a523443ddedf52941874c203475b0ad503e859ad70cb26ab8be9a517dbd5
RUN npm install -g @m11s-io/s3-upload-proxy@0.1.3
USER node
EXPOSE 8082
CMD ["s3-upload-proxy"]
