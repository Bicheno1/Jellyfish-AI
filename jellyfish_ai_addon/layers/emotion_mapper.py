# layers/emotion_mapper.py — CCM v7
#
# EMOTION MAPPER
# Maps emotional state from tags (mental_state_levels / chemical_levels)
# + quadrant + saturation.
#
# PRIMARY signal: which tags are active and at what level
# SECONDARY signal: quadrant (confirms direction)
# TERTIARY signal: saturation (confirms intensity)
#
# This is more robust than angle-based mapping because tags carry
# explicit semantic meaning — no geometric inference needed.
#
# mental STATES (from mental_state_system):
#   fear, loneliness, anguish, security, joy, calm
#
# SOMATIC CHEMICALS (from chemical_system):
#   adrenaline, cortisol, noradrenaline, oxytocin, dopamine,
#   serotonin, testosterone, endorphin
#
# SATURATION LEVELS:
#   neutral   0–10
#   mild      10–25
#   active    25–50
#   intense   50–85
#   saturated 85–120
#   collapse  120+

import math

# ── SATURATION ────────────────────────────────────────────────────────────────

def get_saturation_label(dist: float) -> str:
    if dist <  10:  return "neutral"
    if dist <  25:  return "mild"
    if dist <  50:  return "active"
    if dist <  85:  return "intense"
    if dist < 120:  return "saturated"
    return "collapse"

def _lv(levels: dict, key: str) -> float:
    """Safe level getter."""
    return levels.get(key, 0.0)

# ── mental EMOTION MAPPER ─────────────────────────────────────────────────────

