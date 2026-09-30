# Lecture slides. Run from the repo root (the SimplePlus theme and the Inter
# font path are resolved relative to the working directory).
PY      ?= .venv/bin/python
LATEXMK ?= latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=slides/build
INTER_URL = https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip

.PHONY: slides figures fonts clean-slides guides clean-guides

slides: figures fonts/Inter-4.1
	$(LATEXMK) slides/imu/imu.tex

figures:
	$(PY) -m teaching_sims.slides.imu_figures --out slides/figures/imu

# Study guides (Canvas-ready HTML). IMAGE_BASE rewrites image URLs for Canvas, e.g.
#   make guides IMAGE_BASE=/courses/12345/file_contents/course%20files/imu-guides/
IMAGE_BASE ?=
guides:
	$(PY) -m teaching_sims.guides.figures --out guides/imu/img
	$(PY) -m teaching_sims.guides.build --image-base "$(IMAGE_BASE)"

clean-guides:
	rm -rf guides/imu/img guides/imu/canvas guides/imu/preview

fonts: fonts/Inter-4.1

fonts/Inter-4.1:
	mkdir -p fonts
	curl -sSL -o fonts/Inter-4.1.zip $(INTER_URL)
	unzip -q -o fonts/Inter-4.1.zip -d fonts/Inter-4.1
	rm -f fonts/Inter-4.1.zip

clean-slides:
	rm -rf slides/build slides/figures/imu
