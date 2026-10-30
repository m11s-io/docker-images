"""Exercise the exported IR through an actual KServe v2 REST endpoint."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

import numpy as np
from export import hardware, validate_outputs

OVMS_IMAGE = "openvino/model_server:2026.4.1@sha256:148e3fe802261ed0b5b634de3bbccdefe7176a218ec34a88e382b40704c34a1c"


def parse_response(response: dict):
    try:
        outputs = response["outputs"]
        if len(outputs) != 1:
            raise ValueError("expected exactly one output")
        output = outputs[0]
        if (output["name"] != "quantiles" or output["datatype"] != "FP32"
                or output["shape"] != [1, 32, 21]):
            raise ValueError("unexpected output contract")
        data = np.array(output["data"], dtype=np.float32)
        if data.size != 672 or not np.isfinite(data).all():
            raise ValueError("invalid output values")
        return data.reshape(1, 32, 21)
    except (KeyError, TypeError) as error:
        raise ValueError("malformed KServe response") from error


def request(url: str, body=None):
    encoded = None if body is None else json.dumps(body, allow_nan=False).encode()
    req = urllib.request.Request(url, data=encoded, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("oversized OVMS response")
        return json.loads(raw) if raw else {}


def validate(bundle: Path, url: str, startup_timeout: float = 120) -> None:
    if not url.startswith("http://127.0.0.1:"):
        raise ValueError("validation endpoint must be local")
    deadline = time.monotonic() + startup_timeout
    while True:
        try:
            request(url + "/v2/models/model/ready")
            break
        except (OSError, urllib.error.URLError):
            if time.monotonic() >= deadline:
                raise TimeoutError("OVMS model did not become ready")
            time.sleep(1)
    fixtures = json.loads((bundle / "validation-fixtures.json").read_text())
    results = {}
    for name, case in fixtures.items():
        body = {"inputs": [
            {"name": "context", "shape": [1, 128], "datatype": "FP32",
             "data": np.array(case["context"], dtype=np.float32).ravel().tolist()},
            {"name": "observed", "shape": [1, 128], "datatype": "BOOL",
             "data": np.array(case["observed"], dtype=np.bool_).ravel().tolist()},
        ], "outputs": [{"name": "quantiles"}]}
        actual = parse_response(request(url + "/v2/models/model/infer", body))
        results[name] = validate_outputs(np.array(case["quantiles"], dtype=np.float32), actual)
    report = {"passed": True, "image": OVMS_IMAGE, "protocol": "KServe v2 REST",
              "hardware": hardware(), "cases": results, "precision_hint": "f32"}
    (bundle / "ovms-validation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:18000")
    options = parser.parse_args()
    validate(options.bundle, options.url)