def get_emotion(cx: float, cy: float, mental_state_levels: dict = None) -> dict:
    """
    Maps mental (cx, cy) + mental_state_levels → emotional state.

    cx = (Er - Rr) / 2   positive=emotional, negative=rational
    cy = (P  - A)  / 2   positive=present,   negative=absent

    mental_state_levels: dict from MentalStateSystem.levels
                         keys: fear, loneliness, anguish, security, joy, calm
    """
    dist  = math.sqrt(cx**2 + cy**2)
    sat   = get_saturation_label(dist)
    lvs   = mental_state_levels or {}

    # quadrant
    if   cy >= 0 and cx >= 0: quadrant = "present-emotional"
    elif cy >= 0 and cx <  0: quadrant = "present-rational"
    elif cy <  0 and cx >= 0: quadrant = "absent-emotional"
    else:                      quadrant = "absent-rational"

    fear      = _lv(lvs, "fear")
    loneliness= _lv(lvs, "loneliness")
    anguish   = _lv(lvs, "anguish")
    security  = _lv(lvs, "security")
    joy       = _lv(lvs, "joy")
    calm      = _lv(lvs, "calm")

    emotion = "neutral"
    valence = "neutral"

    # ── ABSENT-EMOTIONAL ─────────────────────────────────────────────────────
    if quadrant == "absent-emotional":
        if fear > 2 and anguish > 2:
            if   sat == "collapse":   emotion, valence = "terror",          "negative"
            elif sat == "saturated":  emotion, valence = "panic",           "negative"
            elif sat == "intense":    emotion, valence = "fear",            "negative"
            elif sat == "active":     emotion, valence = "anxious",         "negative"
            else:                     emotion, valence = "apprehensive",    "negative"
        elif fear > 2 and anguish < 1:
            # high fear, low tension activation — more raw dread
            if   sat in ("collapse", "saturated"): emotion, valence = "dread",          "negative"
            elif sat == "intense":                  emotion, valence = "scared",         "negative"
            else:                                   emotion, valence = "uneasy",         "negative"
        elif loneliness > 2 and fear < 1:
            # loneliness dominant, no fear
            if   sat in ("collapse", "saturated"): emotion, valence = "despair",        "negative"
            elif sat == "intense":                  emotion, valence = "deep grief",     "negative"
            elif sat == "active":                   emotion, valence = "grief",          "negative"
            else:                                   emotion, valence = "sad",            "negative"
        elif loneliness > 1 and fear > 1:
            # loneliness + fear mix — isolated and threatened
            if   sat in ("collapse", "saturated"): emotion, valence = "breakdown",      "negative"
            elif sat == "intense":                  emotion, valence = "anguish",        "negative"
            elif sat == "active":                   emotion, valence = "distressed",     "negative"
            else:                                   emotion, valence = "worried",        "negative"
        elif anguish > 3 and fear < 1 and loneliness < 1:
            # pure anguish without clear source — diffuse tension
            if   sat in ("intense", "saturated", "collapse"): emotion, valence = "agitated",  "negative"
            else:                                               emotion, valence = "restless",  "negative"
        else:
            # generic absent-emotional with low tags
            if   sat == "active":  emotion, valence = "unsettled",  "negative"
            elif sat == "mild":    emotion, valence = "uneasy",     "negative"
            else:                  emotion, valence = "off",        "negative"

    # ── ABSENT-RATIONAL ──────────────────────────────────────────────────────
    elif quadrant == "absent-rational":
        if loneliness > 2 and fear < 1:
            if   sat in ("collapse", "saturated"): emotion, valence = "void",             "negative"
            elif sat == "intense":                  emotion, valence = "hollow",           "negative"
            elif sat == "active":                   emotion, valence = "numb",             "negative"
            else:                                   emotion, valence = "empty",            "negative"
        elif fear > 1 and anguish > 1:
            # fear processed rationally — dissociation
            if   sat in ("intense", "saturated", "collapse"): emotion, valence = "dissociated",    "negative"
            else:                                               emotion, valence = "withdrawn",      "negative"
        elif loneliness > 1 and fear > 1:
            if   sat in ("intense", "saturated", "collapse"): emotion, valence = "severe depression","negative"
            elif sat == "active":                               emotion, valence = "depressed",       "negative"
            else:                                               emotion, valence = "melancholic",     "negative"
        else:
            if   sat in ("intense", "saturated", "collapse"): emotion, valence = "shut down",   "negative"
            elif sat == "active":                               emotion, valence = "detached",    "negative"
            elif sat == "mild":                                 emotion, valence = "cold",        "mixed"
            else:                                               emotion, valence = "flat",        "negative"

    # ── PRESENT-EMOTIONAL ────────────────────────────────────────────────────
    elif quadrant == "present-emotional":
        if joy > 2 and security > 1:
            if   sat in ("saturated", "collapse"):  emotion, valence = "euphoric",        "mixed"
            elif sat == "intense":                   emotion, valence = "elated",          "positive"
            elif sat == "active":                    emotion, valence = "joyful",          "positive"
            else:                                    emotion, valence = "happy",           "positive"
        elif joy > 2 and security < 1:
            if   sat in ("intense", "saturated"):   emotion, valence = "excited",         "positive"
            else:                                    emotion, valence = "cheerful",        "positive"
        elif security > 2 and joy < 1:
            # warm presence, not excited
            if   sat == "intense":                  emotion, valence = "warm",            "positive"
            else:                                    emotion, valence = "content",         "positive"
        elif calm > 1 and joy > 1:
            emotion, valence = "at ease",           "positive"
        else:
            if   sat in ("intense", "saturated"):   emotion, valence = "overstimulated",  "mixed"
            elif sat == "active":                    emotion, valence = "engaged",         "positive"
            elif sat == "mild":                      emotion, valence = "pleasant",        "positive"
            else:                                    emotion, valence = "calm",            "positive"

    # ── PRESENT-RATIONAL ─────────────────────────────────────────────────────
    elif quadrant == "present-rational":
        if security > 2 and calm > 1:
            if   sat in ("intense", "saturated"):   emotion, valence = "resolute",        "positive"
            elif sat == "active":                    emotion, valence = "confident",       "positive"
            else:                                    emotion, valence = "secure",          "positive"
        elif calm > 2 and security < 1:
            if   sat == "active":                   emotion, valence = "focused",         "positive"
            else:                                    emotion, valence = "composed",        "positive"
        elif security > 1 and joy < 1 and calm < 1:
            emotion, valence = "grounded",          "positive"
        elif calm < 0.5 and security < 0.5:
            # present-rational with no positive tags — residual rational clarity
            if   sat in ("intense", "saturated"):   emotion, valence = "cold logic",      "mixed"
            elif sat == "active":                    emotion, valence = "analytical",      "neutral"
            else:                                    emotion, valence = "stable",          "positive"
        else:
            if   sat in ("intense", "saturated"):   emotion, valence = "determined",      "positive"
            elif sat == "active":                    emotion, valence = "clear",           "positive"
            elif sat == "mild":                      emotion, valence = "composed",        "positive"
            else:                                    emotion, valence = "stable",          "positive"

    return {
        "emotion":    emotion,
        "valence":    valence,
        "quadrant":   quadrant,
        "dist":       round(dist, 2),
        "saturation": sat,
        "tags":       {k: round(v, 2) for k, v in lvs.items() if v > 0.05},
    }


