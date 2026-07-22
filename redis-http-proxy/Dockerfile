FROM golang:1.26.5-alpine@sha256:0178a641fbb4858c5f1b48e34bdaabe0350a330a1b1149aabd498d0699ff5fb2 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o redis-http-proxy .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/redis-http-proxy /redis-http-proxy
EXPOSE 80
ENTRYPOINT ["/redis-http-proxy"]
