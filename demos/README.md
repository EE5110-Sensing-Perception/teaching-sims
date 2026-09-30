# Demo launch scripts

Each script activates `.venv` and starts a demo. From the repo root:

### Radar

```bash
./demos/phased-array.sh
./demos/beamforming.sh --scenario mvdr_adaptive_null
./demos/pulsed-ranging.sh --scenario lfm_compression
./demos/target-returns.sh --scenario plate_vs_sphere
./demos/pulse-doppler.sh --scenario mti_reveals_target
./demos/cfar.sh --scenario fixed_vs_cfar_clutter
./demos/fmcw.sh --scenario triangle_decouple
./demos/sar.sh --scenario two_azimuth
```

### IMU

In course order (see `tutorials/IMU-module-map.md`):

```bash
./demos/attitude.sh --scenario ned_vs_ros          # also: order_matters, coning
./demos/mems-accel.sh --scenario impulse_ring      # also: soft_vs_stiff
./demos/mems-gyro.sh --scenario quadrature_bias    # also: mode_matched
./demos/accelerometer.sh --scenario six_position_cal
./demos/gyroscope.sh --scenario allan_industrial   # also: bias_instability
./demos/magnetometer.sh --scenario iron_calibrated
./demos/complementary.sh --scenario kalman_bias    # also: mahony_no_mag
./demos/ins.sh --scenario error_budget             # also: zupt, position_fixes
```

Or use the CLI:

```bash
teaching-sims list
teaching-sims demo <topic> [--scenario ID] [--list-scenarios]
```