# ── SOMATIC STATE MAPPER ──────────────────────────────────────────────────────

def get_somatic_state(cx: float, cy: float, chemical_levels: dict = None) -> dict:
    """
    Maps somatic (cx, cy) + chemical_levels → physical state.

    cx = (Lv - Gv) / 2   positive=localized, negative=globalized
    cy = (V  - I)  / 2   positive=viable,    negative=inviable

    chemical_levels: dict from ChemicalSystem.levels
                     keys: adrenaline, cortisol, noradrenaline, oxytocin,
                           dopamine, serotonin, testosterone, endorphin
    """
    dist = math.sqrt(cx**2 + cy**2)
    sat  = get_saturation_label(dist)
    lvs  = chemical_levels or {}

    if   cy >= 0 and cx >= 0: quadrant = "viable-localized"
    elif cy >= 0 and cx <  0: quadrant = "viable-globalized"
    elif cy <  0 and cx >= 0: quadrant = "inviable-localized"
    else:                      quadrant = "inviable-globalized"

    adrena   = _lv(lvs, "adrenaline")
    cortisol = _lv(lvs, "cortisol")
    noradre  = _lv(lvs, "noradrenaline")
    oxito    = _lv(lvs, "oxytocin")
    dopamine = _lv(lvs, "dopamine")
    seroton  = _lv(lvs, "serotonin")
    testo    = _lv(lvs, "testosterone")
    endorf   = _lv(lvs, "endorphin")

    state   = "neutral"
    valence = "neutral"

    # ── VIABLE-LOCALIZED ─────────────────────────────────────────────────────
    if quadrant == "viable-localized":
        if adrena > 1 and noradre > 1 and cortisol > 1:
            if   sat in ("collapse", "saturated"):  state, valence = "high threat response",   "negative"
            elif sat == "intense":                   state, valence = "racing pulse, on guard", "mixed"
            elif sat == "active":                    state, valence = "alert, tense",           "mixed"
            else:                                    state, valence = "keyed up",               "mixed"
        elif adrena > 1 and noradre > 1 and cortisol < 1:
            # fight activation without chronic stress
            if   sat in ("intense", "saturated"):   state, valence = "fight ready",            "mixed"
            elif sat == "active":                    state, valence = "mobilized",              "mixed"
            else:                                    state, valence = "activated",              "neutral"
        elif testo > 1 and noradre > 1:
            # aggression-ready
            if   sat in ("intense", "saturated", "collapse"): state, valence = "aggressive posture", "negative"
            else:                                               state, valence = "assertive",          "mixed"
        elif cortisol > 2 and adrena < 1:
            # chronic stress without acute threat
            if   sat in ("intense", "saturated"):   state, valence = "chronic tension",        "negative"
            else:                                    state, valence = "stressed",               "negative"
        elif seroton > 1 or oxito > 1:
            if   sat == "active":                   state, valence = "relaxed alert",          "positive"
            else:                                    state, valence = "at ease",                "positive"
        elif endorf > 1:
            state, valence = "physical ease",       "positive"
        else:
            # No single chemical dominates here, but we're already inside
            # the viable quadrant (cy>=0). Since the system never decays
            # exactly to 0 by design, residual distance can sit in
            # "intense"/"saturated" for a long time after any event, even
            # with nothing actively driving it. High magnitude with no
            # clear marker, while still viable-localized, is ambiguous
            # rather than negative — "active" already grades to "mixed"
            # for real tension buildup, so this only softens the top end
            # (intense/saturated/collapse) from "negative" to "neutral".
            if   sat in ("intense", "saturated", "collapse"): state, valence = "elevated, unclear",  "neutral"
            elif sat == "active":                               state, valence = "tense",              "mixed"
            elif sat == "mild":                                 state, valence = "ready",              "positive"
            else:                                               state, valence = "stable",             "positive"

    # ── VIABLE-GLOBALIZED ────────────────────────────────────────────────────
    elif quadrant == "viable-globalized":
        if adrena > 2 and cortisol > 1:
            # high energy dispersed — flight
            if   sat in ("saturated", "collapse"):  state, valence = "fleeing",               "negative"
            elif sat == "intense":                   state, valence = "flight response",       "mixed"
            elif sat == "active":                    state, valence = "running",               "mixed"
            else:                                    state, valence = "moving away",           "neutral"
        elif dopamine > 1 and seroton > 1:
            if   sat in ("intense", "saturated"):   state, valence = "energized, open",       "positive"
            else:                                    state, valence = "expansive",             "positive"
        elif oxito > 1:
            if   sat == "active":                   state, valence = "warm, connected",       "positive"
            else:                                    state, valence = "open",                  "positive"
        elif adrena > 1 and noradre < 1:
            state, valence = "scattered energy",    "mixed"
        else:
            if   sat in ("saturated", "collapse"):  state, valence = "overwhelmed body",      "negative"
            elif sat == "intense":                   state, valence = "activated",             "mixed"
            elif sat == "active":                    state, valence = "energized",             "positive"
            else:                                    state, valence = "open",                  "positive"

    # ── INVIABLE-LOCALIZED ───────────────────────────────────────────────────
    elif quadrant == "inviable-localized":
        if adrena > 2 and noradre > 2:
            # acute threat to body — localized inviability
            if   sat == "collapse":                 state, valence = "physical collapse",     "negative"
            elif sat == "saturated":                 state, valence = "system overload",       "negative"
            elif sat == "intense":                   state, valence = "high threat, tachycardia", "negative"
            elif sat == "active":                    state, valence = "threat response",       "negative"
            else:                                    state, valence = "bracing",               "negative"
        elif cortisol > 3 and adrena < 1:
            # chronic threat, no acute response — frozen
            if   sat in ("intense", "saturated", "collapse"): state, valence = "frozen, cortisol spike", "negative"
            else:                                               state, valence = "locked up",              "negative"
        elif endorf > 1:
            # pain suppression active
            state, valence = "pain response suppressed", "mixed"
        else:
            if   sat == "collapse":                 state, valence = "paralyzed",             "negative"
            elif sat in ("intense", "saturated"):   state, valence = "stiff, restricted",     "negative"
            elif sat == "active":                   state, valence = "tense, guarded",        "negative"
            else:                                    state, valence = "stiff",                 "negative"

    # ── INVIABLE-GLOBALIZED ──────────────────────────────────────────────────
    elif quadrant == "inviable-globalized":
        if cortisol > 2 and adrena < 1 and noradre < 1:
            # burnout — exhausted without activation
            if   sat in ("intense", "saturated", "collapse"): state, valence = "burnout, exhausted",    "negative"
            else:                                               state, valence = "drained",               "negative"
        elif adrena > 1 and cortisol > 1:
            if   sat in ("saturated", "collapse"):  state, valence = "systemic failure",     "negative"
            elif sat == "intense":                   state, valence = "collapse imminent",    "negative"
            else:                                    state, valence = "failing",              "negative"
        elif endorf > 2:
            # strong endorphin — pain override in collapse
            state, valence = "pain override",       "mixed"
        else:
            if   sat == "collapse":                 state, valence = "total breakdown",      "negative"
            elif sat in ("intense", "saturated"):   state, valence = "collapse",             "negative"
            elif sat == "active":                   state, valence = "weakened",             "negative"
            else:                                    state, valence = "low energy",           "negative"

    return {
        "state":      state,
        "valence":    valence,
        "quadrant":   quadrant,
        "dist":       round(dist, 2),
        "saturation": sat,
        "chemicals":  {k: round(v, 2) for k, v in lvs.items() if v > 0.05},
    }
