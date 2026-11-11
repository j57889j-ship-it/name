"""Generate dark terminal charts in memory, without temporary files."""
from __future__ import annotations
import asyncio
from io import BytesIO


def _render_growth(rows: list[dict]) -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(9, 4.8), dpi=140, facecolor="#0D1117")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0D1117")
    labels = [r["day"][5:] for r in rows]
    values = [r["total"] for r in rows]
    ax.plot(labels, values, color="#00FF9C", linewidth=2.4, marker="o", markersize=3)
    ax.fill_between(range(len(values)), values, color="#00FF9C", alpha=0.12)
    ax.grid(True, color="#29313B", linewidth=0.6)
    ax.tick_params(colors="#8B949E", labelsize=8)
    for spine in ax.spines.values(): spine.set_color("#29313B")
    ax.set_title("DASTURLASH & AI / USER GROWTH", color="#00FF9C", loc="left", fontsize=11, fontfamily="monospace", pad=14)
    ax.set_ylabel("New users", color="#8B949E")
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()
    buffer = BytesIO()
    FigureCanvasAgg(fig).print_png(buffer)
    return buffer.getvalue()


async def growth_chart(rows: list[dict]) -> BytesIO:
    data = await asyncio.to_thread(_render_growth, rows)
    buffer = BytesIO(data)
    buffer.seek(0)
    return buffer
