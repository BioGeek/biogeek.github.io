# Build commands for the website (Quarto) and the CV (RenderCV).
# Run `make` (or `make render`) to build both.

.PHONY: render cv site og preview stars inat strava openalex clean hooks

# Build the CV first, then the site, so the deployed site serves the latest CV PDF.
render: cv site

# Render the CV to files/jeroen-van-goey-cv.pdf.
# Skip HTML/Markdown/PNG (gitignored), but keep Typst generation: skipping it
# makes RenderCV compile the PDF from a stale .typ instead of the current YAML.
cv:
	rendercv render Jeroen_Van_Goey_CV.yaml --dont-generate-html --dont-generate-markdown --dont-generate-png

# Render the website into docs/.
site:
	quarto render

# Re-render the Open Graph card (images/og-card.html) to images/og-image.jpg.
# The card is a 1200x630 HTML template; the JPEG is what LinkedIn, Slack and
# Bluesky actually display, so editing the template alone changes nothing.
# Not part of `render` - it only needs running when the card's text changes.
og:
	# Rendered at 1200x800 and cropped: at a window height of exactly 630 Chrome
	# clips the absolutely-positioned footer bar and leaves the bottom 84px white.
	# --virtual-time-budget waits for the Inter webfont from Google Fonts; without
	# it the screenshot can fire on fallback metrics and the text reflows.
	google-chrome --headless --disable-gpu --hide-scrollbars \
	  --screenshot=/tmp/og-image.png --window-size=1200,800 \
	  --virtual-time-budget=5000 \
	  "file://$(CURDIR)/images/og-card.html"
	convert /tmp/og-image.png -crop 1200x630+0+0 +repage -quality 92 images/og-image.jpg
	@rm -f /tmp/og-image.png
	@identify images/og-image.jpg


# Live-preview the website with auto-reload.
preview:
	quarto preview

# Refresh the InstaNovo GitHub star count from the API, then rebuild the site.
stars:
	python scripts/update_instanovo_stars.py
	quarto render

# Refresh iNaturalist observation data (public API, no secrets), then rebuild.
inat:
	python scripts/fetch_inaturalist.py
	quarto render

# Refresh Strava activity data, then rebuild.
# Needs STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN in the env.
strava:
	python scripts/fetch_strava.py
	quarto render

# Sync citation metrics from OpenAlex (public API, no secrets), then rebuild.
openalex:
	python scripts/update_openalex.py
	quarto render

# Recompute the "N publications" intro count from the cards listed. Also runs
# automatically as a Quarto pre-render step on every build.
pubcount:
	python scripts/update_pubcount.py

# Remove the built site.
clean:
	rm -rf docs

# Install the git hooks (re-renders the CV PDF when the YAML is committed).
hooks:
	git config core.hooksPath .githooks
	@echo "Git hooks enabled (core.hooksPath -> .githooks)."
