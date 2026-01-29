# The `/race` Page: Detailed Text Mockup

This document provides a highly detailed, text-based wireframe of the `/race` interactive dashboard (leaning towards the premium, data-journalism "Slate Chronicle" aesthetic combined with high-density telemetry). 

The goal is to show you exactly *what data* is on the screen, *where* it lives, and *how* the user interacts with it, so you can finalize your feature set.

---

## 🌐 1. Global Navigation & Page Header

**[Logo: OFF THE PACE]**    |    [Races ▾]    [Drivers ▾]    [Methodology]    |    [Dark Mode Toggle ☾]    [GitHub Icon]

> **Abu Dhabi Grand Prix (2021)   Yas Marina Circuit**
> *58 Laps | 5.281 km | High Track Evolution | High Degradation*
> 
> *Subtitle:* The raw timing screens tell you Max Verstappen won. The math tells us a different story. This is the isolated causal breakdown of the 2021 title decider.

---

## 📊 2. The Hero Component: The True Skill Leaderboard

*This sits at the top of the page. Unlike standard F1 sites that rank by finish position or fastest lap, this ranks by **Isolated Driver Residual** ($\epsilon_{driver}$).*

**[Toggle View: ◯ Race Average  |  ◉ Best Stint  |  ◯ Qualifying]**

**THE CAUSAL LEADERBOARD (Race Average Lap)**
*Hover over any row to see the exact formula breakdown.*

| Rank | Driver | Raw Avg Pace | Car Penalty/Bonus | Dirty Air Tax | Fuel Adj | **True Skill Residual** |
|:---|:---|:---|:---|:---|:---|:---|
| **1.** | **VER** (Red Bull) | 1:26.312 | +0.000s *(Baseline)* | +0.14s | -0.82s | **-0.230s / lap** 👑 |
| **2.** | **HAM** (Mercedes) | 1:26.155 | -0.150s *(Faster Car)*| +0.05s | -0.80s | **-0.185s / lap** |
| **3.** | **PER** (Red Bull) | 1:27.010 | +0.000s *(Baseline)* | +0.42s | -0.82s | **-0.050s / lap** |
| **4.** | **SAI** (Ferrari)  | 1:27.442 | +0.850s *(Slower Car)*| +0.11s | -0.81s | **-0.020s / lap** |
| ... | ... | ... | ... | ... | ... | ... |

> **Interactive behavior:** 
> * Clicking a driver (e.g., HAM) expands a drawer showing their exact $\epsilon_{driver}$ trend across the race (Stint 1 vs Stint 2).
> * **Recruiter Signal:** Tooltip over "Car Penalty" explains it is derived from `power_pace_index` and `aero_pace_index` XGBoost feature importance.

---

## 📈 3. The Scrollytelling Split: Telemetry vs. Narrative

*As the user scrolls down, the page splits into two columns. The **Left Column** stays pinned in place (showing interactive charts). The **Right Column** scrolls past, containing your editorial narrative and interactive controls.*

### 📍 Pinned Left Pane: The Telemetry Canvas
*(This visual morphs depending on what the user is reading on the right).*

**[Currently Displaying: LAP DECOMPOSITION VISUALIZER]**

```text
[Y-Axis: Lap Time (s)]
1:32 |       . *                  (Raw Lap Time-Dotted Gray Line)
     |     .     * .   
1:30 |   .           * .          (Fuel Corrected Pace-Solid Blue Line)
     | .                 * .      
1:28 |.                      * .  (True Driver Input-Glowing Green Line)
     | 
1:26 |___________________________*___
     | L10   L15   L20   L25   L30
         [X-Axis: Lap Number]
```
*(A shaded red region appears on laps 14-16)* → **Tooltip:** "Dirty Air Wake Detected (Gap < 1.5s)"

### 📜 Scrolling Right Pane: The Narrative & Controls

**(Text Block 1)**
"On Lap 14, Hamilton caught the turbulent wake of Perez. While the official timing screen shows his lap times dropping off by 0.6 seconds, our models indicate his tires were perfectly fine. He was paying the **Dirty Air Tax**."

**(Interactive Widget inside the text)**
**[Select Driver: HAM ▾]** vs **[Trailing: PER ▾]**
* **Sector 1 Tax:** +0.05s
* **Sector 2 Tax:** +0.45s ⚠️ *(High wake turbulence)*
* **Sector 3 Tax:** +0.10s

*(When the user clicks this widget, the Pinned Left Pane instantly changes to a vector map of the Yas Marina circuit, highlighting Sector 2 in glowing red).*

---

## 🏎️ 4. The "Ghost Car" Sandbox (Powered by DuckDB-Wasm)

*A dedicated interactive section allowing fans to run counterfactuals using the ML coefficients.*

**Simulate a Counterfactual Stint**
*What if we put a different driver in the dominant car?*

**[Target Car: 2021 Mercedes W12 ▾]**  *(Sets base pace to 1:25.800)*
**[Select Ego Driver: L. Norris ▾]** *(Applies Norris's historical $\epsilon_{driver}$ of -0.08s)*

**[RUN SIMULATION ▶]** *(Executes sub-5ms Wasm query)*

**Simulation Results:**
> **Projected Pace:** 1:25.720 / lap
> **Delta to Hamilton in same car:** +0.105s slower
> **Predicted Finish Position:** 2nd

*(Below the results, two animated dots race around a minimalist SVG track outline, visually demonstrating the +0.105s gap compounding lap after lap).*

---

## 📉 5. The Pit-Wall: Tyre Cliff & Strategy Simulator

*This section exposes the XGBoost survival fitter and thermal hysteresis model.*

**Tyre Survival Curve & Cliff Prediction**
**[Select Driver: VER ▾]** **[Select Stint: 2 (Hard Tyre) ▾]**

**[Interactive Slider: Drag to simulate lap progression]**
`Lap 20 [========O--------------------------] Lap 58`

**Live ML Inference Panel:**
* **Current Tyre Life:** 15 Laps
* **Thermal Hysteresis Load:** 68% (Stable)
* **Predicted Degradation Rate:** 0.04s / lap
* **⚠️ XGBoost Cliff Prediction:** Lap 42 (95% Confidence Interval: L40-L45)

**Strategy Sandbox:**
*Drag the 'Pit Stop' marker on the timeline to see how an undercut changes the race.*

`[----- Pit Stop @ L35 (Current) ▾ -----]`
> **Result:** Undercut fails. Re-enters traffic on Lap 36, pays +0.4s Dirty Air Tax.

`[----- Pit Stop @ L31 (Simulated) ▾ -----]`
> **Result:** Undercut succeeds. Clears traffic, utilizes peak mechanical grip, gains +1.2s net advantage over HAM.

---

## 🧠 6. The Engineering Recruiter Footer (The Moat)

*A subtle but highly visible section specifically for hiring managers to prove it's not just a toy.*

**Behind the Data (View Source)**
* **Pipeline:** Raw telemetry parsed via FastF1 → dbt Silver/Gold models → Parquet.
* **ML Architecture:** XGBoost Regressor trained on 128k stint-laps with `TimeSeriesSplit` validation.
* **Current UI Performance:** 1.2MB Parquet payload executed locally via DuckDB-Wasm in `4ms`.
* **[View full dbt DAG & Methodology →]** *(Links to the `/build` page)*

---

### Does this text mockup cover all your desired features?
This layout incorporates the **Leaderboard**, **Lap Decomposition**, **Dirty Air Tax**, **Ghost Car Sandbox**, and **Tyre Cliff Strategy**. Let me know if you want to add, remove, or emphasize any specific widget!
