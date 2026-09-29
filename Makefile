# Lecture slides. Run from the repo root (the SimplePlus theme and the Inter
# font path are resolved relative to the working directory).
PY      ?= .venv/bin/python
LATEXMK ?= latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=slides/build
INTER_URL = https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip

.PHONY: slides figures fonts clean-slides

slides: figures fonts/Inter-4.1
	$(LATEXMK) slides/imu/imu.tex

figures:
	$(PY) -m teaching_sims.slides.imu_figures --out slides/figures/imu

fonts: fonts/Inter-4.1

fonts/Inter-4.1:
	mkdir -p fonts
	curl -sSL -o fonts/Inter-4.1.zip $(INTER_URL)
	unzip -q -o fonts/Inter-4.1.zip -d fonts/Inter-4.1
	rm -f fonts/Inter-4.1.zip

clean-slides:
	rm -rf slides/build slides/figures/imu
