# Tutorials

Hands-on guides for the Teaching Sims demos. Each tutorial explains the
underlying principles, maps them to the UI, and walks through experiments you
can run in lecture or self-paced lab.

## Radar track

| Tutorial | Demo command | Time (approx.) |
| --- | --- | --- |
| [01 — Phased-array antennas](01-phased-array.md) | `teaching-sims demo phased-array` | 45–60 min |
| [02 — Digital beamforming](02-beamforming.md) | `teaching-sims demo beamforming` | 45–60 min |
| [03 — Pulsed radar ranging](03-pulsed-ranging.md) | `teaching-sims demo pulsed-ranging` | 40–55 min |
| [15 — Target returns (RCS)](15-target-returns.md) | `teaching-sims demo target-returns` | 35–50 min |
| [04 — Pulse-Doppler / MTI](04-pulse-doppler.md) | `teaching-sims demo pulse-doppler` | 40–55 min |
| [05 — CFAR detection](05-cfar.md) | `teaching-sims demo cfar` | 35–50 min |
| [06 — FMCW radar](06-fmcw.md) | `teaching-sims demo fmcw` | 40–55 min |
| [07 — Stripmap SAR](07-sar.md) | `teaching-sims demo sar` | 40–55 min |

## IMU track (MSc robotics)

Built around 22 learning outcomes. See the
[IMU learning outcomes and coverage map](IMU-learning-outcomes.md). The
matching lecture deck is built with `make slides` (see the top-level README).

| Tutorial | Demo command | Outcomes | Time (approx.) |
| --- | --- | --- | --- |
| [10 — Frames, rotations and kinematics](10-attitude.md) | `teaching-sims demo attitude` | LP1–5 | 50–65 min |
| [14 — MEMS comb-drive accelerometer](14-mems-accel.md) | `teaching-sims demo mems-accel` | LP6 | 35–50 min |
| [16 — MEMS Coriolis gyroscope](16-mems-gyro.md) | `teaching-sims demo mems-gyro` | LP8 | 35–50 min |
| [08 — Accelerometers: errors, calibration, lever arm](08-accelerometer.md) | `teaching-sims demo accelerometer` | LP7, 10, 13, 22 | 45–60 min |
| [09 — Gyroscopes: error models and Allan variance](09-gyroscope.md) | `teaching-sims demo gyroscope` | LP10–12, 21 | 45–60 min |
| [12 — Magnetometer heading and calibration](12-magnetometer.md) | `teaching-sims demo magnetometer` | LP9, 13 | 35–50 min |
| [11 — Attitude fusion: CF, Kalman, Mahony](11-complementary.md) | `teaching-sims demo complementary` | LP14–17 | 55–70 min |
| [13 — Strapdown INS and aiding](13-ins.md) | `teaching-sims demo ins` | LP18–21 | 45–60 min |

## Before you start

```bash
cd ~/teaching-sims
source .venv/bin/activate
# if needed:
pip install -e ".[dev]"
```

Tips that apply to every demo:

- Turn on **Presenter mode** when projecting — it hides advanced sliders and
  keeps the teaching banner readable.
- Use the built-in **Lecture scenarios** buttons as checkpoints; they load a
  curated parameter set and teaching point.

Suggested order: finish the radar track **or** the IMU track as a self-contained
course; mixing is fine once students have the matching prerequisites.
