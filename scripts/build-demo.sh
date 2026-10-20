#!/bin/sh
# Bundle the parser and inline it into demo/index.html (one self-contained page).
set -e
cd "$(dirname "$0")/.."
npx --yes esbuild@0.24.0 src/index.ts --bundle --format=iife --global-name=TP --minify --target=es2020 --outfile=demo/tp.bundle.js --log-level=warning
python3 - <<'PY'
bundle = open('demo/tp.bundle.js').read()
assert '</script' not in bundle
page = open('demo/template.html').read().replace('/*BUNDLE*/', bundle)
open('demo/index.html', 'w').write(page)
print(f'demo/index.html: {len(page)//1024} KB')
PY
