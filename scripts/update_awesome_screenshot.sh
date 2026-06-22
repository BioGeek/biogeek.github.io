#!/usr/bin/env bash
# Re-capture the "Awesome De Novo Peptide Sequencing" dashboard thumbnail used in the
# Projects section. The live site grows over time (more papers/methods), so this keeps
# images/projects/awesome_de_novo.png current. Run locally or via the update-awesome-screenshot
# GitHub Action; then `quarto render` to rebuild the site.
#
# Only overwrites the committed image when the new capture is *visually* different:
# a re-encoded PNG is byte-different even when pixel-identical, which would otherwise
# produce noisy "refresh" commits. We compare pixels (with a small fuzz) and skip if
# nothing meaningful changed.
#
# Requires a headless Chrome/Chromium and ImageMagick (`convert`/`compare`).
set -euo pipefail

URL="https://jeroen.vangoey.be/awesome_de_novo_peptide_sequencing/"
OUT="images/projects/awesome_de_novo.png"
THRESHOLD=20 # max differing pixels still considered "unchanged" (absorbs AA noise)
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

CHROME="$(command -v google-chrome-stable || command -v google-chrome \
  || command -v chromium-browser || command -v chromium || true)"
if [ -z "$CHROME" ]; then
  echo "No Chrome/Chromium binary found." >&2
  exit 1
fi

# Full-viewport screenshot of the live page.
"$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --window-size=1280,900 --screenshot="$TMP/full.png" "$URL"

# Crop the content area (title + stat cards + breakdown charts), excluding the
# right-hand "On this page" table of contents, then resize to a card-friendly width.
convert "$TMP/full.png" -crop 910x575+112+18 +repage -resize 480x -strip "$TMP/new.png"

if [ ! -f "$OUT" ]; then
  cp "$TMP/new.png" "$OUT"
  echo "created $OUT"
  exit 0
fi

# Count differing pixels (fuzz absorbs trivial encoder/anti-aliasing noise).
ae="$(compare -metric AE -fuzz 2% "$OUT" "$TMP/new.png" null: 2>&1 || true)"

case "$ae" in
  '' | *[!0-9]*)
    # Non-numeric => sizes differ or compare errored; treat as a real change.
    cp "$TMP/new.png" "$OUT"
    echo "updated $OUT (compare inconclusive: '$ae')"
    ;;
  *)
    if [ "$ae" -gt "$THRESHOLD" ]; then
      cp "$TMP/new.png" "$OUT"
      echo "updated $OUT ($ae pixels changed)"
    else
      echo "unchanged: $ae pixels differ (<= $THRESHOLD); keeping existing $OUT"
    fi
    ;;
esac
