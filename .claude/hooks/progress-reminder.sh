#!/usr/bin/env bash
# Stop hook: podseti ako ima izmena u repo-u a PROGRESS.md nije azuriran danas.
# Cisto informativno - nikad ne blokira, samo ispise systemMessage kad je uslov ispunjen.

PROGRESS_FILE="PROGRESS.md"

[ -d ".git" ] || exit 0
[ -f "$PROGRESS_FILE" ] || exit 0

if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
  exit 0
fi

TODAY=$(date +%Y-%m-%d)
LAST_COMMIT_EDIT=$(git log -1 --format=%cd --date=short -- "$PROGRESS_FILE" 2>/dev/null)
FILE_MTIME=$(date -r "$PROGRESS_FILE" +%Y-%m-%d 2>/dev/null)

if [ "$LAST_COMMIT_EDIT" = "$TODAY" ] || [ "$FILE_MTIME" = "$TODAY" ]; then
  exit 0
fi

echo '{"systemMessage": "Podsetnik: PROGRESS.md nije azuriran danas iako ima izmena u repo-u - razmisli da li treba zatvoriti sesiju."}'
