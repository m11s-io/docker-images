"""Strict versioned OpenVINO preview artifacts and capability checks."""
import hashlib
import json
from pathlib import Path
import re

SOURCE_REVISION='a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff'
PREVIEW_REVISION='bdd20cfc15a3fea0e4cb5ccef37f8d3ca7aa335f'
MODEL_REVISIONS={'mistralai/Timestral-5M':PREVIEW_REVISION,
                 'mistralai/Timestral-209M':'9874d252ab0aae16f7f7c999f98f98d6ad7d8365'}
PROFILE_FILES={'config.json','LICENSE','README.md',*(f'block-{h}.{ext}' for h in range(1,6) for ext in ('xml','bin'))}


def verify_profiles(root, manifest_sha256, model_id, model_revision):
    root=Path(root)
    if root.is_symlink() or not root.is_dir() or not re.fullmatch('[0-9a-f]{64}',manifest_sha256):
        raise ValueError('invalid profile directory or manifest digest')
    paths=list(root.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise ValueError('profile bundle must contain only regular files')
    if {p.name for p in paths} != PROFILE_FILES|{'manifest.json'}:
        raise ValueError('unexpected or missing profile files')
    if (root/'manifest.json').stat().st_size > 65536:
        raise ValueError('manifest exceeds size limit')
    if (root/'config.json').stat().st_size > 1_048_576:
        raise ValueError('profile configuration exceeds size limit')
    raw=(root/'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest_sha256:
        raise ValueError('manifest checksum mismatch')
    manifest=json.loads(raw)
    if (manifest.get('format')!='timestral-openvino-profiles-v1' or
        manifest.get('source_revision')!=SOURCE_REVISION or
        manifest.get('model_id')!=model_id or model_id not in MODEL_REVISIONS or
        manifest.get('model_revision')!=model_revision or model_revision!=MODEL_REVISIONS.get(model_id) or
        manifest.get('precision')!='FP32' or manifest.get('max_context')!=256 or
        manifest.get('per_shot_horizon_patches')!=5 or
        set(manifest.get('files',{}))!=PROFILE_FILES):
        raise ValueError('unsupported artifact identity or profile contract')
    for name,expected in manifest['files'].items():
        path=root/name
        if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or path.stat().st_size>1_073_741_824:
            raise ValueError('invalid profile checksum or file size')
        with path.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
                raise ValueError('profile checksum mismatch')
    return manifest


def validate_preview_request(inputs):
    from kserve.errors import InvalidInput
    if (inputs.context.shape[:2]!=(1,1) or inputs.context.shape[-1]>256 or
            inputs.prediction_length>320 or inputs.covariates):
        raise InvalidInput('OpenVINO preview supports one target row, context<=256, horizon<=320, no covariates')
