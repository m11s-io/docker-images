# vllm-openai-orjson

vLLM's official `vllm/vllm-openai` image with [`orjson`](https://github.com/ijl/orjson)
installed on top, for faster JSON serialization on endpoints like
`/v1/embeddings` and `/v1/chat/completions`.

## Tags and architecture

This image supports `linux/amd64` only. Public tags are `latest`, the upstream
release version (for example, `v0.32.0`), and a source commit tag. The upstream
base image uses an `-x86_64` suffix; our published tags omit it.
