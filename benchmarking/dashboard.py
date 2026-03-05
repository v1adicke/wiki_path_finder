from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.patches import Circle, FancyBboxPatch


STATUS_LABELS = ["success", "not_found", "timeout", "error"]
STATUS_COLORS = ["#189a68", "#6f7b8d", "#dc9b2f", "#d94f4f"]


def _draw_kpi_card(ax, title: str, value: str, subtitle: str = "") -> None:
    ax.axis("off")
    card = FancyBboxPatch(
        (0.0, 0.05),
        1.0,
        0.9,
        boxstyle="round,pad=0.03,rounding_size=0.1",
        linewidth=0.5,
        edgecolor="#E2E8F0",
        facecolor="#F8FAFC",
        transform=ax.transAxes,
        zorder=1,
    )
    ax.add_patch(card)
    ax.text(0.1, 0.70, title.upper(), fontsize=12, color="#64748B", fontweight="bold", transform=ax.transAxes, zorder=2)
    ax.text(0.1, 0.35, value, fontsize=26, color="#0F172A", fontweight="bold", transform=ax.transAxes, zorder=2)
    if subtitle:
        ax.text(0.1, 0.12, subtitle, fontsize=10, color="#94A3B8", transform=ax.transAxes, zorder=2)


def _draw_logo(ax, logo_path: Path) -> None:
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    image = plt.imread(str(logo_path))
    image_box = OffsetImage(image, zoom=0.24, cmap="gray")
    ann = AnnotationBbox(image_box, (0.5, 0.5), frameon=False)
    ax.add_artist(ann)


def _style_panel(ax, title: str) -> None:
    ax.set_facecolor("#FFFFFF")
    for spine in ax.spines.values():
        spine.set_color("#DDE3EB")
        spine.set_linewidth(1.0)
    ax.set_title(title, fontsize=13, fontweight="bold", color="#263244", pad=12)


def render_dashboard(
    summary: Dict,
    output_path: Path,
    logo_path: Path,
    version: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="white", context="paper", font_scale=0.9)

    fig = plt.figure(figsize=(18, 10), dpi=130, facecolor="white")
    gs = fig.add_gridspec(nrows=20, ncols=24)

    fig.suptitle("Wiki Path Finder Benchmark Dashboard", fontsize=24, fontweight="bold", color="#1E2A3B")

    ax_kpi_1 = fig.add_subplot(gs[1:4, 1:6])
    ax_kpi_2 = fig.add_subplot(gs[1:4, 7:12])
    ax_kpi_3 = fig.add_subplot(gs[1:4, 12:17])
    ax_kpi_4 = fig.add_subplot(gs[1:4, 18:23])

    _draw_kpi_card(ax_kpi_1, "Запросов", str(summary.get("total_cases", 0)), "Общий объем прогона")
    _draw_kpi_card(ax_kpi_2, "Успех", f"{summary.get('success_rate', 0.0):.1f}%", "Доля найденных путей")
    _draw_kpi_card(ax_kpi_3, "Среднее время", f"{summary.get('avg_time', 0.0):.2f}s", "Mean latency")
    _draw_kpi_card(ax_kpi_4, "p95 / max", f"{summary.get('p95_time', 0.0):.2f}s / {summary.get('max_time', 0.0):.2f}s", "Хвосты распределения")

    ax_logo = fig.add_subplot(gs[5:13, 9:15])
    _draw_logo(ax_logo, logo_path)

    ax_status = fig.add_subplot(gs[5:13, 1:8])
    _style_panel(ax_status, "Статусы")
    counts = summary.get("status_counts", {})
    values = [int(counts.get(label, 0)) for label in STATUS_LABELS]
    if sum(values) > 0:
        ax_status.pie(values, labels=STATUS_LABELS, autopct="%1.0f%%", startangle=90, colors=STATUS_COLORS, textprops={"fontsize": 9}, wedgeprops=dict(width=0.4, edgecolor='w'))
    else:
        ax_status.text(0.5, 0.5, "Нет данных", ha="center", va="center", fontsize=11)

    ax_latency = fig.add_subplot(gs[5:13, 16:23])
    _style_panel(ax_latency, "Распределение latency")
    elapsed: List[float] = [float(item.get("elapsed_sec", 0.0)) for item in summary.get("results", [])]
    if elapsed:
        sns.histplot(elapsed, bins=min(24, max(8, len(elapsed) // 12)), color="#4F9BD9", alpha=0.7, edgecolor="white", ax=ax_latency)
        p50 = float(summary.get("median_time", 0.0))
        p90 = float(summary.get("p90_time", 0.0))
        p95 = float(summary.get("p95_time", 0.0))
        for x, c, label in [(p50, "#2E7D65", "p50"), (p90, "#E3A33E", "p90"), (p95, "#D94F4F", "p95")]:
            ax_latency.axvline(x=x, color=c, linestyle="--", linewidth=1.5, label=f"{label}: {x:.2f}s")
        ax_latency.legend(frameon=False, fontsize=10, loc="upper right")
    ax_latency.set_xlabel("Время выполнения (сек)", fontsize=11)
    ax_latency.set_ylabel("Количество", fontsize=11)
    sns.despine(ax=ax_latency, top=True, right=True)

    ax_difficulty = fig.add_subplot(gs[14:19, 4:20])
    _style_panel(ax_difficulty, "Success rate по сложности")
    diff_stats = summary.get("difficulty_stats", {})
    diff_labels = list(diff_stats.keys())
    succ_rates = [float(diff_stats[label].get("success_rate", 0.0)) for label in diff_labels]
    
    if diff_labels:
        sns.barplot(x=diff_labels, y=succ_rates, ax=ax_difficulty, color="#189a68", alpha=0.8, width=0.6)
    
    ax_difficulty.set_ylim(0, 100)
    ax_difficulty.set_ylabel("Успешность (%)", fontsize=11)
    ax_difficulty.set_xlabel("Сложность", fontsize=11)
    sns.despine(ax=ax_difficulty, top=True, right=True)
    
    for i, val in enumerate(succ_rates):
        ax_difficulty.text(i, val + 2, f"{val:.0f}%", ha="center", va="bottom", fontsize=11, fontweight='bold')

    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    footer = f"Версия: {version} | Дата построения: {timestamp}"
    fig.text(0.5, 0.02, footer, ha="center", fontsize=10, color="#5F6B7E")

    fig.subplots_adjust(left=0.03, right=0.985, top=0.91, bottom=0.07, wspace=1.0, hspace=1.15)

    fig.savefig(output_path, facecolor="white")
    plt.close(fig)
