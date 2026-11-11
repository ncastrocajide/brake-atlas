# Work plan

The project in one sentence: extract every braking zone of every driver on
the 2026 grid, line them up corner by corner, and turn them into heatmaps,
driver profiles and conclusions that survive an honest look at the data's
limits.

## 1. Data

| Item | Choice |
|---|---|
| Source | FastF1 (official timing: car data + position data + circuit info) |
| Season | 2026 (22 drivers, 11 teams); 2025 as a pre-regulation baseline in M5 |
| Sessions | Qualifying (each driver's fastest valid lap) and race (clean laps) |
| Unit of analysis | one braking zone of one lap: (season, round, session, driver, lap, zone) |
| Storage | one tidy parquet table per session under `data/` (git-ignored, rebuildable) |

**Lap filters for races** (a clean lap is comparable; anything else is
noise): no pit in/out, green track status for the whole lap (no SC, VSC,
yellow), not lap 1, not the lap after a pit stop, and optionally free air
(gap to the car ahead above ~1.5 s, from lap timing) so a tow or dirty air
does not move the brake point.

**Weather**: wet or mixed sessions are tagged and kept out of season
aggregates by default.

## 2. Metrics

Per braking zone (`brakeatlas.zones.BrakeZone`, already implemented):

| Metric | Definition |
|---|---|
| `brake_point` | first grid point with Brake above threshold [m] |
| `entry_speed`, `min_speed` | at the brake point and at the speed minimum [km/h] |
| `braking_distance` | brake point to speed minimum [m] |
| `mean_decel_g` | (v_e² − v_min²) / (2 d) / g: energy-equivalent mean |
| `peak_decel_g` | max of −v dv/ds over the zone / g |
| `release_offset` | release point − speed-minimum point [m]: trail-braking proxy |
| `coast_before` | off throttle and off brake right before braking [m] |

Derived per zone and lap, relative to the field (M1-M2):

| Metric | Definition |
|---|---|
| `bp_delta_m` | brake point − field median for that zone, same session [m] (positive = later) |
| `bp_delta_ms` | `bp_delta_m` / entry speed: the same thing in time [ms] |
| `bp_z` | robust z-score: (bp − median) / (1.4826 · MAD), so corners of different nature can be pooled |
| `vmin_delta` | min speed − field median [km/h] |

Per driver (M4), each with a bootstrap 95 % CI over laps and zones:

- **Late-braking index**: median `bp_z` over all heavy-braking zones.
- **Deceleration index**: median of mean decel residual after regressing on
  entry speed and speed drop (so a track mix does not decide the ranking).
- **Consistency index**: median over zones of the lap-to-lap std of the
  brake point in clean race stints [m].
- **Race margin**: qualifying brake point − race median brake point, per
  zone [m].
- **Carry index**: slope of `vmin_delta` against `bp_delta_m` across zones:
  does braking later cost this driver minimum speed?

## 3. Methodology rules

1. **Compare like with like.** A zone is only compared across drivers in
   the same session. Season aggregates pool z-scores, never raw metres.
2. **Align the distance axis.** Each lap integrates its own odometer and
   drivers take different lines, so raw distances disagree by metres.
   Zones are aligned with the official corner marks (the apex-trace
   landmark alignment) before any delta is computed.
3. **Match zones to corners by name.** Each zone takes the official corner
   designation whose mark is nearest to its speed minimum. Zones that match
   no corner, or two zones claiming the same corner, are flagged and
   inspected, not silently dropped.
4. **Driver vs. car.** Cross-team differences are reported as "driver +
   car". Claims about the driver alone come from teammate comparisons.
5. **Robust statistics.** Medians and MAD instead of means and std;
   bootstrap CIs; a minimum sample size per cell before it is coloured in a
   heatmap (cells below it are greyed out, not hidden).
6. **No hidden smoothing.** Any filter on speed or deceleration is a named,
   documented parameter.
7. **Reproducibility.** Every figure in the README and the findings comes
   from a script in `examples/` (or a CLI command), with the session it uses
   hard-coded.

## 4. Milestones

Each milestone ends with a commit series, a README update and, from M1 on,
at least one figure.

### M0: skeleton and extractor (done)

- Repo, uv, ruff, pytest, GitHub Actions CI.
- `apextrace` pinned as a dependency: canonical `Lap`, FastF1 loader,
  corner marks are reused, not copied.
- `detect_brake_zones` and `zones_to_frame` with closed-form synthetic tests
  (constant-g stops, signal flicker, dabs, two corners).

### M1: one session, end to end

- Load every driver's fastest qualifying lap for one heavy-braking track
  (Monza, Montreal or Baku 2026).
- Zone-to-corner matching via official marks; landmark-aligned distances.
- **Validation**: estimate brake-point uncertainty from sampling (raw sample
  spacing at each brake point; onset from the brake channel vs. onset from
  the deceleration trace); check deceleration magnitudes are physically
  plausible (roughly 3-6 g in heavy zones).
- First heatmap: drivers × zones, `bp_delta_m`.
- Done when: the heatmap reproduces from one script and the uncertainty is
  printed next to it.

### M2: field dataset builder

- `brakeatlas build --season 2026 [--round N] [--session Q|R]`: loads,
  filters, extracts, tags (driver, team, PU manufacturer, compound, tyre
  age, lap, track status) and writes parquet.
- Race lap filters from section 1, with counts of laps kept and dropped
  per reason printed in the build log.
- Synthetic tests for the filters and the field-relative metrics.
- Done when: the full 2026 season builds from cache into one dataset and a
  re-run is a no-op.

### M3: the atlas

- Per track: drivers × zones heatmap (rows grouped by team), track map
  coloured by field spread of the brake point, braking-zone summary table.
- Season: drivers × tracks heatmap of the late-braking index.
- One palette and layout for every figure; light and dark friendly.
- Done when: every round of the season has its atlas page.

### M4: driver profiles

- The five indices of section 2 with bootstrap CIs.
- Teammate head-to-heads per zone and per season.
- Driver cards (one figure per driver).
- Done when: every ranking in the README shows its CI and sample size.

### M5: patterns and strategy

- **Stint drift**: brake point and deceleration vs. tyre age and lap
  (fuel), per compound.
- **Quali vs. race margin** by driver and by corner type.
- **2026 energy signature**: `coast_before` by team and PU manufacturer;
  where on the lap coasting happens (before which corner types); 2025 vs.
  2026 for the same circuits.
- **Corner archetypes**: cluster zones on entry speed, speed drop and
  deceleration; which drivers gain on which archetype.
- **Does it pay?** Link braking metrics to corner time (apex-trace
  per-corner delta): is late braking where lap time is actually made?
- Done when: each pattern is a figure plus a one-paragraph claim with its
  evidence and its caveat.

### M6: publication

- `docs/FINDINGS.md`: the conclusions, each with figure, numbers, CI and
  limit.
- Interactive atlas (static site on GitHub Pages: pick a track, a driver,
  a corner).
- README headline figure and a short write-up for LinkedIn.

## 5. Risks

| Risk | Mitigation |
|---|---|
| Brake points only known to ~1 raw sample (up to ~20 m) | quantify in M1; report deltas with that floor; rely on aggregates over many laps |
| On/off brake signal, no pressure or steering | deceleration from speed; trail braking only as a proxy, labelled as such |
| Recent-session data flaky on the F1 API side | build from cache; re-run failed sessions; log missing laps |
| Driver and car confounded | teammate comparisons for driver claims |
| 2026 coasting is often a team instruction | report it as a team/PU signature, not a driver skill |
| Season not finished when the study starts | the builder is incremental by round |
