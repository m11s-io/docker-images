#!/usr/bin/env python3
import json, os
from pathlib import Path
records=[json.loads(p.read_text()) for p in Path('receipts').rglob('standard-publication.json')]
models={r['model_id']:r for r in records}
expected={f'mistralai/Timestral-{size}' for size in ('5M','28M','123M','209M')}
if len(records)!=4 or set(models)!=expected:
    raise ValueError('release requires exactly one receipt for each model')
if any(r['source']!=os.environ['GITHUB_SHA'] or r['run']!=os.environ['GITHUB_RUN_ID'] for r in records):
    raise ValueError('release receipts must come from this source and run')
images={r['image'] for r in records}
if len(images)!=1:
    raise ValueError('all models must use the same immutable runtime image')
release=dict(source=os.environ['GITHUB_SHA'],image=images.pop(),models=models)
Path('timestral-openvino-release.json').write_text(json.dumps(release,indent=2)+'\n')
with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
    f.write('```json\n'+json.dumps(release,indent=2)+'\n```\n')
