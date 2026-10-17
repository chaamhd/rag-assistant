#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/astral-sh/uv.git"
DEST="data/raw"
TMP="$(mktemp -d)"

git clone --depth 1 "$REPO_URL" "$TMP/repo"

rm -rf "$DEST"
mkdir -p "$DEST"

rsync -a --max-size=100K --prune-empty-dirs \
  --include='*/' --include='*.md' --exclude='*' \
  "$TMP/repo/docs/" "$DEST/"

git -C "$TMP/repo" rev-parse HEAD > data/SOURCE.txt
echo "$REPO_URL" >> data/SOURCE.txt

rm -rf "$TMP"
echo "Fichiers récupérés : $(find "$DEST" -name '*.md' | wc -l)"