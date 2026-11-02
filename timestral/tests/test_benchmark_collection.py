import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import pytest

spec=importlib.util.spec_from_file_location('benchmark_collection',Path(__file__).parents[1]/'benchmarks/collect.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)


def bundle(path, contents, expected):
    with tarfile.open(path,'w:gz') as tar:
        for name,data in contents.items():
            info=tarfile.TarInfo(name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
        data=json.dumps({'status':'measured','files':expected}).encode()
        info=tarfile.TarInfo('done.json');info.size=len(data);tar.addfile(info,io.BytesIO(data))


def test_collected_bundle_requires_every_immutable_checksum(tmp_path):
    path=tmp_path/'results.tar.gz';data=b'{"status":"measured"}'
    bundle(path,{'summary.json':data},{'summary.json':hashlib.sha256(data).hexdigest()})
    assert collector.verify_bundle(path)['status']=='measured'
    bundle(path,{'summary.json':b'corrupt'},{'summary.json':hashlib.sha256(data).hexdigest()})
    with pytest.raises(ValueError):collector.verify_bundle(path)


@pytest.mark.parametrize('name',['../outside','/absolute','nested/file'])
def test_collection_does_not_accept_unexpected_archive_paths(tmp_path,name):
    path=tmp_path/'results.tar.gz';data=b'test'
    bundle(path,{name:data},{name:hashlib.sha256(data).hexdigest()})
    with pytest.raises(ValueError):collector.verify_bundle(path)
