"""Exercise image startup validation with real child HTTP servers."""
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

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
