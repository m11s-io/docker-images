# vllm-openai

vLLM's official `vllm/vllm-openai` image with [`orjson`](https://github.com/ijl/orjson)
installed on top, for faster JSON serialization on endpoints like
`/v1/embeddings` and `/v1/chat/completions`.

## Tags and architecture

This image supports `linux/amd64` only. Public tags are `latest-orjson`, the upstream
release version with the flavor suffix (for example, `v0.32.0-orjson`), and a
source commit tag ending in `-orjson`. The upstream
base image uses an `-x86_64` suffix; our published tags omit it.

```sh
docker pull m11s/vllm-openai:latest-orjson
```
