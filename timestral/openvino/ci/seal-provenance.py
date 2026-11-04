#!/usr/bin/env python3
import json, os
from pathlib import Path
root=Path(os.environ['BUNDLE'])
(root/'evidence/provenance.json').write_text(json.dumps(dict(
    source=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'])))
