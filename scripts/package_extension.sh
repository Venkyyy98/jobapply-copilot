#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTENSION_DIR="$ROOT_DIR/extension"
DIST_DIR="$ROOT_DIR/dist"
VERSION="$(node -e "console.log(require('$EXTENSION_DIR/manifest.json').version)")"
ZIP_PATH="$DIST_DIR/jobapply-copilot-extension-v$VERSION.zip"

mkdir -p "$DIST_DIR"
rm -f "$ZIP_PATH"

cd "$EXTENSION_DIR"
zip -r "$ZIP_PATH" . \
  -x '*.DS_Store' \
  -x '__MACOSX/*' \
  -x '*.map'

echo "Created $ZIP_PATH"
