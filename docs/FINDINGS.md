# Findings, 2026 season so far

Data: 18 rounds from Melbourne to Interlagos. Bahrain and Jeddah were
cancelled; Madring and Kuala Lumpur have no official corner marks yet.
Qualifying uses each driver's fastest lap (2032 heavy braking zones).
Races use about 15 000 clean laps (green flag, dry tyres, no pit laps,
about 79 000 heavy zones). The 2025 comparison adds 23 qualifying sessions
and about 20 500 clean race laps from that season. A heavy zone is a stop that loses 50 km/h or
more.

Two things to keep in mind throughout. A single brake point is only known
to about ±10 m, because the timing feed is 4 Hz, so every number here is a
median over many corners. And brake points are compared after correcting
for entry speed: a car that arrives slower can brake later without the
driver doing anything special. Before that correction the two slowest cars
on the grid came out as the latest brakers at Monza.

Every figure and number comes from `examples/season_atlas.py` and
`examples/race_atlas.py`.

## Qualifying

### The car sets the brake point

![Season index per driver](season_2026_index.png)

Driver medians vary 8 times more between teams (12.3 m²) than within a
team (1.5 m²). Both Ferraris brake latest, +6.4 and +6.6 m against what
their entry speed predicts, and both Cadillacs earliest, −5.3 and −5.7 m.
Late braking and qualifying pace go together (Spearman 0.87 over 22
drivers), but the ranking sorts teams, with teammates next to each other.

![Late braking against qualifying pace](season_2026_pace.png)

### The gaps between cars open at high speed

![Brake point by entry-speed band](season_2026_bands.png)

McLaren is level with the field in stops that start below 250 km/h (+0.6 m)
and 7.7 m later in stops from above 300 km/h. Cadillac goes the other way,
from −3.7 m to −10.0 m. Ferrari is late everywhere. Deceleration itself
follows speed: the field's median peak is 4.7 g above 300 km/h, 3.9 g from
250-300, 2.9 g from 200-250 and 1.8 g below 200 km/h. Both point at
downforce as what separates the cars under braking. The hardest stop of the
year is turn 17 in Miami at 5.6 g.

