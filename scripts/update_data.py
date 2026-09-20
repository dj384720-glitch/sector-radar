#!/usr/bin/env python3
"""Daily refresh entry point. Add each licensed/public fetcher after mapping benchmarks."""
from datetime import datetime, timezone
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
sectors=json.loads((root/'data/sectors.json').read_text())
out=root/'docs/data';out.mkdir(exist_ok=True)
(out/'latest.json').write_text(json.dumps({'updated_at':datetime.now(timezone.utc).isoformat(),'status':'configuration_required','sectors':sectors},ensure_ascii=False,indent=2))
