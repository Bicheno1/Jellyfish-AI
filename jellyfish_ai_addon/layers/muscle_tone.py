# layers/muscle_tone.py — CCM v7
#
# MUSCLE TONE SYSTEM
# ══════════════════════════════════════════════════════════════════════
#
# The X-axis of each motor's impact point determines muscle tone:
#
#   Somatic Df:
#     cx > 0  →  Lv dominates  →  muscle tension
#     cx < 0  →  Gv dominates  →  muscle relaxation
#
#   Mental Cf:
#     cx > 0  →  Er dominates  →  muscle tension
#     cx < 0  →  Rr dominates  →  muscle relaxation
#
# The motor with greater euclidean distance (Df vs Cf) determines
# which signal writes to muscle_tension this cycle.
#
# MAGNITUDE MAPPING:
#   The absolute value of cx drives the activation level.
#   Both motors operate in their own scale:
#     Somatic cx max ≈ 200  (Lv or Gv up to 400, cx = (Lv-Gv)/2)
#     Mental  cx max ≈ 100  (Er or Rr up to 200, cx = (Er-Rr)/2)
#
#   Both are normalized to [0.0–1.0] before mapping to % MVC.
#
# MUSCLE TENSION SCALE (% MVC — from db_receptors):
#   very_low    0–10    collapse / frozen
#   low        10–30    relaxed (baseline 20)
#   normal     30–60    functional tone
#   high       60–80    high tension
#   saturated  80–100   max contraction / locked
#
# DIRECTION:
#   tension   → maps |cx| → range 30–100 % MVC  (above baseline)
#   relaxation → maps |cx| → range 0–20  % MVC  (below/at baseline)
#
# ══════════════════════════════════════════════════════════════════════

import math

# Normalization maxima per motor
SOMATIC_CX_MAX = 200.0
MENTAL_CX_MAX  = 100.0

# Muscle tension % MVC ranges
TENSION_MIN    = 30.0   # where tension begins (above normal baseline)
TENSION_MAX    = 100.0  # saturated ceiling
RELAX_MIN      =  0.0   # floor (very_low / frozen)
RELAX_MAX      = 20.0   # baseline ceiling (low)

# Minimum |cx| to register as directional signal
# Below this the X-axis is considered neutral — baseline tone applies
DOMINANCE_THRESHOLD = 3.0


def _label(value: float) -> str:
    """Maps % MVC value to label."""
    if value < 10:  return "very_low"
    if value < 30:  return "low"
    if value < 60:  return "normal"
    if value < 80:  return "high"
    return "saturated"


def _normalize(cx_abs: float, motor: str) -> float:
    """Normalizes |cx| to [0.0–1.0] using the motor's max."""
    cap = SOMATIC_CX_MAX if motor == "somatic" else MENTAL_CX_MAX
    return min(cx_abs / cap, 1.0)


def _map_tension(norm: float) -> float:
    """Maps normalized intensity [0–1] → tension % MVC [30–100]."""
    return TENSION_MIN + norm * (TENSION_MAX - TENSION_MIN)


def _map_relaxation(norm: float) -> float:
    """Maps normalized intensity [0–1] → relaxation % MVC [20–0]."""
    return RELAX_MAX - norm * (RELAX_MAX - RELAX_MIN)


def compute_muscle_tone(dfx: float, df_dist: float,
                        cfx: float, cf_dist: float) -> dict:
    """
    Computes muscle_tone output from both motors.

    Parameters
    ----------
    dfx     : x-component of somatic Df  (positive=Lv, negative=Gv)
    df_dist : euclidean distance of somatic Df
    cfx     : x-component of mental Cf   (positive=Er, negative=Rr)
    cf_dist : euclidean distance of mental Cf

    Returns
    -------
    dict:
        dominant_motor   : "somatic" | "mental"
        direction        : "tension" | "relaxation" | "neutral"
        muscle_tension   : float  — % MVC value to write to core_system
        label            : str    — very_low | low | normal | high | saturated
        somatic_signal   : dict   — what somatic motor would produce
        mental_signal    : dict   — what mental motor would produce
    """
    somatic_signal = _compute_signal(dfx, df_dist, "somatic")
    mental_signal  = _compute_signal(cfx, cf_dist, "mental")

    # Dominant motor = greater distance
    if df_dist >= cf_dist:
        dominant_motor = "somatic"
        active_signal  = somatic_signal
    else:
        dominant_motor = "mental"
        active_signal  = mental_signal

    return {
        "dominant_motor":  dominant_motor,
        "direction":       active_signal["direction"],
        "muscle_tension":  active_signal["value"],
        "label":           active_signal["label"],
        "somatic_signal":  somatic_signal,
        "mental_signal":   mental_signal,
    }


def _compute_signal(cx: float, dist: float, motor: str) -> dict:
    """Computes the tone signal for one motor."""
    abs_cx = abs(cx)

    if abs_cx < DOMINANCE_THRESHOLD or dist < 1.0:
        # Neutral — return baseline
        return {
            "direction": "neutral",
            "value":     20.0,
            "label":     "low",
            "cx":        round(cx, 3),
            "norm":      0.0,
        }

    norm = _normalize(abs_cx, motor)

    if cx > 0:
        # Lv / Er dominates — tension
        value = _map_tension(norm)
        direction = "tension"
    else:
        # Gv / Rr dominates — relaxation
        value = _map_relaxation(norm)
        direction = "relaxation"

    return {
        "direction": direction,
        "value":     round(value, 2),
        "label":     _label(value),
        "cx":        round(cx, 3),
        "norm":      round(norm, 3),
    }


def apply_muscle_tone(dfx: float, df_dist: float,
                      cfx: float, cf_dist: float) -> dict:
    """
    Computes muscle tone and writes the result to core_system.

    Returns the full tone dict (same as compute_muscle_tone).
    """
    from systems.core_system import update_stat

    tone = compute_muscle_tone(dfx, df_dist, cfx, cf_dist)
    update_stat("muscle_tension", tone["muscle_tension"], label=tone["label"])
    return tone
