FROM golang:1.26-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o redis-http-proxy .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /app/redis-http-proxy /redis-http-proxy
EXPOSE 80
ENTRYPOINT ["/redis-http-proxy"]
