package main

import "encoding/base64"

// encode converts a Redis value to the Upstash REST API wire format.
// Strings and byte slices are base64-encoded; integers and nil pass through.
func encode(v interface{}) interface{} {
	switch val := v.(type) {
	case nil:
		return nil
	case int64:
		return val
	case string:
		return base64.StdEncoding.EncodeToString([]byte(val))
	case []byte:
		return base64.StdEncoding.EncodeToString(val)
	case []interface{}:
		out := make([]interface{}, len(val))
		for i, item := range val {
			out[i] = encode(item)
		}
		return out
	default:
		return val
	}
}
