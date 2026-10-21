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
# GitHub Pages copy: a full standalone document.
# Title, fonts and styles go in <head>; everything from the first <div> on is the body.
split = page.index('<div class="wrap">')
head, body = page[:split], page[split:]
full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
        'body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
        + head + '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
import os
os.makedirs('docs', exist_ok=True)
open('docs/index.html', 'w').write(full)
open('docs/.nojekyll', 'w').write('')
print('docs/index.html written for GitHub Pages')
PY
