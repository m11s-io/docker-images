"""Fetch the pinned upstream package without changing or forking its source."""
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request

REVISION = 'a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff'
SHA256 = 'be734f502f88e95b138558d765f3ad3b3ac8d2662270f9cf8b03138359828150'


def fetch(destination):
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / 'source.tar.gz'
        with urllib.request.urlopen(f'https://codeload.github.com/mistralai/timestral/tar.gz/{REVISION}', timeout=60) as response:
            data = response.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError('upstream source archive mismatch')
        archive.write_bytes(data)
        with tarfile.open(archive) as stream:
            members = stream.getmembers()
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                    raise ValueError('unsafe upstream archive')
            stream.extractall(Path(tmp) / 'tree', filter='data')
        upstream = Path(tmp) / 'tree' / f'timestral-{REVISION}'
        shutil.copytree(upstream / 'src', destination / 'src')
        shutil.copyfile(upstream / 'LICENSE', destination / 'LICENSE')
        (destination / 'SOURCE_REVISION').write_text(REVISION + '\n')


if __name__ == '__main__':
    import sys
    fetch(Path(sys.argv[1]))
