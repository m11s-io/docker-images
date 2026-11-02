"""Run the unmodified server entry point with bounded, external GPU telemetry.

This wrapper changes neither inference nor admission. GPU counters are sampled
only after the serving process itself initializes its device. Framework peaks
are cumulative for this server lifetime; free/total are whole-device counters.
"""
import json
import os
from pathlib import Path
import runpy
import threading
import time


def main():
    if os.environ.get('TIMESTRAL_BACKEND') in ('cuda','rocm'):
        def sample():
            import torch
            path=Path(os.environ['BENCHMARK_GPU_SAMPLES'])
            while True:
                if torch.cuda.is_initialized():
                    free,total=torch.cuda.mem_get_info()
                    item=dict(monotonic_seconds=time.monotonic(),
                        server_allocated_bytes=torch.cuda.memory_allocated(),
                        server_reserved_bytes=torch.cuda.memory_reserved(),
                        server_peak_allocated_bytes_cumulative=torch.cuda.max_memory_allocated(),
                        server_peak_reserved_bytes_cumulative=torch.cuda.max_memory_reserved(),
                        whole_device_free_bytes=free,whole_device_total_bytes=total,
                        device_name=torch.cuda.get_device_name())
                    with path.open('a') as stream:stream.write(json.dumps(item)+'\n')
                time.sleep(1)
        threading.Thread(target=sample,daemon=True).start()
    runpy.run_module('serving',run_name='__main__')


if __name__=='__main__':main()
