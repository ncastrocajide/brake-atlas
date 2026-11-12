# brake-atlas

![CI](https://github.com/ncastrocajide/brake-atlas/actions/workflows/ci.yml/badge.svg)

Braking analysis across the whole 2026 F1 grid. For each session I extract
every braking zone of every driver, match the zones to the official corner
numbers and compare drivers corner by corner: where they brake, how hard,
how much speed they keep to the apex and how much that changes from
qualifying to the race.

It builds on [apex-trace](https://github.com/ncastrocajide/apex-trace), which
does the lap loading, the distance grid and the corner marks. apex-trace
compares two laps; this repo runs the same kind of comparison over 22 drivers
and a full season.

**Status: M0.** The braking-zone extractor and its tests are done; no real
data has gone through it yet. The work plan is in [docs/PLAN.md](docs/PLAN.md).

## What gets measured

`detect_brake_zones` takes an apex-trace `Lap` and returns one `BrakeZone`
per braking event, with brake point, release point and speed minimum (all in
metres from the line), entry and minimum speed, braking distance, mean and
peak deceleration in g, and the distance spent coasting before the brake
point. F1 timing only says whether the brake is on, so deceleration is
computed from the speed trace (a = v dv/ds).

The comparisons I want to get to:

- brake point relative to the field median at each corner, per track and
  over the season
- deceleration at equal entry speed and speed drop
- whether braking later costs minimum speed, driver by driver
- lap-to-lap spread of the brake point in clean race stints
- qualifying vs. race brake points, and how they drift with tyre age
- coasting before braking zones by team and power unit, which in 2026 is
  mostly about energy harvesting
- teammate comparisons, since that is the only way to take the car out

## Data access

Since October 2026 the F1 timing archive only serves past sessions to a
signed-in F1 TV account (Access or higher). FastF1 3.9 handles the login; you
need your own subscription to rebuild the dataset. The test suite does not
need any of this.

## Running it

```bash
uv sync
uv run pytest
```

## Roadmap

- [x] **M0**: repo, CI, braking-zone extractor with synthetic tests
- [ ] **M1**: one qualifying session end to end, zone-to-corner matching,
      brake-point uncertainty, first heatmap
- [ ] **M2**: dataset builder for the season (qualifying and clean race laps)
- [ ] **M3**: heatmaps and track maps for every round
- [ ] **M4**: driver profiles and teammate comparisons, with confidence
      intervals
- [ ] **M5**: tyre and fuel effects, qualifying vs. race, 2026 coasting,
      corner types
- [ ] **M6**: write-up of the findings and an interactive version

## Limitations

FastF1 car data comes in every 0.2-0.27 s, which at 300 km/h is up to 20 m
between samples, so single brake points are rough; the analysis leans on
medians over many laps. There is no brake pressure or steering channel, so
trail braking can only be approximated. Differences between teams mix driver
and car. And in 2026 coasting before a corner is often a team instruction for
energy management, so I treat it as a team pattern, not a driver trait.
