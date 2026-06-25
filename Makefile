# Build commands for the website (Quarto) and the CV (RenderCV).
# Run `make` (or `make render`) to build both.

.PHONY: render cv site preview stars clean hooks

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

# Live-preview the website with auto-reload.
preview:
	quarto preview

# Refresh the InstaNovo GitHub star count from the API, then rebuild the site.
stars:
	python scripts/update_instanovo_stars.py
	quarto render

# Remove the built site.
clean:
	rm -rf docs

# Install the git hooks (re-renders the CV PDF when the YAML is committed).
hooks:
	git config core.hooksPath .githooks
	@echo "Git hooks enabled (core.hooksPath -> .githooks)."
