#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../editor/wodcraft-vscode"

if ! command -v vsce >/dev/null 2>&1; then
  echo "vsce not found. Install with: npm i -g @vscode/vsce" >&2
  exit 1
fi

vsce package
echo "VSIX created in $(pwd)"

