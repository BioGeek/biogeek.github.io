#!/usr/bin/env bash
# Re-capture the "Awesome De Novo Peptide Sequencing" dashboard thumbnail used in the
# Projects section. The live site grows over time (more papers/methods), so this keeps
# images/projects/awesome_de_novo.png current. Run locally or via the update-awesome-screenshot
# GitHub Action; then `quarto render` to rebuild the site.
#
# Requires a headless Chrome/Chromium and ImageMagick (`convert`).
set -euo pipefail

URL="https://jeroen.vangoey.be/awesome_de_novo_peptide_sequencing/"
OUT="images/projects/awesome_de_novo.png"
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
convert "$TMP/full.png" -crop 910x575+112+18 +repage -resize 480x -strip "$OUT"

echo "updated $OUT ($(identify -format '%wx%h' "$OUT"))"
