# Work plan

## Data

Source is FastF1 (car data, position data, circuit info). Main season is
2026, with 2025 as a baseline for the regulation change in M5. Since
October 2026 the timing archive needs an F1 TV login, so the dataset is
built locally from the FastF1 cache.

Two kinds of laps:

- Qualifying: each driver's fastest valid lap.
- Race: clean laps only. That means no pit in or out lap, green flag for
  the whole lap, not lap 1, and ideally more than ~1.5 s to the car ahead
  so a tow or dirty air does not move the brake point. The build log
  prints how many laps each filter removes.

Wet or mixed sessions are tagged and left out of season totals by default.

One row in the dataset is one braking zone of one lap, keyed by season,
round, session, driver, lap and zone. Each session is saved as a parquet
file under `data/` (git-ignored; it can always be rebuilt).

## Metrics

Per zone, from `brakeatlas.zones.BrakeZone` (already implemented):

| Field | Meaning |
|---|---|
| `brake_point` | first point with brake on [m] |
| `entry_speed`, `min_speed` | at the brake point and at the speed minimum [km/h] |
| `braking_distance` | brake point to speed minimum [m] |
| `mean_decel_g` | (v_e² − v_min²) / (2 d) / g |
| `peak_decel_g` | maximum of −v dv/ds over the zone, in g |
| `release_offset` | release point − speed-minimum point [m] |
| `coast_before` | off throttle and off brake just before braking [m] |

Relative to the field, same session:

| Field | Meaning |
|---|---|
| `bp_delta_m` | brake point − field median for that zone [m], positive = later |
| `bp_delta_ms` | the same divided by entry speed [ms] |
| `bp_z` | (bp − median) / (1.4826 · MAD), so different corners can be pooled |
| `vmin_delta` | minimum speed − field median [km/h] |

Per driver, each with a bootstrap 95 % interval:

- late braking: median `bp_z` over heavy braking zones
- deceleration: median residual of mean deceleration after regressing on
  entry speed and speed drop, so the track mix does not decide the order
- consistency: median over zones of the lap-to-lap standard deviation of
  the brake point in clean stints [m]
- race margin: qualifying brake point minus race median, per zone [m]
- carry: slope of `vmin_delta` against `bp_delta_m`

## Method

Zones are only compared within a session. Season numbers pool z-scores,
never raw metres.

Each lap has its own integrated odometer and drivers take different lines,
so distances disagree by a few metres. Before computing any delta, laps are
aligned to the official corner marks (apex-trace's landmark alignment).

A zone gets the name of the corner mark closest to its speed minimum. If a
zone matches no corner, or two zones claim the same one, it is flagged and
checked by hand.

Differences between teams are reported as driver plus car. Anything said
about a driver alone comes from the teammate comparison.

Medians and MAD instead of means and standard deviations. Heatmap cells
with too few laps are greyed out rather than coloured.

Any filter on speed or deceleration is a named parameter. Every figure in
the README comes from a script in `examples/` with the session written in.

## Milestones

**M0, done.** uv, ruff, pytest and CI. apex-trace pinned as a dependency
(lap model, FastF1 loader, corner marks). `detect_brake_zones` and
`zones_to_frame`, tested on synthetic constant-deceleration stops, brake
flicker, dabs and a two-corner lap.

**M1, one session.** Fastest qualifying lap of every driver at a track with
heavy braking (Monza, Montreal or Baku 2026). Zone-to-corner matching on
aligned distances. Estimate the brake-point uncertainty: raw sample spacing
at each brake point, and onset from the brake channel compared with onset
from the deceleration trace. Check that deceleration in heavy zones lands
around 3-6 g. First heatmap, drivers by zones, coloured by `bp_delta_m`.
Finished when the heatmap comes out of one script with the uncertainty
printed next to it.

**M2, dataset builder.** `brakeatlas build --season 2026 [--round N]
[--session Q|R]` loads, filters, extracts and tags (driver, team, power
unit, compound, tyre age, lap, track status), then writes parquet. Tests
for the lap filters and the field-relative metrics. Finished when the 2026
season builds from cache and a second run does nothing.

**M3, figures.** For each track: the drivers-by-zones heatmap, a track map
coloured by how much brake points vary across the field, and a summary
table. For the season: drivers by tracks, late-braking index. All figures
use `brakeatlas.style`.

**M4, drivers.** The per-driver metrics with intervals, teammate
comparisons per zone and per season, and one summary figure per driver.

**M5, patterns.** Brake point and deceleration against tyre age and lap
number, by compound. Qualifying vs. race margin by driver and corner type.
`coast_before` by team and power unit, where on the lap it happens, and
2025 vs. 2026 on the same circuits. Clustering zones by entry speed, speed
drop and deceleration to see which drivers gain where. Then the question
that matters most: whether braking later actually shows up in corner time
(apex-trace per-corner delta).

**M6, write-up.** `docs/FINDINGS.md` with each result, its numbers and its
caveat. An interactive version on GitHub Pages to pick track, driver and
corner.

## Risks

- Brake points are only known to about one raw sample (up to ~20 m).
  Measured in M1; results rely on aggregates.
- No brake pressure or steering. Deceleration comes from speed; trail
  braking is an approximation and labelled as one.
- F1 TV login required, and the FastF1 token expires after a few days.
  Data is built locally and cached.
- Driver and car are mixed in cross-team comparisons. Teammates are used
  for driver claims.
- 2026 coasting is often a team instruction. Reported per team, not per
  driver.
- The season is still running. The builder works round by round.
