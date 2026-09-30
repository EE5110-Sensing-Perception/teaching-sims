# Tutorial 16 — MEMS Coriolis vibratory gyroscope

**Demo:** `teaching-sims demo mems-gyro`  
**Prerequisites:** [14 — MEMS comb-drive](14-mems-accel.md) (spring–mass–damper, resonance)  
**Slides:** section “Inertial sensors” of the IMU deck

By the end you should be able to:

- explain how a vibrating mass senses rotation through the Coriolis force
- explain why the rate signal is recovered by synchronous demodulation
- explain how quadrature error and a demodulator phase error produce gyro bias
- describe the mode-matched vs mode-split trade between sensitivity and bandwidth

---

## 1. Principles

### 1.1 Drive and sense

A proof mass is driven at its **drive resonance** \(\omega_d\) along \(x\). An AGC loop holds the amplitude \(A\) constant:
\(x = A\sin\omega_d t\), \(\dot x = A\omega_d\cos\omega_d t\).

Rotation \(\Omega\) about \(z\) produces a Coriolis acceleration \(-2\,\boldsymbol\Omega\times\mathbf v\) along \(y\), which excites the **sense mode**:

\[
\ddot y + \frac{\omega_y}{Q}\dot y + \omega_y^2 y = -2\Omega\,\dot x \;-\; \frac{k_{xy}}{m}\,x .
\]

The Coriolis term is in phase with drive **velocity**. The second term is **quadrature** from fabrication imbalance, and it is in phase with drive **displacement**, 90° away.

### 1.2 Demodulation

Multiply the sense signal by the drive-velocity reference, delayed by the sense-mode phase \(\angle H(\omega_d)\), then low-pass filter. This gives

\[
\hat\Omega = \Omega\cos\varphi - \Omega_q\sin\varphi,
\]

where \(\varphi\) is the demodulator phase error and \(\Omega_q = k_{xy}/(2m\omega_d)\) is the quadrature expressed as an equivalent rate.

- With \(\varphi=0\), quadrature is rejected completely.
- With \(\varphi\neq0\), it leaks into the output as a **bias**.
- Quadrature can be hundreds of deg/s, so a phase error of a fraction of a degree matters.
- The phase drifts with temperature, so the bias does too.

### 1.3 Mode matching

- Sensitivity \(\propto |H(\omega_d)|\).
- **Matched** (\(\omega_y=\omega_d\)): \(|H|=Q/\omega_d^2\), so there is about Q times more motion per deg/s and lower rate noise. But the rate bandwidth is only \(\approx f_d/2Q\), and the sense lags 90°.
- **Split** by \(\Delta f\): \(|H|\approx1/(2\omega_d\Delta\omega)\). Sensitivity is lower, and the rate response is flat up to roughly \(\Delta f\).

---

## 2. UI map

| Element | Role |
| --- | --- |
| Structure view | Drive frame (x) on anchors; proof mass on sense springs (y); v (blue) and Coriolis force (pink). Slow-motion stroboscopic animation with exaggerated motion |
| Mass path x vs y | Two drive cycles at the view time. An **ellipse** means sense motion 90° from drive (Coriolis, split mode); a **tilted line** means in phase (quadrature, or matched-mode Coriolis) |
| Drive x vs sense y | The same two cycles as time traces (normalised) |
| Rate plot | True rate, demodulated rate output (I), quadrature channel (Q) |
| Sense envelope | The carrier amplitude over the whole run |
| Rate response | Output/input vs rate frequency, including the output LPF |
| Status | Sensitivity (pm per deg/s), rate bandwidth, sense phase, measured vs theoretical bias, output noise |

---

## 3. Guided walkthrough

### Experiment A — No rotation (~3 min)

1. Load **Drive only, no rotation**. The mass moves on a straight line and y = 0.

### Experiment B — Coriolis (~5 min)

1. Load **Rotation creates Coriolis force**.
2. After the step at 50 ms, the mass path opens into an ellipse, because the force follows velocity.
3. The rate output rises to 100 deg/s. The rise time is set by the LPF and the sense mode.

### Experiment C — Quadrature (~5 min)

1. Load **Quadrature error (rejected)**. The path becomes a tilted line, the Q channel reads 200, and the rate output stays at 0.
2. Load **Phase error -> bias**. With 3° of phase error the bias is \(-200\sin3^\circ\approx-10.5\) deg/s. The status shows measured vs theory.
3. Sweep **Demod phase err** from −5° to 5° and read the bias.

### Experiment D — Mode matching (~8 min)

1. Load **Mode matched: sensitive but slow**. Note the pm per deg/s (about 25× the split case), the low output noise, and the slower step response.
2. Load **Mode split: fast but less sensitive**. It responds quickly, but the noise is higher for the same pick-off noise.
3. Load **Rate bandwidth** (40 Hz sine). Split mode tracks it. Set **Mode split** to 0 and the output is attenuated. Check the marker on the response plot.

---

## 4. Lab sheet

| Trial | Split (Hz) | Q | Quadrature | Phase err | Sensitivity (pm/dps) | Bias (dps) | BW (Hz) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 300 | 200 | 0 | 0 | | | |
| 2 | 300 | 200 | 200 | 3 | | | |
| 3 | 0 | 200 | 0 | 0 | | | |
| 4 | 0 | 1000 | 0 | 0 | | | |

---

## 5. Check your understanding

1. Why must the drive amplitude be held constant by an AGC loop?
2. Coriolis and quadrature both appear at \(\omega_d\). What separates them?
3. A gyro's bias changes by 0.5 deg/s over temperature. Suggest a mechanism.
4. Why do high-end MEMS gyros pursue mode matching despite the bandwidth penalty (hint: closed-loop force rebalance)?

---

## 6. Next

Continue with [08 — Accelerometers](08-accelerometer.md) and [09 — Gyroscopes](09-gyroscope.md) for system-level error models.
