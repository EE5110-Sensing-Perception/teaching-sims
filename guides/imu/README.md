# IMU study guides (Canvas pages)

One foundational study guide per IMU demo. Each guide has definitions, background,
explanations with figures, worked examples with checked numbers, common mistakes, a
demo map, practice problems with answers, and further reading. The guides fill in the
background that the tutorials (`tutorials/`) and the lecture deck assume.

| # | Guide | Demo |
| --- | --- | --- |
| 1 | Frames, rotations and attitude kinematics | `attitude` |
| 2 | How a MEMS accelerometer works | `mems-accel` |
| 3 | How a MEMS gyroscope works | `mems-gyro` |
| 4 | Accelerometers: specific force, tilt, errors, calibration | `accelerometer` |
| 5 | Gyroscopes: integration, noise models, Allan variance | `gyroscope` |
| 6 | Magnetometers: heading, tilt compensation, calibration | `magnetometer` |
| 7 | Attitude fusion: complementary, Kalman, Mahony | `complementary` |
| 8 | Strapdown INS: mechanisation, error growth, aiding | `ins` |

## Build

```bash
make guides                 # figures -> guides/imu/img, pages -> canvas/ and preview/
```

- `src/` — the sources (edit these). Body-only HTML with a `<!-- title: ... -->` first
  line and a few classes (`def`, `key`, `warn`, `demo`, `example`, `answer`, `overview`,
  `narrow`). Unknown classes fail the build.
- `canvas/` — Canvas-ready fragments. Canvas strips `<style>` and `<script>`, so every
  class is converted to an inline style.
- `preview/` — standalone pages with MathJax for checking locally
  (`python -m http.server -d guides/imu`, then open `/preview/`).
- `img/` — PNG figures, from `teaching_sims.guides.figures` (new foundational figures)
  plus the slide figures re-exported as PNG.

## Putting a guide into Canvas

1. **Upload the figures.** In the course, go to *Files*, create a folder `imu-guides`, and
   upload everything in `guides/imu/img/`.
2. **Rebuild with the Canvas image path**, using your course ID from the course URL:
   ```bash
   make guides IMAGE_BASE=/courses/12345/file_contents/course%20files/imu-guides/
   ```
3. **Create a page** (*Pages → + Page*), give it the guide's title, switch the editor to
   the HTML view (`</>`), paste the contents of `canvas/NN-*.html`, and save.

Check the first page after saving. If the images do not show, open one uploaded image
in *Files*, copy its URL, and adjust `IMAGE_BASE` to match that path.

**Math.** Equations are LaTeX in `\( ... \)` (inline) and `$$ ... $$` (display). Canvas
renders these with MathJax when the page is viewed. If your institution has disabled
that, equations appear as raw LaTeX.
