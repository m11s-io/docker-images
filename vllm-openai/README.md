# vllm-openai

vLLM's official `vllm/vllm-openai` image with a couple of additions layered on top:

- [`orjson`](https://github.com/ijl/orjson) for faster JSON serialization on
  endpoints like `/v1/embeddings` and `/v1/chat/completions`.
- [`lmcache`](https://github.com/LMCache/LMCache) for KV-cache offload/sharing.
  Installed against the cu130 torch wheel index to match this image's CUDA
  13.0.3 runtime - see the comment in `Dockerfile` for why that matters.
