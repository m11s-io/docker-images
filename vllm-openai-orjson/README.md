# vllm-openai-orjson

vLLM's official `vllm/vllm-openai` image with [`orjson`](https://github.com/ijl/orjson)
installed on top, for faster JSON serialization on endpoints like
`/v1/embeddings` and `/v1/chat/completions`.

To bump the base vLLM version: edit the `VLLM_BASE_IMAGE` default in
`Dockerfile` and the `vllm-openai-orjson` tag in
`.github/workflows/build.yaml`, then push — no vLLM source fork needed,
this just layers a pip install on the official image.
