# Study guides. Run from the repo root.
PY ?= .venv/bin/python

.PHONY: guides clean-guides

# Study guides (Canvas-ready HTML). IMAGE_BASE rewrites image URLs for Canvas, e.g.
#   make guides IMAGE_BASE=/courses/12345/file_contents/course%20files/imu-guides/
IMAGE_BASE ?=
guides:
	$(PY) -m teaching_sims.guides.figures --out guides/imu/img
	$(PY) -m teaching_sims.guides.build --image-base "$(IMAGE_BASE)"

clean-guides:
	rm -rf guides/imu/img guides/imu/canvas guides/imu/preview
