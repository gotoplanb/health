#!/usr/bin/env python3
"""Generate example Sumo Logic-style dashboard PNG images for local development.

Run: python scripts/generate_example_data.py

Produces PNGs in example-data/dashboards/ that mimic dark-themed Sumo dashboards
with Latency, Requests, and Errors panels. Each dashboard gets 3 snapshots at
different timestamps.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# --- Config ---
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "example-data" / "dashboards"
BG_COLOR = "#1a1a2e"
PANEL_BG = "#16213e"
GRID_COLOR = "#1e3050"
TEXT_COLOR = "#c8c8d0"
TITLE_COLOR = "#e8e8f0"

SERVICES = {
    "api-gateway": {"color": "#ff6b6b", "base_latency": 45, "base_rps": 120, "base_error": 0.5},
    "payment-service": {"color": "#ffd93d", "base_latency": 180, "base_rps": 35, "base_error": 0.2},
    "user-service": {"color": "#6bcb77", "base_latency": 25, "base_rps": 85, "base_error": 0.1},
    "search-service": {"color": "#4d96ff", "base_latency": 95, "base_rps": 60, "base_error": 0.8},
    "notification-service": {"color": "#ff922b", "base_latency": 15, "base_rps": 200, "base_error": 0.05},
}

DASHBOARDS = {
    "platform-overview": {
        "title": "Platform Overview",
        "services": list(SERVICES.keys()),
    },
    "api-gateway": {
        "title": "API Gateway",
        "services": ["api-gateway"],
        "extra_panels": ["P50 Latency", "P99 Latency", "Error Breakdown"],
    },
    "payment-service": {
        "title": "Payment Service",
        "services": ["payment-service"],
        "extra_panels": ["P50 Latency", "P99 Latency", "Error Breakdown"],
    },
    "user-service": {
        "title": "User Service",
        "services": ["user-service"],
        "extra_panels": ["P50 Latency", "P99 Latency", "Error Breakdown"],
    },
}

# 3 snapshots per dashboard: today, yesterday, day before
BASE_TIME = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
SNAPSHOT_OFFSETS = [timedelta(hours=0), timedelta(hours=-24), timedelta(hours=-48)]


def generate_time_series(hours=24, points=288, base=100, volatility=0.15, seed=None):
    """Generate realistic-looking time series data."""
    rng = np.random.RandomState(seed)
    t = np.linspace(0, hours, points)
    # Diurnal pattern (higher during business hours)
    diurnal = 1 + 0.3 * np.sin(2 * np.pi * (t - 6) / 24)
    noise = rng.normal(0, volatility * base, points)
    trend = base * diurnal + noise
    # Occasional spikes
    for _ in range(rng.randint(1, 4)):
        spike_idx = rng.randint(0, points)
        spike_width = rng.randint(2, 8)
        spike_height = base * rng.uniform(1.5, 4)
        start = max(0, spike_idx - spike_width)
        end = min(points, spike_idx + spike_width)
        trend[start:end] += spike_height * np.exp(-0.5 * ((np.arange(start, end) - spike_idx) / (spike_width / 2)) ** 2)
    return t, np.clip(trend, 0, None)


def make_panel(ax, title, ylabel, services_data, legend=True):
    """Draw a single panel (subplot) in Sumo style."""
    ax.set_facecolor(PANEL_BG)
    ax.set_title(title, color=TITLE_COLOR, fontsize=11, fontweight="bold", loc="left", pad=8)
    ax.set_ylabel(ylabel, color=TEXT_COLOR, fontsize=8)
    ax.tick_params(colors=TEXT_COLOR, labelsize=7)
    ax.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.5)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)

    for name, (t, values, color) in services_data.items():
        label = name.replace("-", " ").title()
        ax.plot(t, values, color=color, linewidth=1, alpha=0.85, label=f"{label}, avg {np.mean(values):.1f}")

    ax.set_xlim(0, 24)
    hours = list(range(0, 25, 4))
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], fontsize=7)

    if legend:
        leg = ax.legend(loc="upper right", fontsize=6, facecolor=PANEL_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
        leg.get_frame().set_alpha(0.9)


def generate_overview_dashboard(dashboard_name, config, snapshot_time, seed_base):
    """Generate a multi-service overview dashboard."""
    fig, axes = plt.subplots(3, 1, figsize=(10, 12), facecolor=BG_COLOR)
    fig.subplots_adjust(top=0.92, bottom=0.05, hspace=0.35, left=0.08, right=0.95)

    # Dashboard header
    time_range = f"{(snapshot_time - timedelta(hours=24)).strftime('%Y-%m-%d %I:%M %p')} to {snapshot_time.strftime('%Y-%m-%d %I:%M %p')}"
    fig.suptitle(config["title"], color=TITLE_COLOR, fontsize=14, fontweight="bold", x=0.08, ha="left")
    fig.text(0.95, 0.96, f"(i) {time_range}", color="#888", fontsize=7, ha="right")
    fig.text(0.08, 0.955, "environment: prod", color="#666", fontsize=7,
             bbox=dict(boxstyle="round,pad=0.3", facecolor="#252545", edgecolor="#333"))

    panels = [
        ("Latency", "ms", "base_latency"),
        ("Requests", "req/s", "base_rps"),
        ("Errors", "err %", "base_error"),
    ]

    for ax, (panel_title, ylabel, metric_key) in zip(axes, panels):
        services_data = {}
        for i, svc_name in enumerate(config["services"]):
            svc = SERVICES[svc_name]
            base = svc[metric_key]
            t, values = generate_time_series(
                base=base,
                volatility=0.2 if metric_key != "base_error" else 0.5,
                seed=seed_base + i + hash(panel_title) % 100,
            )
            services_data[svc_name] = (t, values, svc["color"])
        make_panel(ax, panel_title, ylabel, services_data)

    return fig


def generate_service_dashboard(dashboard_name, config, snapshot_time, seed_base):
    """Generate a single-service detailed dashboard with extra panels."""
    fig, axes = plt.subplots(3, 2, figsize=(10, 12), facecolor=BG_COLOR)
    fig.subplots_adjust(top=0.92, bottom=0.05, hspace=0.35, wspace=0.25, left=0.08, right=0.95)

    svc_name = config["services"][0]
    svc = SERVICES[svc_name]

    time_range = f"{(snapshot_time - timedelta(hours=24)).strftime('%Y-%m-%d %I:%M %p')} to {snapshot_time.strftime('%Y-%m-%d %I:%M %p')}"
    fig.suptitle(config["title"], color=TITLE_COLOR, fontsize=14, fontweight="bold", x=0.08, ha="left")
    fig.text(0.95, 0.96, f"(i) {time_range}", color="#888", fontsize=7, ha="right")
    fig.text(0.08, 0.955, "environment: prod", color="#666", fontsize=7,
             bbox=dict(boxstyle="round,pad=0.3", facecolor="#252545", edgecolor="#333"))

    panel_configs = [
        ("Latency (avg)", "ms", svc["base_latency"], 0.2),
        ("P50 Latency", "ms", svc["base_latency"] * 0.8, 0.15),
        ("Requests", "req/s", svc["base_rps"], 0.2),
        ("P99 Latency", "ms", svc["base_latency"] * 3, 0.25),
        ("Errors", "err %", svc["base_error"], 0.5),
        ("Error Breakdown", "count", svc["base_error"] * svc["base_rps"], 0.4),
    ]

    for ax, (panel_title, ylabel, base, vol) in zip(axes.flat, panel_configs):
        t, values = generate_time_series(base=base, volatility=vol, seed=seed_base + hash(panel_title) % 100)
        services_data = {svc_name: (t, values, svc["color"])}
        # For error breakdown, add subcategories
        if panel_title == "Error Breakdown":
            services_data = {}
            for j, err_type in enumerate(["4xx", "5xx", "timeout"]):
                frac = [0.6, 0.25, 0.15][j]
                t2, v2 = generate_time_series(base=base * frac, volatility=vol, seed=seed_base + j + 50)
                colors = ["#ffd93d", "#ff6b6b", "#ff922b"]
                services_data[err_type] = (t2, v2, colors[j])
        make_panel(ax, panel_title, ylabel, services_data)

    return fig


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for dash_name, config in DASHBOARDS.items():
        dash_dir = OUTPUT_DIR / dash_name
        dash_dir.mkdir(parents=True, exist_ok=True)

        is_overview = len(config["services"]) > 1

        for i, offset in enumerate(SNAPSHOT_OFFSETS):
            snapshot_time = BASE_TIME + offset
            ts_str = snapshot_time.strftime("%Y-%m-%dT%H-%M-%SZ")
            seed_base = hash(dash_name) % 10000 + i * 100

            if is_overview:
                fig = generate_overview_dashboard(dash_name, config, snapshot_time, seed_base)
            else:
                fig = generate_service_dashboard(dash_name, config, snapshot_time, seed_base)

            out_path = dash_dir / f"{ts_str}.png"
            fig.savefig(out_path, dpi=150, facecolor=BG_COLOR)
            plt.close(fig)
            print(f"  {out_path}")

    print(f"\nDone! Generated example data in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
