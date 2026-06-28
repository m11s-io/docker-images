package main

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"

	"github.com/redis/go-redis/v9"
)

func handleCommand(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var args []interface{}

	// Support URL-path form: POST /SET/mykey/myvalue
	path := strings.TrimPrefix(r.URL.Path, "/")
	if path != "" {
		parts := strings.Split(path, "/")
		args = make([]interface{}, len(parts))
		for i, p := range parts {
			args[i] = p
		}
	} else {
		if err := json.NewDecoder(r.Body).Decode(&args); err != nil {
			writeError(w, http.StatusBadRequest, "invalid JSON body")
			return
		}
	}

	val, err := rdb.Do(context.Background(), args...).Result()
	if err == redis.Nil {
		writeResult(w, nil)
		return
	}
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeResult(w, encode(val))
}

func handlePipeline(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var commands [][]interface{}
	if err := json.NewDecoder(r.Body).Decode(&commands); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	pipe := rdb.Pipeline()
	cmds := make([]*redis.Cmd, len(commands))
	ctx := context.Background()
	for i, cmd := range commands {
		cmds[i] = pipe.Do(ctx, cmd...)
	}
	pipe.Exec(ctx) //nolint:errcheck // individual cmd errors checked below

	results := make([]map[string]interface{}, len(cmds))
	for i, cmd := range cmds {
		val, err := cmd.Result()
		if err == redis.Nil {
			results[i] = map[string]interface{}{"result": nil}
		} else if err != nil {
			results[i] = map[string]interface{}{"error": err.Error()}
		} else {
			results[i] = map[string]interface{}{"result": encode(val)}
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results) //nolint:errcheck
}

func handleMultiExec(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}

	var commands [][]interface{}
	if err := json.NewDecoder(r.Body).Decode(&commands); err != nil {
		writeError(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	// TxPipeline acquires a dedicated connection and wraps commands in MULTI/EXEC —
	// no shared-connection race condition possible.
	pipe := rdb.TxPipeline()
	cmds := make([]*redis.Cmd, len(commands))
	ctx := context.Background()
	for i, cmd := range commands {
		cmds[i] = pipe.Do(ctx, cmd...)
	}
	pipe.Exec(ctx) //nolint:errcheck // individual cmd errors checked below

	results := make([]map[string]interface{}, len(cmds))
	for i, cmd := range cmds {
		val, err := cmd.Result()
		if err == redis.Nil {
			results[i] = map[string]interface{}{"result": nil}
		} else if err != nil {
			results[i] = map[string]interface{}{"error": err.Error()}
		} else {
			results[i] = map[string]interface{}{"result": encode(val)}
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results) //nolint:errcheck
}

func writeResult(w http.ResponseWriter, result interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"result": result}) //nolint:errcheck
}

func writeError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": msg}) //nolint:errcheck
}
