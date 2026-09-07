"""Render documentation charts using only the published aggregate results."""
from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/benchmark-results/material-gui-mcp-20260908.json"
OUTPUT = ROOT / "docs/assets/agent-evaluation"


def main():
    data = json.loads(DATA.read_text())
    OUTPUT.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 14,
                         "svg.fonttype": "none", "svg.hashsalt": "vase-material-20260908",
                         "axes.spines.top": False,
                         "axes.spines.right": False, "axes.spines.left": False})
    for material in data["materials"]:
        fig, ax = plt.subplots(figsize=(5.2, 2.5))
        fig.subplots_adjust(left=.25, right=.97, top=.94, bottom=.29)
        values = [material["arms"][arm]["total_tokens"]["median"] for arm in ("gui", "mcp")]
        counts = [material["arms"][arm]["strict_successes"] for arm in ("gui", "mcp")]
        ax.barh([1, 0], values, height=.40, color=["#66788b", "#087f74"])
        # All three charts share a zero baseline and the same scale.
        ax.set_xlim(0, 2_500_000)
        ax.set_ylim(-.55, 1.55)
        ax.set_yticks([1, 0], [f"GUI\nn = {counts[0]}", f"MCP\nn = {counts[1]}"])
        ax.tick_params(axis="y", length=0, pad=9, labelsize=16)
        ax.set_xticks([0, 750_000, 1_500_000], ["0", "0.75M", "1.5M"])
        ax.tick_params(axis="x", colors="#52616e", labelsize=13)
        ax.set_xlabel("Median total tokens", fontsize=14, labelpad=9)
        ax.spines["bottom"].set_color("#c4cdd4")
        for y, value in zip([1, 0], values):
            label = f"{value:,.0f}" if value.is_integer() else f"{value:,.1f}"
            ax.text(value + 30_000, y, label, va="center", fontsize=16, color="#172734")
        for extension in ("png", "svg"):
            path = OUTPUT / f"{material['id']}-tokens.{extension}"
            fig.savefig(path, dpi=180, facecolor="white",
                        metadata={"Creator": "v_ase aggregate evaluation", "Date": None} if extension == "svg" else None)
            if extension == "svg":
                path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
        plt.close(fig)


if __name__ == "__main__":
    main()
