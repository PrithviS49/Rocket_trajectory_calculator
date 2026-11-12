"""
Rocket_Analysis.py
Extra analysis for Proj.py (atmospheric rocket trajectory simulator).

For every launch configuration in trajectory_parameters.csv it:
  1. runs the flight with drag (same physics as Proj.py),
  2. runs the same flight in vacuum (Cd = 0) to show the effect of drag,
  3. checks the solver against the exact burnout velocity of the vacuum flight,
  4. saves graphs and a results table in the 'outputs' folder.

Run:  python Rocket_Analysis.py
"""
import math
import os

import matplotlib
matplotlib.use("Agg")                       # draw to files, no window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import Proj                                 # re-use the physics of the main program

G = Proj.G
SOUND_SPEED = 343.0                         # m/s, same value as Proj.py uses for Mach
OUT = "outputs"
os.makedirs(OUT, exist_ok=True)


def run_flight(row, cd=None):
    """Integrate one flight with Proj.calculate_trajectory. cd=0.0 gives a vacuum flight."""
    return Proj.calculate_trajectory(row, cd=cd)


df = pd.read_csv("trajectory_parameters.csv")
rows = []
flights, vacuum_flights = {}, {}

for _, row in df.iterrows():
    name = row["Launch_Name"]
    sol = run_flight(row)
    vac = run_flight(row, cd=0.0)
    flights[name], vacuum_flights[name] = sol, vac

    m_dot = row["Thrust"] / (row["ISP"] * G)
    burn_time = (row["M_Initial"] - row["M_Dry"]) / m_dot
    x, z, vx, vz = sol.y[0], sol.y[1], sol.y[2], sol.y[3]
    speed = np.hypot(vx, vz)
    rho = Proj.RHO_0 * np.exp(-np.clip(z, 0, None) / Proj.H_SCALE)
    q_max = (0.5 * rho * speed ** 2).max() / 1000                     # kPa

    # exact burnout velocity in vacuum: vx = Isp g cos(th) ln(m0/mdry), vz = Isp g sin(th) ln(m0/mdry) - g tb
    theta = math.radians(row["Theta"])
    ln_ratio = math.log(row["M_Initial"] / row["M_Dry"])
    vx_exact = row["ISP"] * G * math.cos(theta) * ln_ratio
    vz_exact = row["ISP"] * G * math.sin(theta) * ln_ratio - G * burn_time
    # solver state at burnout (end of the powered phase)
    k_b = np.searchsorted(vac.t, vac.t_burnout)
    state_b = vac.y[:, k_b]

    rows.append({
        "Launch_Name": name,
        "Burn_Time_s": round(burn_time, 1),
        "Initial_TWR": round(row["Thrust"] / (row["M_Initial"] * G), 2),
        "Burnout_Altitude_km": round(float(np.interp(sol.t_burnout, sol.t, z)) / 1000, 2),
        "Apogee_km": round(z.max() / 1000, 2),
        "Apogee_Time_s": round(float(sol.t[z.argmax()]), 1),
        "Range_km": round(x[-1] / 1000, 2),
        "Flight_Time_s": round(sol.t[-1], 1),
        "Impact_Speed_ms": round(float(speed[-1]), 1),
        "Impact_Mach": round(float(speed[-1] / SOUND_SPEED), 2),
        "Impact_Angle_deg": round(abs(float(np.degrees(np.arctan2(vz[-1], vx[-1])))), 1),
        "Max_Speed_ms": round(float(speed.max()), 0),
        "Max_q_kPa": round(float(q_max), 1),
        "Apogee_Vacuum_km": round(vac.y[1].max() / 1000, 2),
        "Range_Vacuum_km": round(vac.y[0][-1] / 1000, 2),
        "Impact_Speed_Vacuum_ms": round(float(np.hypot(vac.y[2][-1], vac.y[3][-1])), 0),
        "Burnout_vx_solver_ms": round(float(state_b[2]), 1),
        "Burnout_vx_exact_ms": round(vx_exact, 1),
        "Burnout_vz_solver_ms": round(float(state_b[3]), 1),
        "Burnout_vz_exact_ms": round(vz_exact, 1),
        "Burnout_vx_error_pct": round(100 * (state_b[2] - vx_exact) / vx_exact, 4) + 0.0,
        "Burnout_vz_error_pct": round(100 * (state_b[3] - vz_exact) / vz_exact, 4) + 0.0,
    })

table = pd.DataFrame(rows)
table.to_csv(os.path.join(OUT, "results_summary.csv"), index=False)
print(table.T.to_string(header=False))

colors = {n: c for n, c in zip(flights, ["tab:blue", "tab:orange", "tab:green"])}

# Graph 1: trajectory comparison (same as the plot of Proj.py, but saved to a file)
plt.figure(figsize=(10, 5))
for name, sol in flights.items():
    plt.plot(sol.y[0] / 1000, sol.y[1] / 1000, color=colors[name], label=name)
plt.xlabel("Downrange distance (km)"); plt.ylabel("Altitude (km)")
plt.title("Rocket trajectory comparison (atmospheric drag included)")
plt.grid(True, linestyle="--", alpha=0.6); plt.legend(); plt.tight_layout()
plt.savefig(os.path.join(OUT, "trajectory_comparison_regenerated.png"), dpi=150); plt.close()

# Graph 2: altitude and speed against time
fig, axes = plt.subplots(1, 3, figsize=(13, 4))
for ax, (name, sol) in zip(axes, flights.items()):
    ax.plot(sol.t, sol.y[1] / 1000, color="tab:blue")
    ax.set_xlabel("Time (s)"); ax.set_ylabel("Altitude (km)", color="tab:blue"); ax.grid(alpha=0.3)
    ax2 = ax.twinx(); ax2.plot(sol.t, np.hypot(sol.y[2], sol.y[3]), color="tab:red")
    ax2.set_ylabel("Speed (m/s)", color="tab:red")
    ax.axvline(table.loc[table.Launch_Name == name, "Burn_Time_s"].iloc[0], color="k", ls=":")
    ax.set_title(name.replace("_", " ") + " (dotted line = burnout)", fontsize=9)
plt.suptitle("Altitude and speed against time"); plt.tight_layout()
plt.savefig(os.path.join(OUT, "time_histories.png"), dpi=150); plt.close()

# Graph 3: with drag against vacuum
fig, axes = plt.subplots(1, 3, figsize=(13, 4))
for ax, name in zip(axes, flights):
    ax.plot(flights[name].y[0] / 1000, flights[name].y[1] / 1000, color=colors[name], label="With drag")
    ax.plot(vacuum_flights[name].y[0] / 1000, vacuum_flights[name].y[1] / 1000, "k--", label="No drag (Cd = 0)")
    ax.set_xlabel("Downrange distance (km)"); ax.set_ylabel("Altitude (km)")
    ax.set_title(name.replace("_", " "), fontsize=10); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_xlim(left=0); ax.set_ylim(bottom=0)
plt.suptitle("Effect of atmospheric drag on the trajectories"); plt.tight_layout()
plt.savefig(os.path.join(OUT, "drag_vs_vacuum.png"), dpi=150); plt.close()
print("\nSaved results_summary.csv and 3 graphs in the 'outputs' folder.")
