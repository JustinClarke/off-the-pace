"""
São Paulo 2021 case study-data extraction and chart generation.

Queries fct_lap_residuals for race_id='2021_19' (Brazilian GP, Round 19).
Generates two PNGs in docs/static/img/case-studies/sao-paulo-2021/:
  1. final-stint-components.png -component evolution HAM vs VER, laps 45-71
  2. lap-decomposition-bars.png -grouped bar chart, 4 key moments
"""

from pathlib import Path
import duckdb
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

DB = Path(__file__).parent.parent / "data" / "dev.duckdb"
IMG_DIR = Path(__file__).parent.parent / "docs" / "images" / "case-studies" / "sao-paulo-2021"
IMG_DIR.mkdir(parents=True, exist_ok=True)

RACE_ID = "2021_19"
RACE_YEAR = 2021


def load_race(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(
        """
        SELECT driver_id, lap_number, position, compound, age_in_stint,
               lap_time_s,
               fuel_component_s,
               compound_component_s,
               rubber_component_s,
               ambient_component_s,
               constructor_component_s,
               driver_skill_residual_s,
               dirty_air_tax_s,
               total_explained_s,
               correction_weight,
               is_safety_car_lap, is_vsc_lap
        FROM fct_lap_residuals
        WHERE race_year = ? AND race_id = ?
        ORDER BY driver_id, lap_number
        """,
        [RACE_YEAR, RACE_ID],
    ).fetchdf()


def print_findings(df: pd.DataFrame) -> None:
    ham = df[df["driver_id"] == "HAM"].copy()
    ver = df[df["driver_id"] == "VER"].copy()

    # Final stint
    ham_final = ham[ham["lap_number"] >= 45]
    ver_final = ver[ver["lap_number"] >= 45]

    print("=== KEY FINDINGS: Sao Paulo 2021 ===\n")

    # Tire age at end
    ham_end = ham_final[ham_final["lap_number"] == 71].iloc[0]
    ver_end = ver_final[ver_final["lap_number"] == 71].iloc[0]
    print(f"Final lap compound_component_s:")
    print(f"  HAM (age {ham_end['age_in_stint']} laps): {ham_end['compound_component_s']:.3f}s")
    print(f"  VER (age {ver_end['age_in_stint']} laps): {ver_end['compound_component_s']:.3f}s")
    print(f"  Tire-age delta:                    {ver_end['compound_component_s']-ham_end['compound_component_s']:.3f}s\n")

    # Driver skill at end
    print(f"Final lap driver_skill_residual_s:")
    print(f"  HAM: {ham_end['driver_skill_residual_s']:.3f}s")
    print(f"  VER: {ver_end['driver_skill_residual_s']:.3f}s\n")

    # Overtake lap (59)
    ham_59 = ham_final[ham_final["lap_number"] == 59].iloc[0]
    ver_59 = ver_final[ver_final["lap_number"] == 59].iloc[0]
    print(f"Lap 59 (overtake):")
    print(f"  HAM: {ham_59['lap_time_s']:.3f}s  |  compound: {ham_59['compound_component_s']:.3f}s  |  skill: {ham_59['driver_skill_residual_s']:.3f}s  |  dirty_air: {ham_59['dirty_air_tax_s']:.3f}s")
    print(f"  VER: {ver_59['lap_time_s']:.3f}s  |  compound: {ver_59['compound_component_s']:.3f}s  |  skill: {ver_59['driver_skill_residual_s']:.3f}s  |  dirty_air: {ver_59['dirty_air_tax_s']:.3f}s")
    lap_time_gap = ver_59["lap_time_s"]-ham_59["lap_time_s"]
    compound_gap = ver_59["compound_component_s"]-ham_59["compound_component_s"]
    skill_gap = ham_59["driver_skill_residual_s"]-ver_59["driver_skill_residual_s"]
    print(f"  Gap explained by tire age: {compound_gap:.3f}s  |  driver skill: {skill_gap:.3f}s  |  combined: {compound_gap + abs(skill_gap):.3f}s  |  actual gap: {lap_time_gap:.3f}s\n")

    # Base pace equality (fresh tire laps, 45-50)
    ham_fresh = ham_final[(ham_final["lap_number"] >= 45) & (ham_final["lap_number"] <= 50)]
    ver_fresh = ver_final[(ver_final["lap_number"] >= 45) & (ver_final["lap_number"] <= 50)]
    print(f"Laps 45-50 (fresh-tire baseline):")
    print(f"  HAM avg lap time: {ham_fresh['lap_time_s'].mean():.3f}s (tire ages {ham_fresh['age_in_stint'].min()}-{ham_fresh['age_in_stint'].max()})")
    print(f"  VER avg lap time: {ver_fresh['lap_time_s'].mean():.3f}s (tire ages {ver_fresh['age_in_stint'].min()}-{ver_fresh['age_in_stint'].max()})\n")

    # Cumulative time delta in closing phase (laps 59-71)
    ham_closing = ham_final[ham_final["lap_number"] >= 59]["lap_time_s"].sum()
    ver_closing = ver_final[ver_final["lap_number"] >= 59]["lap_time_s"].sum()
    print(f"Laps 59-71 cumulative:")
    print(f"  HAM total: {ham_closing:.3f}s")
    print(f"  VER total: {ver_closing:.3f}s")
    print(f"  HAM advantage: {ver_closing-ham_closing:.3f}s\n")

    print(f"HAM dirty_air laps (final stint): {(ham_final['dirty_air_tax_s'] > 0).sum()} laps, cumulative: {ham_final['dirty_air_tax_s'].sum():.3f}s")
    print(f"VER dirty_air laps (final stint): {(ver_final['dirty_air_tax_s'] > 0).sum()} laps, cumulative: {ver_final['dirty_air_tax_s'].sum():.3f}s")


def plot_component_evolution(df: pd.DataFrame) -> None:
    """Line chart: compound_component_s and driver_skill_residual_s, laps 42-71."""
    ham = df[(df["driver_id"] == "HAM") & (df["lap_number"] >= 42)].copy()
    ver = df[(df["driver_id"] == "VER") & (df["lap_number"] >= 42)].copy()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    fig.suptitle(
        "São Paulo 2021-Final Stint: Tyre Degradation vs Driver Skill",
        fontsize=14, fontweight="bold", y=0.98
    )

    # ---- Panel 1: compound degradation ----
    ax1.plot(ver["lap_number"], ver["compound_component_s"], color="#E8002D",
             linewidth=2.5, label="VER-Hard (31 laps)", zorder=3)
    ax1.plot(ham["lap_number"], ham["compound_component_s"], color="#00D2BE",
             linewidth=2.5, label="HAM-Hard (27 laps)", zorder=3)
    ax1.axvline(x=59, color="#888", linestyle="--", linewidth=1.2, zorder=2)
    ax1.annotate("Lap 59\novertake", xy=(59, ax1.get_ylim()[1] if ax1.get_ylim()[1] > 0 else 1),
                 xytext=(60.5, 10), fontsize=9, color="#444",
                 arrowprops=dict(arrowstyle="->", color="#888", lw=1))
    ax1.set_ylabel("Compound component (s)\n[positive = slower]", fontsize=10)
    ax1.set_ylim(0, 16)
    ax1.yaxis.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(fontsize=10, loc="upper left")
    ax1.set_title("Tyre-age penalty growing over stint", fontsize=11, pad=4)

    # annotate final-lap values
    ax1.annotate(f"+{ver.iloc[-1]['compound_component_s']:.1f}s",
                 xy=(71, ver.iloc[-1]["compound_component_s"]),
                 xytext=(71.3, ver.iloc[-1]["compound_component_s"]-0.8),
                 fontsize=9, color="#E8002D")
    ax1.annotate(f"+{ham.iloc[-1]['compound_component_s']:.1f}s",
                 xy=(71, ham.iloc[-1]["compound_component_s"]),
                 xytext=(71.3, ham.iloc[-1]["compound_component_s"] + 0.5),
                 fontsize=9, color="#00D2BE")

    # ---- Panel 2: driver skill residual ----
    ax2.plot(ver["lap_number"], ver["driver_skill_residual_s"], color="#E8002D",
             linewidth=2.5, label="VER", zorder=3)
    ax2.plot(ham["lap_number"], ham["driver_skill_residual_s"], color="#00D2BE",
             linewidth=2.5, label="HAM", zorder=3)
    ax2.axhline(y=0, color="#aaa", linestyle="-", linewidth=0.8)
    ax2.axvline(x=59, color="#888", linestyle="--", linewidth=1.2, zorder=2)
    ax2.set_ylabel("Driver skill residual (s)\n[negative = faster than model]", fontsize=10)
    ax2.set_ylim(-15, 1)
    ax2.yaxis.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(fontsize=10, loc="lower left")
    ax2.set_xlabel("Lap number", fontsize=10)
    ax2.set_title("Driver outdriving the car-skill residual deepening", fontsize=11, pad=4)

    # annotate final-lap values
    ax2.annotate(f"{ver.iloc[-1]['driver_skill_residual_s']:.1f}s",
                 xy=(71, ver.iloc[-1]["driver_skill_residual_s"]),
                 xytext=(71.3, ver.iloc[-1]["driver_skill_residual_s"] + 0.8),
                 fontsize=9, color="#E8002D")
    ax2.annotate(f"{ham.iloc[-1]['driver_skill_residual_s']:.1f}s",
                 xy=(71, ham.iloc[-1]["driver_skill_residual_s"]),
                 xytext=(71.3, ham.iloc[-1]["driver_skill_residual_s"]-1.2),
                 fontsize=9, color="#00D2BE")

    plt.tight_layout()
    out = IMG_DIR / "final-stint-components.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


def plot_lap_decomposition_bars(df: pd.DataFrame) -> None:
    """Grouped bar: actual vs 'car-only' lap time for HAM & VER at 4 key laps."""
    key_laps = [45, 55, 65, 71]
    ham = df[df["driver_id"] == "HAM"].set_index("lap_number")
    ver = df[df["driver_id"] == "VER"].set_index("lap_number")

    ham_actual = [ham.loc[l, "lap_time_s"] for l in key_laps]
    ver_actual = [ver.loc[l, "lap_time_s"] for l in key_laps]
    ham_skill = [ham.loc[l, "driver_skill_residual_s"] for l in key_laps]
    ver_skill = [ver.loc[l, "driver_skill_residual_s"] for l in key_laps]
    # "car-only" = what the lap time would be without the driver skill contribution
    ham_car = [a-s for a, s in zip(ham_actual, ham_skill)]
    ver_car = [a-s for a, s in zip(ver_actual, ver_skill)]

    x = range(len(key_laps))
    width = 0.2

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.suptitle(
        "São Paulo 2021-How Much Driving Is the Driver?",
        fontsize=14, fontweight="bold"
    )

    bars_ham_car = ax.bar([i-1.5 * width for i in x], ham_car, width,
                          label="HAM-car+tyre pace", color="#00D2BE", alpha=0.5, zorder=3)
    bars_ham_act = ax.bar([i-0.5 * width for i in x], ham_actual, width,
                          label="HAM-actual lap time", color="#00D2BE", alpha=0.95, zorder=3)
    bars_ver_car = ax.bar([i + 0.5 * width for i in x], ver_car, width,
                          label="VER-car+tyre pace", color="#E8002D", alpha=0.5, zorder=3)
    bars_ver_act = ax.bar([i + 1.5 * width for i in x], ver_actual, width,
                          label="VER-actual lap time", color="#E8002D", alpha=0.95, zorder=3)

    # Annotate driver skill contribution brackets
    for i, lap in enumerate(key_laps):
        hs = abs(ham_skill[i])
        vs = abs(ver_skill[i])
        ax.annotate(
            f"−{hs:.1f}s", xy=(i-1.5 * width, ham_car[i]),
            xytext=(i-1.5 * width, ham_actual[i]-hs / 2),
            ha="center", va="center", fontsize=7.5, color="white", fontweight="bold"
        )
        ax.annotate(
            f"−{vs:.1f}s", xy=(i + 0.5 * width, ver_car[i]),
            xytext=(i + 0.5 * width, ver_actual[i]-vs / 2),
            ha="center", va="center", fontsize=7.5, color="white", fontweight="bold"
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"Lap {l}" for l in key_laps], fontsize=11)
    ax.set_ylabel("Lap time (seconds)", fontsize=11)
    ax.set_ylim(70, 80)
    ax.yaxis.grid(True, linestyle=":", alpha=0.5)
    ax.legend(fontsize=9, loc="upper left", ncol=2)
    ax.set_title(
        "Faded bar = structural pace (car + tyre age). Solid bar = actual time driven.\n"
        "Gap = driver skill residual. Both drivers are outdriving their tyres-but by how much?",
        fontsize=10, pad=6
    )

    plt.tight_layout()
    out = IMG_DIR / "lap-decomposition-bars.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    df = load_race(con)
    con.close()

    print_findings(df)
    plot_component_evolution(df)
    plot_lap_decomposition_bars(df)


if __name__ == "__main__":
    main()
