# Lecture slides. Run from the repo root.
#   make slides         EE5110 course decks, IMU parts 1-3 (EE5110_Sensing_and_Perception/build/)
#   make slides-legacy  the earlier demo-only deck (slides/build/imu.pdf)
PY      ?= .venv/bin/python
LATEXMK ?= latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=slides/build
INTER_URL = https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip

.PHONY: slides slides-legacy figures fonts clean-slides guides clean-guides ee5110-imu ee5110-imu-figures

slides: ee5110-imu

slides-legacy: figures fonts/Inter-4.1
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

# EE5110 course decks (IMU parts 1-3). Figures are written as PDF next to the
# course's own figures; the decks build from inside the course folder.
EE5110      = EE5110_Sensing_and_Perception
EE5110_FIGS = $(EE5110)/figures/06_IMU/sim
ee5110-imu-figures:
	$(PY) -m teaching_sims.guides.figures --format pdf --out $(EE5110_FIGS)

ee5110-imu: ee5110-imu-figures
	cd $(EE5110) && for n in 1 2 3; do \
	  latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=build 06_IMU_pt$$n.tex || exit 1; \
	done
