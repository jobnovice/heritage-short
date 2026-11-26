# One command from a clean clone:  make setup && make film
PY := .venv/bin/python
.PHONY: setup smoke validate script narration keyframes sheets shots music radio film plan clean costs plan test showcase

setup:            ## create venv and install deps (needs python3 + ffmpeg on PATH)
	python3 -m venv .venv && $(PY) -m pip install -q -r requirements.txt
	@test -f .env || (cp .env.example .env && echo "created .env - add GEMINI_API_KEY")

smoke:            ## call every provider once, log latency to runs.jsonl
	$(PY) -m pipeline.smoke

validate:         ## schema + semantic validation of storyboard.json
	$(PY) -m pipeline.validate

narration: validate
	$(PY) -m pipeline.narration

sheets: validate
	$(PY) -m pipeline.keyframes --sheets-only

keyframes: validate
	$(PY) -m pipeline.keyframes

music: narration
	$(PY) -m pipeline.music

shots: keyframes narration
	$(PY) -m pipeline.shots

radio: narration music   ## Phase 1 checkpoint: narration + score on black
	$(PY) -m pipeline.assemble --radio

film: shots music        ## the whole pipeline; only changed shots regenerate
	$(PY) -m pipeline.assemble

clean:            ## delete generated media (keeps runs.jsonl)
	rm -rf outputs/narration outputs/keyframes outputs/shots outputs/music outputs/edit

costs:            ## regenerate the measured tables in COSTS.md from runs.jsonl
	$(PY) -m pipeline.costs

plan:             ## predict what `make film` would regenerate - no model is called
	$(PY) -m pipeline.plan || true

test:             ## offline test suite (no API keys, no network)
	$(PY) -m pytest -q tests

showcase:         ## build docs/index.html, the ship's-log provenance page (GitHub Pages)
	$(PY) -m pipeline.showcase $(if $(FILM_URL),--film-url $(FILM_URL),)
