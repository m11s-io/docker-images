package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/redis/go-redis/v9"
)

var (
	rdb   *redis.Client
	token string
)

func main() {
	token = os.Getenv("TOKEN")
	if token == "" {
		log.Fatal("TOKEN environment variable is required")
	}

	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379"
	}

	opts, err := redis.ParseURL(redisURL)
	if err != nil {
		log.Fatalf("invalid REDIS_URL: %v", err)
	}

	rdb = redis.NewClient(opts)

	if err := rdb.Ping(context.Background()).Err(); err != nil {
		log.Fatalf("cannot reach Redis at %s: %v", redisURL, err)
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "80"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/pipeline", auth(handlePipeline))
	mux.HandleFunc("/multi-exec", auth(handleMultiExec))
	mux.HandleFunc("/healthz", handleHealthz)
	mux.HandleFunc("/", auth(handleCommand))

	log.Printf("redis-http-proxy listening on :%s", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}

func auth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		bearer := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		if bearer == token || r.URL.Query().Get("_token") == token {
			next(w, r)
			return
		}
		writeError(w, http.StatusUnauthorized, "Unauthorized")
	}
}

func handleHealthz(w http.ResponseWriter, r *http.Request) {
	if err := rdb.Ping(context.Background()).Err(); err != nil {
		http.Error(w, "redis unavailable", http.StatusServiceUnavailable)
		return
	}
	w.WriteHeader(http.StatusOK)
}
