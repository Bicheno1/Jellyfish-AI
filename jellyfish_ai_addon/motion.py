# motion.py — Jellyfish AI motion system
#
# v2 — weighted blend across the 16 active modes, mirroring
# chemical_system.ChemicalSystem.get_somatic_push() exactly: each mode
# contributes to the total proportionally to its current level, so the
# highest-level mode dominates the outcome without erasing the others.
# This replaces the earlier quadrant+tension lookup table, which used
# the WHOLE state's cy sign (viable/inviable) to pick direction — wrong,
# because attack/flee/accept/cooperate all live on the Lv/Gv (cx) axes,
# not on V/I (cy), so danger/benefit never reliably flipped cy. Direction
# now comes directly from each mode's own predefined pattern, blended by
# weight — the centroid still governs overall amplitude via muscle_tone.

# ── PER-MODE MOVEMENT PATTERN ────────────────────────────────────────────────
# One entry per MATRIX_MODES cell (systems/chemical_system.py). Mirrors that
# table's own shape: a small fixed pattern per (category, axis), same as
# every mode already has an "emotion"/"peak_push"/"half_life".
#   heading : -1 away from target, 0 no directional pull, +1 toward target
#   speed   : 0-1 how eager this mode is to actually translate
#   wave    : 0-1 tentacle-ripple emphasis
#   freeze  : this mode, if dominant, overrides everything to a hard stop

MODE_MOTION = {
    # -- danger --
    "attack":     {"heading":  0, "speed": 0.1, "wave": 1.0, "freeze": False},  # strike in place
    "surrender":  {"heading":  0, "speed": 0.0, "wave": 0.0, "freeze": True},   # go limp
    "protect":    {"heading":  1, "speed": 0.4, "wave": 0.2, "freeze": False},  # interpose for an ally
    "flee":       {"heading": -1, "speed": 1.0, "wave": 0.3, "freeze": False},  # away, fast
    # -- benefit --
    "accept":     {"heading":  1, "speed": 0.6, "wave": 0.2, "freeze": False},  # approach/feed
    "deny":       {"heading": -1, "speed": 0.3, "wave": 0.1, "freeze": False},  # withdraw from excess
    "cooperate":  {"heading":  1, "speed": 0.3, "wave": 0.4, "freeze": False},  # drift toward
    "ignore_benefit": {"heading": 0, "speed": 0.0, "wave": 0.0, "freeze": False},  # no change
    # -- neutral --
    "observe":        {"heading":  1, "speed": 0.1, "wave": 0.1, "freeze": False},  # orient only
    "ignore_neutral": {"heading":  0, "speed": 0.15, "wave": 0.0, "freeze": False},  # idle drift
    "group":          {"heading":  1, "speed": 0.2, "wave": 0.3, "freeze": False},  # loose schooling
    "formulate":      {"heading":  0, "speed": 0.1, "wave": 0.1, "freeze": False},  # slow scan pulse
    # -- unclassifiable --
    "investigate": {"heading":  1, "speed": 0.3, "wave": 0.2, "freeze": False},  # cautious approach
    "desist":      {"heading": -1, "speed": 0.2, "wave": 0.0, "freeze": False},  # disengage
    "signal":      {"heading":  1, "speed": 0.3, "wave": 0.5, "freeze": False},  # group up (school toward ally)
    "suppress":    {"heading":  0, "speed": 0.0, "wave": 0.0, "freeze": True},   # freeze
}

_ACTIVE_THRESHOLD = 0.05  # matches chemical_system._ZERO_THRESHOLD's spirit


def build_motion(chem_levels: dict, muscle: dict) -> dict:
    """
    Blends every currently-active mode's movement pattern, weighted by
    level/10 -- same normalization ChemicalSystem.get_somatic_push() uses.

    chem_levels : ChemicalSystem.levels (mode_name -> 0-10 level)
    muscle      : layers.muscle_tone.compute_muscle_tone() output -- the
                  centroid already governs contraction amplitude, this
                  function only adds heading/speed/wave on top of it.
    """
    total_w = heading_sum = speed_sum = wave_sum = freeze_w = 0.0
    active_modes = []

    for mode_name, level in chem_levels.items():
        if level < _ACTIVE_THRESHOLD:
            continue
        w = level / 10.0
        pat = MODE_MOTION[mode_name]
        heading_sum += w * pat["heading"]
        speed_sum   += w * pat["speed"]
        wave_sum    += w * pat["wave"]
        if pat["freeze"]:
            freeze_w += w
        total_w += w
        active_modes.append((mode_name, round(w, 3)))

    contraction = muscle["muscle_tension"] / 100.0

    if not active_modes:
        # no mode cleared the per-mode inclusion bar -> idle drift baseline
        return {"heading": 0.0, "speed": 0.15, "wave": 0.0,
                "contraction": contraction, "frozen": False,
                "drifting": True, "active_modes": []}

    frozen = (freeze_w / total_w) > 0.5
    if frozen:
        return {"heading": 0.0, "speed": 0.0, "wave": 0.0,
                "contraction": 0.0, "frozen": True,
                "drifting": False, "active_modes": active_modes}

    heading = heading_sum / total_w         # weighted average direction, -1..+1
    speed   = min(1.0, speed_sum)           # NOT normalized: several modes
                                             # firing together raises urgency
    wave    = min(1.0, wave_sum)

    return {
        "heading":     round(heading, 3),
        "speed":       round(speed, 3),
        "wave":        round(wave, 3),
        "contraction": round(contraction, 3),
        "frozen":      False,
        "drifting":    False,               # at least one mode is meaningfully active
        "active_modes": active_modes,        # for debugging/console output
    }
