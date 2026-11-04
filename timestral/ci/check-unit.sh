#!/usr/bin/env bash
set -eo pipefail

# Check packaging and tag routing
uv run --frozen --project timestral/dependencies/cpu python -m unittest discover -s scripts -p 'test_*.py'

# Verify all candidate frozen locks
for project in timestral/dependencies/{cpu,cuda,rocm} timestral/openvino timestral/openvino/export; do
  python3 scripts/check_uv_lock.py "$project"
done

# Artifact publication guard tests
uv run --frozen --project timestral/dependencies/cpu python -m unittest discover -s timestral/openvino/export/tests

# Shared KServe regression tests
PYTHONPATH=timestral uv run --frozen --project timestral/dependencies/cpu python -m pytest timestral/tests timestral/openvino/tests -q -o asyncio_default_fixture_loop_scope=function

