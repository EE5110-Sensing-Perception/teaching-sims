# Teaching Sims

Interactive Dear PyGui simulations for graduate teaching. Two tracks:

- **Radar** — arrays through stripmap SAR  
- **IMU / navigation** — accelerometers through unaided strapdown INS  

Physics cores are UI-agnostic; each topic ships with lecture scenarios and a tutorial.

## Quick start

```bash
cd ~/teaching-sims
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

teaching-sims list
teaching-sims demo accelerometer
teaching-sims demo phased-array
pytest
```

## Course map — Radar

| # | Demo | Tutorial | Launch |
| --- | --- | --- | --- |
| 1 | Phased-array ULA | [01](tutorials/01-phased-array.md) | `teaching-sims demo phased-array` |
| 2 | Digital beamforming | [02](tutorials/02-beamforming.md) | `teaching-sims demo beamforming` |
| 3 | Pulsed ranging | [03](tutorials/03-pulsed-ranging.md) | `teaching-sims demo pulsed-ranging` |
| 4 | Target returns (RCS) | [15](tutorials/15-target-returns.md) | `teaching-sims demo target-returns` |
| 5 | Pulse-Doppler / MTI | [04](tutorials/04-pulse-doppler.md) | `teaching-sims demo pulse-doppler` |
| 6 | CFAR detection | [05](tutorials/05-cfar.md) | `teaching-sims demo cfar` |
| 7 | FMCW radar | [06](tutorials/06-fmcw.md) | `teaching-sims demo fmcw` |
| 8 | Stripmap SAR | [07](tutorials/07-sar.md) | `teaching-sims demo sar` |

## Course map — IMU (MSc robotics)

Organised by topic. See
[tutorials/IMU-module-map.md](tutorials/IMU-module-map.md) for the
topic → demo → scenario map.

| # | Demo | Tutorial | Launch |
| --- | --- | --- | --- |
| 9 | Frames, rotations, kinematics (NED vs ROS) | [10](tutorials/10-attitude.md) | `teaching-sims demo attitude` |
| 10 | MEMS comb-drive accelerometer | [14](tutorials/14-mems-accel.md) | `teaching-sims demo mems-accel` |
| 11 | MEMS Coriolis gyroscope | [16](tutorials/16-mems-gyro.md) | `teaching-sims demo mems-gyro` |
| 12 | Accelerometer: errors, calibration, lever arm | [08](tutorials/08-accelerometer.md) | `teaching-sims demo accelerometer` |
| 13 | Gyroscope: error models, Allan variance | [09](tutorials/09-gyroscope.md) | `teaching-sims demo gyroscope` |
| 14 | Magnetometer: heading, iron calibration | [12](tutorials/12-magnetometer.md) | `teaching-sims demo magnetometer` |
| 15 | Attitude fusion: CF, Kalman, Mahony | [11](tutorials/11-complementary.md) | `teaching-sims demo complementary` |
| 16 | Strapdown INS and aiding | [13](tutorials/13-ins.md) | `teaching-sims demo ins` |

## Study guides (Canvas)

Each IMU demo has a foundational study guide (definitions, explanations, figures,
worked examples, practice problems with answers) as Canvas-ready HTML. Build with
`make guides`; see [guides/imu/README.md](guides/imu/README.md) for importing into Canvas.

## Lecture slides

The IMU lectures are three Beamer decks (SimplePlus theme) in
`EE5110_Sensing_and_Perception/`, in the same format as the other course decks:

| Deck | Content |
| --- | --- |
| `06_IMU_pt1.tex` | How inertial sensors work: MEMS accelerometer, specific force, Coriolis gyroscope, magnetometer |
| `06_IMU_pt2.tex` | Errors, noise and calibration: thermal noise, error model, Allan variance, grades, calibration |
| `06_IMU_pt3.tex` | Attitude, fusion and inertial navigation: frames, rotations, filters, strapdown INS, aiding |

Each deck has **Background** frames for prerequisites and **Demo** frames that give
the command, what to do, what to observe and a question. Shared notation is in
`06_IMU_macros.tex`. `06_IMU.tex` is the original single deck, kept as an archive.

```bash
make slides               # figures + XeLaTeX -> EE5110_Sensing_and_Perception/build/06_IMU_pt{1,2,3}.pdf
make ee5110-imu-figures   # figures only -> EE5110_Sensing_and_Perception/figures/06_IMU/sim/*.pdf
make slides-legacy        # the earlier demo-only deck -> slides/build/imu.pdf
```

To build one deck by hand, run `latexmk -xelatex 06_IMU_pt1.tex` from inside
`EE5110_Sensing_and_Perception/` (the theme, font and figure paths are relative to it).

Prerequisites:

- XeLaTeX with `beamer`, `siunitx`, `pgf`, `booktabs` and `caption`. With TinyTeX:
  `tlmgr install beamer siunitx pgf caption`.
- The Inter font under `EE5110_Sensing_and_Perception/fonts/Inter-4.1/`.

List scenarios for any demo:

```bash
teaching-sims demo complementary --list-scenarios
```

Shell shortcuts live in [`demos/`](demos/README.md).

## Tips

- Enable **Presenter mode** when projecting.
- Use **Lecture scenarios** as the talk track; sliders are for exploration.
- Radar angles are from **broadside** (\(0^\circ\) = array / look normal).
- IMU conventions: NED navigation / FRD body frame, aerospace **ZYX** yaw–pitch–roll,
  specific force \(\mathbf f=\mathbf a-\mathbf g\) (level reads \(f_z\approx-g\)). The attitude demo
  shows the ROS REP-103 ENU/FLU equivalent.
- IMU demos share role colours (truth, gyro, accel, mag, fused, Kalman, error), which the slide
  figures use too.
- Optional **3D attitude windows** (accelerometer / gyroscope) need `matplotlib` + `PySide6`
  (already in package dependencies). Checkbox in the left panel opens an external Qt window.

## Layout

```text
src/teaching_sims/
  core/           shared constants, IMU error model, Allan deviation
  topics/*/       physics + scenarios per demo
  ui/desktop/     Dear PyGui apps (+ imu_style, playback helpers)
  ui/external/    optional matplotlib 3D viewers
  ui/palette.py   role colours shared by apps and slides
  slides/         slide-figure generators
  ui/cli.py       teaching-sims entry point
EE5110_Sensing_and_Perception/  course decks, incl. IMU parts 1-3 (06_IMU_pt*.tex)
slides/imu/       earlier demo-only IMU deck (make slides-legacy)
tutorials/        principles + walkthroughs
tests/            physics unit tests
demos/            one-liner launch scripts
```

## Develop

```bash
pip install -e ".[dev]"
pytest
```
