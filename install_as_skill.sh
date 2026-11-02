#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="viral-structure-teardown"
TARGET_ROOT="${1:-${CODEX_HOME:-$HOME/.codex}/skills}"
TARGET_DIR="$TARGET_ROOT/$SKILL_NAME"
STAGING_ROOT="$(mktemp -d)"
STAGING_DIR="$STAGING_ROOT/$SKILL_NAME"

cleanup() {
  rm -rf "$STAGING_ROOT"
}
trap cleanup EXIT

mkdir -p "$TARGET_ROOT"
mkdir -p "$STAGING_DIR"
cp -R "$SOURCE_DIR/." "$STAGING_DIR"
rm -rf "$STAGING_DIR/.git" "$STAGING_DIR/.local-evals"

if [[ -e "$TARGET_DIR" ]]; then
  BACKUP_DIR="$TARGET_DIR.backup-$(date +%Y%m%d%H%M%S)"
  mv "$TARGET_DIR" "$BACKUP_DIR"
  printf 'Previous installation moved to %s\n' "$BACKUP_DIR"
fi
mv "$STAGING_DIR" "$TARGET_DIR"

printf 'Installed %s to %s\n' "$SKILL_NAME" "$TARGET_DIR"
