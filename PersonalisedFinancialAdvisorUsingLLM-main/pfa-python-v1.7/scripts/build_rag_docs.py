#!/usr/bin/env python3
import csv, re, sys
from pathlib import Path
src=Path(sys.argv[1] if len(sys.argv)>1 else 'data/nifty50_training.csv')
out=Path(sys.argv[2] if len(sys.argv)>2 else 'knowledge-base')
out.mkdir(parents=True, exist_ok=True)
# Remove generated NIFTY docs only; leave hand-authored finance KB markdown untouched.
for p in out.glob('nifty50_*.md'): p.unlink()
with src.open(encoding='utf-8-sig', newline='') as f:
    for i,row in enumerate(csv.DictReader(f),1):
        cat=(row.get('category') or 'uncategorized').strip()
        safe=re.sub(r'[^a-zA-Z0-9_-]+','_',cat)[:50]
        text=(f"# NIFTY 50 Historical Example\n\n**Category:** {cat}\n\n"
              f"## Instruction\n{row.get('instruction','')}\n\n"
              f"## Context\n{row.get('context','')}\n\n"
              f"## Response\n{row.get('response','')}\n\n"
              f"## Source\n{row.get('source','')}\n")
        (out/f'nifty50_{i:04d}_{safe}.md').write_text(text,encoding='utf-8')
print(f'Generated {i} NIFTY 50 RAG documents in {out}')
