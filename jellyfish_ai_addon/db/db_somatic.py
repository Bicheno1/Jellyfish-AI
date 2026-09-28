# db/db_somatic.py — CCM v5
# Functional scale: 0–50 normal use · 50–100 intense · 100–150 extreme · 150–200 collapse
# SOMATIC_BASE neutral: V=8 I=2 Lv=10 Gv=6

SOMATIC_KEYS     = ["V", "I", "Lv", "Gv"]
SOMATIC_MAX      = 400
SOMATIC_APERTURE = 12

SOMATIC_BASE = {
    "V":  8,
    "I":  2,
    "Lv": 10,
    "Gv": 6
}

# ── TAG VALUES ─────────────────────────────────────────────────────────────────
# Each tag is a pure physiological response.
# Calibration reference:
#   darkness       → I=12 Lv=15  (insecurity moderate)
#   direct threat  → I=35 Lv=40  (immediate survival)
#   physical pain    → I=30 Lv=38  (maximum body threat)
#   loved person    → V=24 Gv=28  (attachment, protection)
#   food            → V=18 Lv=20  (restoration)

TAG_VALUES_SOMATIC = {

    # ── judgment of others (for "good/bad/mysterious person") ──
    # High Lv, low everywhere else -> lands the raw-push classifier
    # (core/response_matrix.py::primary_evaluator_category_from_axis_push)
    # on Lv/Er = "unclassifiable" (investigate), deliberately WITHOUT the
    # fear/threat tags "bad" uses -- "mysterious" isn't scary by itself,
    # just unresolved/ambiguous, so it shouldn't also read as danger.
    "curiosity_pull":     {"V":  4, "I":  4, "Lv": 30, "Gv":  4},

    # ── threat ────────────────────────────────────────────────────────────────
    "adrenaline":        {"V":  6, "I": 28, "Lv": 32, "Gv":  4},  # flight activation burst
    "muscle_tension":  {"V":  4, "I": 18, "Lv": 22, "Gv":  6},  # body on guard
    "paralysis":         {"V":  1, "I": 38, "Lv": 35, "Gv":  3},  # total freeze
    "flight_burst":             {"V": 32, "I": 10, "Lv": 38, "Gv":  5},  # escape movement
    "pain":              {"V":  0, "I": 30, "Lv": 38, "Gv":  2},  # acute physical pain
    "suffocation":       {"V":  2, "I": 34, "Lv": 28, "Gv":  8},  # shortness of breath

    # ── HOSTILE ENVIRONMENT ──────────────────────────────────────────────────
    "physical_darkness":{"V":  2, "I": 12, "Lv": 15, "Gv":  4},  # physical darkness
    "enclosed_space":   {"V":  3, "I": 14, "Lv": 16, "Gv":  5},  # mild claustrophobia
    "open_space":        {"V": 14, "I":  4, "Lv":  5, "Gv": 18},  # openness
    "cold":              {"V":  5, "I": 10, "Lv": 12, "Gv":  6},  # low temperature
    "noise":             {"V":  8, "I":  9, "Lv": 14, "Gv":  5},  # auditory stimulation
    "silence":           {"V":  2, "I": 10, "Lv":  8, "Gv":  6},  # absolute silence

    # ── PRESENCE / CONTACT ────────────────────────────────────────────────────
    "safe_contact":      {"V": 22, "I":  2, "Lv":  8, "Gv": 26},  # affectionate touch
    "hostile_contact":   {"V":  2, "I": 32, "Lv": 36, "Gv":  4},  # physical aggression
    "proximity":         {"V":  6, "I":  6, "Lv": 10, "Gv":  8},  # someone nearby
    "isolation":         {"V":  4, "I":  8, "Lv":  9, "Gv":  5},  # being alone

    # ── RECOVERY ──────────────────────────────────────────────────────────
    # Gv > Lv = diffuse/global calm. Lv > Gv = local/present stability.
    # Neutral state has Lv>Gv, so recovery should also have it.
    "breathing":         {"V": 16, "I":  2, "Lv": 18, "Gv":  5},  # deep breathing
    "physical_calm":     {"V": 18, "I":  1, "Lv": 20, "Gv":  4},  # body relaxation
    "ambient_light":     {"V": 16, "I":  2, "Lv": 18, "Gv":  6},  # soft light
    "firm_surface":      {"V": 14, "I":  2, "Lv": 16, "Gv":  5},  # stable ground

    # ── SOCIAL / CALM ─────────────────────────────────────────────────────────
    # Exact opposites of the ghost-in-a-dark-room tags
    "oxytocin_a":        {"V": 28, "I":  6, "Lv":  4, "Gv": 32},  # opposite of adrenaline
    "serotonin_a":       {"V": 10, "I":  2, "Lv":  5, "Gv": 38},  # opposite of flight_burst
    "muscle_calm_a":     {"V": 18, "I":  4, "Lv":  6, "Gv": 22},  # opposite of muscle_tension
    "safe_presence":     {"V": 38, "I":  1, "Lv":  3, "Gv": 35},  # opposite of paralysis
    "oxytocin":          {"V": 28, "I":  2, "Lv":  6, "Gv": 30},  # social bond
    "serotonin":         {"V": 24, "I":  2, "Lv":  8, "Gv": 26},  # diffuse wellbeing
    "muscle_calm":       {"V": 22, "I":  2, "Lv":  5, "Gv": 24},  # opposite of muscle_tension
    "open_space_safe":   {"V": 20, "I":  2, "Lv":  8, "Gv": 22},  # opposite of enclosed_space

    # ── CHEMICALS ─────────────────────────────────────────────────────────────
    "cortisol":          {"V":  3, "I": 22, "Lv": 20, "Gv":  6},  # sustained stress, inhibition
    "noradrenaline":     {"V":  8, "I": 24, "Lv": 28, "Gv":  5},  # acute alert, scanning
    "dopamine":          {"V": 26, "I":  4, "Lv": 10, "Gv": 28},  # motivation, reward
    "endorphins":        {"V": 30, "I":  2, "Lv":  8, "Gv": 32},  # physical wellbeing, euphoria

    # ── movement ────────────────────────────────────────────────────────────
    "fast_movement": {"V": 28, "I":  6, "Lv": 34, "Gv":  4},  # intense motor action
    "slow_movement":  {"V": 12, "I":  3, "Lv": 14, "Gv":  8},  # calm displacement
    "stillness":         {"V":  3, "I": 14, "Lv": 10, "Gv":  6},  # forced stillness

    # ── NEEDS ────────────────────────────────────────────────────────────
    "hunger_signal":     {"V":  3, "I": 16, "Lv": 18, "Gv":  4},  # food need
    "satiety":           {"V": 18, "I":  0, "Lv": 22, "Gv":  4},  # after eating
    "thirst_signal":     {"V":  2, "I": 14, "Lv": 16, "Gv":  3},  # water need
    "fatigue":           {"V":  2, "I": 12, "Lv":  8, "Gv":  6},  # physical tiredness
    "rest":              {"V": 14, "I":  1, "Lv": 16, "Gv":  4},  # body recovered

    # ── MUSIC / MELODY ──────────────────────────────────────────────────────
    "soft_melody":  {"V": 3, "I": 1, "Lv": 1, "Gv": 2},
    "melodic_phrase": {"V": 2, "I": 0, "Lv": 1, "Gv": 3},
    "calm_rhythm":  {"V": 3, "I": 0, "Lv": 2, "Gv": 2},
    # ── CONCEPT DIRECT VALUES ─────────────────────────────────────────────────
    # Each concept carries its own somatic signature — the baseline physiological
    # response that the concept itself produces, independent of its related nodes.
    # Used as the baseline value for a concept referencing itself.
    #
    # Calibration logic:
    #   ghost   → high I/Lv (existential threat, instant freeze response)
    #   dark    → moderate I/Lv (insecurity, vigilance, no immediate threat)
    #   room    → low baseline, slight enclosed pressure
    #   person  → moderate V/Gv (social bonding, attachment baseline)
    #   light   → moderate V/Lv (orientation, safety signal)

    "concept_ghost":   {"V":  2, "I": 30, "Lv": 28, "Gv":  4},  # presence of the impossible — freeze
    "concept_dark":    {"V":  4, "I": 14, "Lv": 16, "Gv":  5},  # reduced visibility — vigilance
    "concept_room":    {"V":  6, "I":  6, "Lv": 10, "Gv":  8},  # enclosed space — mild containment
    "concept_person":  {"V": 20, "I":  3, "Lv":  8, "Gv": 22},  # human presence — attachment signal
    "concept_light":   {"V": 16, "I":  2, "Lv": 18, "Gv":  6},  # visible light — orientation/safety

    # ── EXISTENTIAL ──────────────────────────────────────────────────────────
    "vital_threat":     {"V":  0, "I": 40, "Lv": 42, "Gv":  6},  # death risk
    "death_presence":   {"V":  1, "I": 24, "Lv": 18, "Gv": 26},  # corpse / nearby death
    "resource":          {"V": 20, "I":  0, "Lv": 24, "Gv":  4},  # resource control
}