![All circuits with the field's braking zones](season_2026_tracks.png)

### Teammates brake within about 2 m of each other

![Teammate differences](season_2026_teammates.png)

Comparing both drivers on the same corner in the same session takes the
car, the track and the conditions out. Ten of eleven pairs are within about
2 m with intervals that include zero. The exception is Audi: Hülkenberg
brakes 5.1 m later than Bortoleto (95 % interval 1.5 to 6.7 m, 63 corners).

### Braking later gains a little time

![Later braking against time through the corner](season_2026_teammate_time.png)

Among 747 teammate pairs, the one who brakes 15 m or more later is quicker
from 250 m before the corner to 150 m after it 60 % of the time, by a
median of 21 ms, after removing the difference in overall lap pace. The
correlation is weak (Spearman −0.08). With ±10 m of sampling error on each
brake point the true relation is probably stronger than what shows here,
but this is what the data supports.

![Who brakes late, track by track](season_2026_heatmap.png)

## Races

### On Sunday the field brakes about 14 m earlier

![Race against qualifying by team](race_2026_margin.png)

Same driver, same corner: the median race brake point is 13.8 m before the
qualifying one (95 % interval over races 11.5 to 17.5 m, 1756 driver-corner
pairs). Entry speed is 10 km/h lower in the race, which on its own would
allow braking later, and peak deceleration is 0.4 g lower. Teams range from
8 m (Cadillac) to 17 m (Ferrari); the intervals overlap, so the order
between teams is not established.

### Lift and coast belongs to the race

![Lift and coast, race against qualifying](race_2026_coast.png)

A stop counts as lift and coast when the car spends 40 m or more off
throttle before the brake point; shorter coasts cannot be told apart from
interpolation between 4 Hz samples. In the median round that is 5 % of
heavy stops in the race and under 1 % in qualifying. It peaks at Melbourne
(30 %), Miami (23 %) and Mexico City (17 %).

In qualifying it was common only at the start of the year: 21 % of heavy
stops at Melbourne and about a fifth at Suzuka, then under 3 % from Miami
on. That fits teams still learning to deploy the new power units over one
lap, though each of those tracks appears only once.

### The power-unit pattern, and why it is weaker than it looks

![Lift and coast by power unit](race_2026_power_unit.png)

Grouped by 2026 power unit, the two Red Bull Ford teams lift and coast
before 15 % of heavy race stops (interval 11 to 21 %) and the four Mercedes
powered teams before 4 % (2 to 8 %). Red Bull Ford is the highest in 12 of
18 races, and the gap is the same in free air.

On its own that reads as a power-unit effect. The 2025 data says to be
careful:

![The same teams a year apart](regs_2025_2026_teams.png)

Racing Bulls was already the team that coasted most in 2025, 17 % of heavy
race stops against 20 % now, with a different power unit. Most of the "Red
Bull Ford" number is that team's habit. What did change is at the other
end: all four Mercedes powered teams coast less than a year ago, the works
team by 9 points per circuit (interval 4 to 11) and Alpine, which switched
to Mercedes power, by 3 (0.1 to 8). For McLaren and Williams the interval
includes zero.

### Old tyres cost corner speed, not brake point

![Brake point through a stint](race_2026_stint.png)

A model with tyre age and race distance, which pit stops allow to separate,
gives per 10 laps of tyre age: minimum speed −0.5 km/h (interval −0.9 to
−0.1) and the brake point 1.4 m later (0.6 to 2.6). Per 10 laps of race
distance, as fuel burns off: minimum speed +0.6 km/h and entry speed
+0.4 km/h, with no clear change in brake point. Drivers do not back the
brake point off as the tyres wear; the loss shows at the apex. Most of the
"later" happens in the first laps of a stint, when drivers brake early on
new tyres.

### Traffic moves the brake point

A lap counts as free air when the car ahead on the road, lapped cars
included, is more than 1.5 s away at both ends of the lap. That is 57 % of
clean laps. Comparing the same driver in the same stint and corner, in
traffic he brakes 4.5 m earlier (95 % interval 3.5 to 5.7 m, 3011
stint-corners) while arriving 0.6 km/h faster from the tow.

The results above hold in free air alone: the race brake point is 11.7 m
before the qualifying one, and lift and coast is 15 % for Red Bull Ford
against 4 % for Mercedes.

### Lap-to-lap scatter

![Lap-to-lap scatter per driver](race_2026_scatter.png)

Between consecutive clean laps of a stint, the brake point at a given
corner moves with a standard deviation of 7.9 m in free air and 9.9 m in
traffic, once sampling noise is removed. In free air drivers range from
6.7 m (Piastri) to 8.7 m (Stroll). Most of the field cannot be separated:
the intervals overlap. The number still mixes the driver with energy
management, which moves a race brake point too. Odometer error is not a
large part: at Monza the result is the same for the first corner of the lap
and the last.

## 2025 against 2026

Same 17 circuits, 115 corners that are heavy braking zones in both seasons,
field medians from qualifying. The official corner marks are in exactly the
same place in both years, so brake points compare directly. Intervals are
over circuits. From `examples/regs_atlas.py`.

![Entry and minimum speed, 2025 against 2026](regs_2025_2026_speeds.png)

The 2026 cars reach the brake point 18 km/h slower (interval 8 to 24) and
take the corner 6 km/h slower (4 to 9). The loss on entry grows with speed:
9 km/h in stops that started below 250 km/h in 2025, 24 km/h in stops from
above 300. Peak deceleration is 0.64 g lower (0.54 to 0.87).

![Brake point by circuit](regs_2025_2026_braking.png)

Even arriving slower, the field brakes 10 m earlier (5 to 15). Less
downforce shows twice: lower corner speed, and less deceleration to get
down to it.

![Lift and coast in races, 2025 against 2026](regs_2025_2026_coast.png)

Lift and coast in races did not grow with the new rules. On the 17 circuits
raced in both seasons the median is 10 % of heavy stops in 2025 and 6 % in
2026, and the change per circuit is −1.0 points (−3.9 to +1.0). Melbourne
and Miami went up; most of the rest went down. Melbourne 2025 was wet and
has only 109 clean laps.

## What is not in here

- Baku 2025 qualifying: the source has no lap table for that session.
- Hungaroring race: the feed has holes of about 1600 m per lap, so only 232
  laps survive the filters.
- Interlagos race: 453 laps on wet-weather tyres are excluded.
- One qualifying lap per driver, the fastest, which mixes Q1, Q2 and Q3
  track conditions.
- No brake pressure or steering in the feed, so nothing about trail braking.
