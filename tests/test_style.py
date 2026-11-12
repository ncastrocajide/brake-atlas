import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from brakeatlas import style  # noqa: E402


def test_delta_scale_is_centred_on_zero():
    norm = style.delta_norm(10.0)
    assert norm(0.0) == 0.5
    assert norm(-10.0) == 0.0
    assert norm(10.0) == 1.0


def test_figure_round_trip(tmp_path):
    style.apply()
    fig, ax = plt.subplots()
    x = np.linspace(0.0, 1.0, 5)
    ax.plot(x, x)
    style.label_end(ax, x, x, "NOR", style.SERIES[0])
    style.headline(ax, "Title", "Subtitle")
    style.source_note(fig)
    out = style.save(fig, tmp_path / "figs" / "demo.png")
    assert out.stat().st_size > 0
