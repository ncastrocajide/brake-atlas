# brake-atlas

![CI](https://github.com/ncastrocajide/brake-atlas/actions/workflows/ci.yml/badge.svg)

Field-wide F1 braking analysis: every driver, every braking zone, every
track of the 2026 season, compared on a common distance axis.

Where [apex-trace](https://github.com/ncastrocajide/apex-trace) compares two
laps in depth, brake-atlas goes wide: it extracts every braking zone of every
driver on the grid (22 drivers, 11 teams), lines them up corner by corner and
turns them into heatmaps, driver profiles and testable conclusions about who
brakes late, who brakes hard, who is consistent, and what the 2026 energy
rules changed about braking.

**Status: M0 (skeleton, braking-zone extractor, synthetic tests, CI).**
Full work plan: [docs/PLAN.md](docs/PLAN.md).

## Questions this project answers

1. **Who brakes latest?** Brake point relative to the field median, per
   corner, per track, across the season.
2. **Who brakes hardest?** Mean and peak deceleration for the same speed
   drop; braking distance at equal entry and minimum speed.
3. **Late braking vs. carrying speed.** Does braking later cost minimum
   speed? V-style (stop and rotate) vs. U-style (carry and roll) drivers.
4. **Consistency.** Lap-to-lap spread of the brake point in clean race
   stints.
5. **Qualifying vs. race margin.** How much earlier each driver brakes on
   Sunday, and how that drifts with tyre age and fuel.
6. **2026 energy management.** Lift-and-coast before braking zones as a
   signature of harvesting, by team and power-unit manufacturer.
7. **Driver vs. car.** Teammate head-to-heads, the only comparison where the
   car is held constant.

## Planned outputs

- Per-track heatmap: drivers × braking zones, coloured by brake-point delta
  to the field median (metres and milliseconds).
- Per-track map: track outline coloured by how much the field disagrees
  about where to brake.
- Season heatmap: drivers × tracks, late-braking index.
- Driver cards: late-braking, deceleration, consistency and race-margin
  indices with bootstrap confidence intervals.
- A findings write-up with every claim reproducible from one script.

## What a braking zone is here

`brakeatlas.zones.detect_brake_zones` turns a canonical apex-trace `Lap` into
`BrakeZone` records: brake point, release point, speed minimum, entry and
minimum speed, braking distance, mean (energy-equivalent) and peak
deceleration in g, how long the brake stays on relative to the speed minimum
(a trail-braking proxy), and the lift-and-coast distance before the brake
point. Deceleration comes from the speed trace (a = v dv/ds), because F1
timing data only gives an on/off brake signal.

## Stack

Python 3.12 · pandas · NumPy · SciPy · matplotlib · FastF1 ·
[apex-trace](https://github.com/ncastrocajide/apex-trace) (canonical `Lap`,
FastF1 loader, corner marks, pinned to a commit) · managed with
[uv](https://github.com/astral-sh/uv)

## Quick start

```bash
uv sync
uv run pytest      # synthetic test suite, no network
```

## Roadmap

- [x] **M0**: skeleton, CI, braking-zone extractor with closed-form tests
- [ ] **M1**: real data chain on one session, zone-to-corner matching,
      sampling-uncertainty validation, first heatmap
- [ ] **M2**: field dataset builder (season, qualifying + clean race laps,
      parquet)
- [ ] **M3**: the atlas: per-track and season heatmaps, track maps
- [ ] **M4**: driver profiles, indices with confidence intervals, teammate
      head-to-heads
- [ ] **M5**: patterns and strategy: stint drift, quali vs. race, 2026
      lift-and-coast, corner archetypes
- [ ] **M6**: findings write-up and interactive atlas

## Honest limits

FastF1 car data arrives every ~0.2-0.27 s (up to ~20 m at 300 km/h) and the
brake channel is on/off: brake points are located to within one raw sample,
and there is no brake pressure or steering, so trail braking can only be
approximated. Brake point differences between teams mix driver and car;
only teammate comparisons isolate the driver. In 2026, coasting before a
braking zone is often an energy-management instruction, not a driver choice.
