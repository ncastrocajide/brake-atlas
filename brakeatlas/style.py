"""Figure style shared by every plot in the repo.

Matplotlib's defaults (tab10 blue and orange, boxed legend, full frame,
centred title) make every figure look the same as every other notebook
plot. The rules here:

- The title states the result ("HAM brakes 8 m later than the field into
  T1"), the subtitle says what is plotted and from which session.
  Left-aligned, no parenthesised debug info.
- Two lines are labelled at their right end, not with a legend box.
- Axes carry units ("Speed [km/h]"). No top or right spine; the grid is
  a hairline on y only.
- Brake-point deltas use a diverging map: blue = earlier than the field,
  red = later, neutral grey at zero, symmetric limits.
- Magnitudes use a single-hue blue ramp. No viridis or rainbow.
- Every figure saved for the README gets a source line at the bottom.

Colours come from a palette checked for colour-blind separation.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"  # subtitles, axis labels, notes
GRID = "#e1e0d9"
NEUTRAL = "#f0efec"  # diverging midpoint

# Categorical order, used for two- or three-line comparisons. Keep the
# order: it is what keeps neighbours apart for colour-blind readers.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")

BLUE_RAMP = ("#cde2fb", "#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b")

EARLIER = "#1c5cab"  # brakes before the field median
LATER = "#b8312f"  # brakes after it

SOURCE = "Data: Formula 1 timing via FastF1"


def apply() -> None:
    """Set the rcParams. Call once before building figures."""
    mpl.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "axes.edgecolor": INK_2,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.labelcolor": INK_2,
            "axes.labelsize": 9,
            "axes.titlelocation": "left",
            "axes.prop_cycle": mpl.cycler(color=SERIES),
            "xtick.color": INK_2,
            "ytick.color": INK_2,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "lines.linewidth": 1.4,
            "legend.frameon": False,
            "font.size": 9,
            "text.color": INK,
            "figure.dpi": 100,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
        }
    )


def headline(ax, title: str, subtitle: str | None = None) -> None:
    """Title (the finding) and grey subtitle (what is shown) above `ax`.

    Anchored to the top of the axes and to the left edge of the figure,
    so the gap to the plot stays the same whatever the figure height.
    """
    anchor = {"xy": (0.01, 1.0), "xycoords": ("figure fraction", "axes fraction")}
    lift = 30 if subtitle else 12
    ax.annotate(
        title,
        **anchor,
        xytext=(0, lift),
        textcoords="offset points",
        ha="left",
        va="bottom",
        fontsize=12,
        color=INK,
        fontweight="bold",
        annotation_clip=False,
    )
    if subtitle:
        ax.annotate(
            subtitle,
            **anchor,
            xytext=(0, 12),
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=9,
            color=INK_2,
            annotation_clip=False,
        )


def source_note(fig, text: str = SOURCE) -> None:
    """Source line under the plot area."""
    fig.text(0.01, 0.005, text, ha="left", va="bottom", fontsize=7, color=INK_2)


def label_end(ax, x, y, text: str, color: str, dy: float = 0.0) -> None:
    """Write a series label just right of its last point, in the series colour."""
    ax.annotate(
        text,
        (x[-1], y[-1]),
        xytext=(4, dy),
        textcoords="offset points",
        va="center",
        fontsize=8,
        color=color,
        fontweight="bold",
        annotation_clip=False,
    )


def delta_cmap() -> LinearSegmentedColormap:
    """Blue (earlier) to grey (field median) to red (later)."""
    return LinearSegmentedColormap.from_list("brake_delta", [EARLIER, NEUTRAL, LATER])


def delta_norm(limit: float) -> TwoSlopeNorm:
    """Colour scale centred on zero, symmetric at +/- limit."""
    return TwoSlopeNorm(vcenter=0.0, vmin=-limit, vmax=limit)


def magnitude_cmap() -> LinearSegmentedColormap:
    """Single-hue blue ramp for magnitudes (speed, deceleration)."""
    return LinearSegmentedColormap.from_list("blue_ramp", BLUE_RAMP)


def save(fig, path: str | Path) -> Path:
    """Save at README resolution and close the figure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
