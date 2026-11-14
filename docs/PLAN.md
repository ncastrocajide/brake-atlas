# Work plan

Status: M0 to M6 are done for the 18 rounds with usable data. Results are
in [FINDINGS.md](FINDINGS.md). What is left is listed at the end of the
README roadmap.

## Data

Source is OpenF1 (car data and position, the same feed as official
timing, about 4 Hz) plus the official corner marks from MultiViewer. FastF1
was the first choice, but since October 2026 the F1 archive needs an F1 TV
login. Main season is 2026, with 2025 as a baseline for the regulation
change in M5.

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
| `bp_before_mark` | corner mark − brake point, on the lap's own distance axis [m] |
| `bp_delta_m` | field median of `bp_before_mark` minus the driver's [m], positive = later |
| `bp_resid_m` | the same after fitting `bp_before_mark` against entry speed² at that corner [m] |
| `bp_uncertainty_m` | half the spacing of the raw samples around the brake point [m] |
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

Each lap has its own integrated odometer, so raw distances disagree by
metres. Brake points are therefore measured as metres before the corner
mark, with the mark projected onto the same lap's line: the drift cancels.

A zone belongs to the first corner mark after its brake point. Matching on
the speed minimum was tried first and failed in chicanes, where the minimum
falls on either apex depending on the driver.

A car that reaches a corner slower can brake later without the driver doing
anything special, because stopping distance grows with v². At Monza the
uncorrected numbers had the two slowest cars as the latest brakers. All
driver comparisons use the residual after fitting brake point against entry
speed² at each corner (`bp_resid_m`).

One brake point is only known to about ±10 m at 4 Hz, about the same size
as the differences between drivers at a single corner. Single cells of a
heatmap are noise-level; the sampling error is random, so medians over a
season of corners are not.

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
