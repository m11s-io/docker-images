"""Exercise image startup validation with real child HTTP servers."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("verify_image", Path(__file__).resolve().parents[1] / "comfyui/verify_image.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

SERVER = '''
import argparse, json
from http.server import BaseHTTPRequestHandler, HTTPServer
parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int)
args, _ = parser.parse_known_args()
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({'system': {}} if self.path == '/system_stats' else NODES).encode())
HTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
'''


class ComfyValidationTest(unittest.TestCase):
    def test_rocm_accepts_matching_packages_without_cuda(self):
        verify.check_torch_backend("rocm", "2.14.0+rocm10.1.0", "0.29.0a0+rocm10.1.0", None, "7.16.0")

    def test_backend_rejects_cpu_and_wrong_gpu_packages(self):
        for backend, torch, vision, cuda, hip in (
            ("rocm", "2.14.1+cu132", "0.29.1+cu132", "13.2", None),
            ("cuda", "2.14.0+rocm10.1.0", "0.29.0a0+rocm10.1.0", None, "7.16.0"),
            ("rocm", "2.14.0+cpu", "0.29.0+cpu", None, None),
            ("rocm", "2.14.0+rocm10.1.0", "0.29.0a0+rocm10.0.0", None, "7.16.0"),
            ("other", "2.14.0", "0.29.0", None, None),
        ):
            with self.subTest(backend=backend, torch=torch, vision=vision):
                with self.assertRaises(RuntimeError):
                    verify.check_torch_backend(backend, torch, vision, cuda, hip)

    def test_cuda_contract_still_accepts_matching_cuda(self):
        verify.check_torch_backend("cuda", "2.14.1+cu132", "0.29.1+cu132", "13.2", None)

    def test_constraints_detect_replaced_rocm_package(self):
        with tempfile.TemporaryDirectory() as directory:
            constraints = Path(directory, "constraints.txt")
            constraints.write_text("torch==2.14.0+rocm10.1.0\n")
            # Only the external installed-package inventory is substituted.
            with patch.object(verify, "version", return_value="2.14.1+cu132"):
                with self.assertRaisesRegex(RuntimeError, "expected.*rocm10.1.0.*installed.*cu132"):
                    verify.check_pinned_packages(constraints)

    def test_rejects_mixed_cuda_variants(self):
        with self.assertRaisesRegex(RuntimeError, "same CUDA variant"):
            verify.check_cuda_variants("2.14.1+cu132", "0.29.1+cu130")

    def test_accepts_matching_cuda_variants(self):
        verify.check_cuda_variants("2.14.1+cu132", "0.29.1+cu132")

    def check_backend(self, source):
        # Exercise Python's actual package loader without a GPU or Torch install.
        with tempfile.TemporaryDirectory() as directory:
            backend = Path(directory, "comfy_kitchen/backends/cuda")
            backend.mkdir(parents=True)
            for package in (backend.parent, backend.parent.parent):
                (package / "__init__.py").write_text("")
            (backend / "__init__.py").write_text(source)
            return subprocess.run(
                [sys.executable, "-c", f"import runpy; v = runpy.run_path({str(Path(verify.__file__).resolve())!r}); v['check_cuda_backend']()"],
                env={**os.environ, "PYTHONPATH": directory},
                capture_output=True, text=True,
            )

    def test_rejects_unavailable_native_cuda_backend(self):
        result = self.check_backend("_EXT_AVAILABLE = False\n_EXT_ERROR = 'libcublasLt missing'\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("libcublasLt missing", result.stderr)

    def test_accepts_loaded_native_cuda_backend_without_a_gpu(self):
        result = self.check_backend("_EXT_AVAILABLE = True\n_EXT_ERROR = None\n")
        self.assertEqual(result.returncode, 0, result.stderr)

    def exercise(self, source, *, gguf=False):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "main.py").write_text(source)
            with contextlib.chdir(directory), contextlib.redirect_stdout(io.StringIO()):
                verify.check_startup(gguf, timeout_seconds=5)

    def test_rejects_a_process_that_exits_before_ready(self):
        with self.assertRaisesRegex(RuntimeError, "exited"):
            self.exercise("raise SystemExit(7)")

    def test_rejects_missing_gguf_node_even_when_server_is_healthy(self):
        with self.assertRaisesRegex(RuntimeError, "UnetLoaderGGUF"):
            self.exercise("NODES = {}\n" + SERVER, gguf=True)

    def test_accepts_healthy_generic_server(self):
        self.exercise("NODES = {}\n" + SERVER)

    def test_accepts_healthy_gguf_server_with_loader(self):
        self.exercise("NODES = {'UnetLoaderGGUF': {}}\n" + SERVER, gguf=True)


if __name__ == '__main__':
    unittest.main()
