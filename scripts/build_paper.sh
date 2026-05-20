#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MANIFEST="results/latest/manifest.json"
PAPER_PDF="paper/paper.pdf"

if [[ ! -f "$MANIFEST" ]]; then
  echo "Missing $MANIFEST" >&2
  exit 1
fi

if grep -R "results/archive" paper >/dev/null 2>&1; then
  echo "paper/ must not reference results/archive/" >&2
  exit 1
fi

if find results -path "*artifact_manifest.json" -print | grep -q .; then
  echo "Forbidden complex artifact_manifest.json found under results/" >&2
  exit 1
fi

if find results -path "*run_manifest.json" -print | grep -q .; then
  echo "Forbidden per-run run_manifest.json found under results/" >&2
  exit 1
fi

bash scripts/render_paper_tables.sh

python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('results/latest/manifest.json').read_text())
status = manifest.get('status')
paper_allowed = bool(manifest.get('paper_allowed'))
source = Path('paper/paper.md').read_text() + '\n' + Path('paper/paper.tex').read_text()
if status != 'final' or not paper_allowed:
    if 'TODO' not in source:
        raise SystemExit('Manifest is not final/paper_allowed, so paper source must retain TODO placeholders.')
print(f"manifest status={status}; paper_allowed={paper_allowed}")
PY

mkdir -p paper

if command -v pdflatex >/dev/null 2>&1; then
  (
    cd paper
    pdflatex -interaction=nonstopmode -halt-on-error paper.tex
    pdflatex -interaction=nonstopmode -halt-on-error paper.tex
  )
else
  python3 - <<'PY'
from pathlib import Path
import textwrap

out = Path('paper/paper.pdf')
# Minimal dependency-free PDF fallback. It intentionally renders a concise,
# placeholder-safe paper preview when LaTeX is unavailable.
lines = [
    'Streaming Zero-Shot Industrial Anomaly Detection with CLIP',
    'Anonymous ACCV/LNCS-style paper scaffold',
    '',
    'Final artifact: paper/paper.pdf',
    'Result source: results/latest/ only',
    '',
    'Results status: TODO / placeholder until results/latest/manifest.json is final.',
    'No measured AUROC, AUPR, ECE, latency, or CRD-lite is claimed here.',
    '',
    'P0 scope: MVTec AD, VisA; iid and bursty streams; prevalence 0.05;',
    'epsilon in {0, 0.01, 0.05}; RareCLIP, PatchCore, WinCLIP, AnomalyCLIP.',
    '',
    'TODO: Replace this PDF with a LaTeX-built ACCV/LNCS manuscript after real P0 runs.',
]

wrapped = []
for line in lines:
    wrapped.extend(textwrap.wrap(line, width=88) or [''])

content_lines = []
y = 760
for line in wrapped[:42]:
    escaped = line.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')
    content_lines.append(f'BT /F1 11 Tf 54 {y} Td ({escaped}) Tj ET')
    y -= 16
stream = '\n'.join(content_lines).encode('ascii')

objects = []
objects.append(b'<< /Type /Catalog /Pages 2 0 R >>')
objects.append(b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
objects.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>')
objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
objects.append(b'<< /Length ' + str(len(stream)).encode('ascii') + b' >>\nstream\n' + stream + b'\nendstream')

pdf = bytearray(b'%PDF-1.4\n')
offsets = [0]
for i, obj in enumerate(objects, start=1):
    offsets.append(len(pdf))
    pdf.extend(f'{i} 0 obj\n'.encode('ascii'))
    pdf.extend(obj)
    pdf.extend(b'\nendobj\n')
xref_offset = len(pdf)
pdf.extend(f'xref\n0 {len(objects)+1}\n'.encode('ascii'))
pdf.extend(b'0000000000 65535 f \n')
for off in offsets[1:]:
    pdf.extend(f'{off:010d} 00000 n \n'.encode('ascii'))
pdf.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n'.encode('ascii'))
out.write_bytes(pdf)
print('pdflatex not found; wrote dependency-free placeholder PDF fallback.')
PY
fi

test -f "$PAPER_PDF"
echo "Built $PAPER_PDF"
