# systems/vital_system.py — CCM v4
#
# VitalSystem — statistical needs, RPG-style.
#
# TREE STRUCTURE:
#   HEALTH (somatic root, own value 0-10, slow decay)
#     └── roots: hunger, thirst, energy, temperature, commodity
#   SANITY (mental root, own value 0-10, slow decay)
#     └── roots: company, purpose, security, structure
#
#   Roots push Health/Sanity up or down each tick.
#   Health/Sanity have more weight than roots individually.
#   Health high → somatic engine more resilient (pressure dampened)
#   Sanity high → mental engine more resilient (pressure dampened)
#
# COMMODITY — physical comfort from posture/proximity.
#   Updated externally by proprioception/proximity systems.
#   Bad posture (bone near range limit) → commodity drops.
#   External contact properties (warm clothing, cold object) → commodity changes.

import math

# ── SOMATIC ROOTS ─────────────────────────────────────────────────────────────

SOMATIC_NEEDS = {
    "hunger": {
        "value": 8.0, "decay_per_tick": 0.04,
        "comfort_threshold": 6.0, "critical_threshold": 2.0,
        "somatic_push":{"I": 160, "Lv": 80, "V": 0, "Gv": 0},
        "mental_push":{"A": 30, "Er": 40, "P": 0, "Rr": 0},
        "health_weight": -0.30,   # how much this root pulls health down when low
        "description": "Physical hunger",
    },
    "thirst": {
        "value": 9.0, "decay_per_tick": 0.06,
        "comfort_threshold": 6.0, "critical_threshold": 2.0,
        "somatic_push":{"I": 140, "Gv": 100, "V": 0, "Lv": 0},
        "mental_push":{"A": 20, "Rr": 30, "P": 0, "Er": 0},
        "health_weight": -0.25,
        "description": "Hydration",
    },
    "energy": {
        "value": 8.5, "decay_per_tick": 0.03,
        "comfort_threshold": 5.0, "critical_threshold": 1.5,
        "somatic_push":{"I": 180, "Gv": 120, "V": 0, "Lv": 0},
        "mental_push":{"A": 50, "Rr": 40, "P": 0, "Er": 0},
        "health_weight": -0.25,
        "description": "Physical energy / fatigue",
    },
    "temperature": {
        "value": 7.0, "decay_per_tick": 0.0,  # frozen for now, per user request
        "comfort_threshold": 5.0, "critical_threshold": 1.5,
        "somatic_push":{"I": 120, "Lv": 140, "V": 0, "Gv": 0},
        "mental_push":{"A": 30, "Er": 50, "P": 0, "Rr": 0},
        "health_weight": -0.10,
        "description": "Body temperature regulation",
    },
    "structural": {
        "value": 10.0, "decay_per_tick": 0.0,  # only drops from take_damage(), not on its own
        "comfort_threshold": 5.0, "critical_threshold": 2.0,
        "somatic_push":{"I": 80, "Lv": 100, "V": 0, "Gv": 0},
        "mental_push":{"A": 20, "Er": 30, "P": 0, "Rr": 0},
        "health_weight": -1.5,  # physical damage tracker -- was "commodity" (comfort, -0.10); strengthened since this now represents injury, not comfort
        "description": "Structural integrity -- physical damage/wear from predator contact",
    },
}

# ── mental ROOTS ──────────────────────────────────────────────────────────────

MENTAL_NEEDS = {
    "company": {
        "value": 7.5, "decay_per_tick": 0.025,
        "comfort_threshold": 5.0, "critical_threshold": 1.5,
        "mental_push":{"A": 80, "Rr": 50, "P": 0, "Er": 0},
        "somatic_push":{"I": 40, "Gv": 60, "V": 0, "Lv": 0},
        "sanity_weight": -0.25,
        "description": "Social connection",
    },
    "purpose": {
        "value": 7.0, "decay_per_tick": 0.015,
        "comfort_threshold": 4.0, "critical_threshold": 1.0,
        "mental_push":{"A": 70, "Rr": 60, "P": 0, "Er": 0},
        "somatic_push":{"I": 40, "Gv": 80, "V": 0, "Lv": 0},
        "sanity_weight": -0.30,
        "description": "Sense of meaning",
    },
    "security": {
        "value": 8.0, "decay_per_tick": 0.02,
        "comfort_threshold": 5.0, "critical_threshold": 2.0,
        "mental_push":{"A": 60, "Er": 70, "P": 0, "Rr": 0},
        "somatic_push":{"I": 60, "Lv": 100, "V": 0, "Gv": 0},
        "sanity_weight": -0.30,
        "description": "Felt safety",
    },
    "structure": {
        "value": 7.0, "decay_per_tick": 0.018,
        "comfort_threshold": 4.5, "critical_threshold": 1.5,
        "mental_push":{"A": 50, "Rr": 70, "P": 0, "Er": 0},
        "somatic_push":{"I": 30, "Gv": 60, "V": 0, "Lv": 0},
        "sanity_weight": -0.15,
        "description": "Daily routine and predictability",
    },
}

# ── HEALTH & SANITY TREES ─────────────────────────────────────────────────────

HEALTH_TREE = {
    "value":          9.0,   # starts healthy
    "decay_per_tick": 0.005, # very slow natural decay
    "min": 0.0, "max": 10.0,
}

SANITY_TREE = {
    "value":          9.0,
    "decay_per_tick": 0.004,
    "min": 0.0, "max": 10.0,
}

# ── CROSS-NEED LINKS ──────────────────────────────────────────────────────────

NEED_LINKS = [
    ("hunger",      "energy",      1.8),
    ("energy",      "hunger",      1.4),
    ("thirst",      "temperature", 1.5),
    ("temperature", "energy",      1.6),
    ("company",     "purpose",     1.3),
    ("security",    "structure",   1.2),
    # health low → all somatic roots decay slightly faster
    # sanity low → all mental roots decay slightly faster
    # (handled in _decay_roots)
]

# ── INPUT MAP ─────────────────────────────────────────────────────────────────

NEED_INPUTS = {
    "food":        {"hunger": +3.0, "energy": +1.0, "health": +0.1},
    "eat":         {"hunger": +2.5},
    "water":       {"thirst": +3.5},
    "drink":       {"thirst": +2.5},
    "sleep":       {"energy": +4.0, "hunger": +0.5, "health": +0.2, "sanity": +0.1},
    "rest":        {"energy": +2.0, "structural": +1.0},
    "run":         {"energy": -1.5, "hunger": -0.5, "thirst": -0.8, "structural": -0.5},
    "walk":        {"energy": -0.4, "thirst": -0.2},
    "fight":       {"energy": -2.0, "thirst": -1.0, "temperature": -1.5, "health": -0.3},
    "cold":        {"temperature": -2.0, "energy": -0.5, "structural": -1.0},
    "heat":        {"temperature": +2.5, "thirst": -0.8, "structural": -0.5},
    "fire":        {"temperature": +2.0},
    "warm":        {"temperature": +1.0, "structural": +0.5},
    "pain":        {"health": -0.4, "structural": -2.0},
    "hurt":        {"health": -0.3, "structural": -1.5},
    "heal":        {"health": +1.0},
    "medicine":    {"health": +0.8},
    "friend":      {"company": +2.5, "security": +1.0, "sanity": +0.1},
    "talk":        {"company": +1.5},
    "alone":       {"company": -1.5},
    "danger":      {"security": -2.5, "structure": -1.0, "sanity": -0.2},
    "safe":        {"security": +2.0, "sanity": +0.1},
    "home":        {"security": +1.5, "structure": +2.0, "structural": +1.0},
    "work":        {"purpose": +2.0, "structure": +1.5},
    "routine":     {"structure": +2.5, "sanity": +0.1},
    "chaos":       {"structure": -2.0, "security": -1.0, "sanity": -0.2},
    "goal":        {"purpose": +2.5},
    "lost":        {"purpose": -2.0, "security": -1.5, "sanity": -0.3},
    "calm":        {"sanity": +0.1, "structural": +0.5},
    "relax":       {"sanity": +0.15, "structural": +1.5, "energy": +0.5},
    # structural — posture/contact inputs (also set externally by proximity system)
    "comfortable": {"structural": +2.0},
    "uncomfortable":{"structural": -2.0},
    "soft":        {"structural": +1.0},
    "hard":        {"structural": -0.5},
    "tight":       {"structural": -1.0},
}

# ── vital SYSTEM ──────────────────────────────────────────────────────────────

class VitalSystem:
    def __init__(self):
        self.somatic = {k: dict(v) for k, v in SOMATIC_NEEDS.items()}
        self.mental  = {k: dict(v) for k, v in MENTAL_NEEDS.items()}
        self.health  = dict(HEALTH_TREE)
        self.sanity  = dict(SANITY_TREE)
        self._tick   = 0

    # ── TICK ──────────────────────────────────────────────────────────────────

    def tick(self, active_concepts=None):
        self._tick += 1
        if active_concepts:
            self._apply_inputs(active_concepts)
        amplifiers = self._compute_link_amplifiers()
        self._decay_roots(amplifiers)
        self._update_trees()

    # ── INPUTS ────────────────────────────────────────────────────────────────

    def _apply_inputs(self, concepts):
        for c in concepts:
            if c in NEED_INPUTS:
                for need_name, delta in NEED_INPUTS[c].items():
                    self._apply_delta(need_name, delta)

    def _apply_delta(self, name, delta):
        if name == "health":
            self.health["value"] = max(0.0, min(10.0, self.health["value"] + delta))
        elif name == "sanity":
            self.sanity["value"] = max(0.0, min(10.0, self.sanity["value"] + delta))
        elif name in self.somatic:
            self.somatic[name]["value"] = max(0.0, min(10.0, self.somatic[name]["value"] + delta))
        elif name in self.mental:
            self.mental[name]["value"]  = max(0.0, min(10.0, self.mental[name]["value"]  + delta))

    # ── COMMODITY — external update from proximity/proprioception ─────────────

    def set_commodity(self, value):
        """Called externally by ProximitySystem or ProprioceptionSystem."""
        self.somatic["structural"]["value"] = max(0.0, min(10.0, value))

    def push_commodity(self, delta):
        """Incremental update — positive = more comfortable, negative = less."""
        self._apply_delta("structural", delta)

    # ── CROSS-NEED AMPLIFIERS ─────────────────────────────────────────────────

    def _compute_link_amplifiers(self):
        amps = {}
        all_needs = {**self.somatic, **self.mental}
        for source, target, amp in NEED_LINKS:
            sn = all_needs.get(source)
            if sn and sn["value"] < sn["comfort_threshold"]:
                depth = 1.0 - (sn["value"] / sn["comfort_threshold"])
                amps[target] = amps.get(target, 1.0) + (amp - 1.0) * depth
        return amps

    # ── DECAY ─────────────────────────────────────────────────────────────────

    def _decay_roots(self, amplifiers):
        # Health/Sanity low → roots decay slightly faster
        health_amp = 1.0 + max(0.0, (5.0 - self.health["value"]) / 10.0) * 0.3
        sanity_amp = 1.0 + max(0.0, (5.0 - self.sanity["value"]) / 10.0) * 0.3

        for name, need in self.somatic.items():
            amp = amplifiers.get(name, 1.0) * health_amp
            need["value"] = max(0.0, need["value"] - need["decay_per_tick"] * amp)

        for name, need in self.mental.items():
            amp = amplifiers.get(name, 1.0) * sanity_amp
            need["value"] = max(0.0, need["value"] - need["decay_per_tick"] * amp)

    def _update_trees(self):
        """
        Roots push Health and Sanity up or down.
        Each root contributes proportionally to how far below comfort it is.
        Health/Sanity have own slow decay on top.
        """
        # ── HEALTH ────────────────────────────────────────────
        health_delta = -self.health["decay_per_tick"]
        for name, need in self.somatic.items():
            weight = need.get("health_weight", 0.0)
            pressure = self._compute_pressure(name, need)
            # pressure 0 = satisfied (no pull), 1 = critical (full pull)
            health_delta += weight * pressure  # weight is negative → pulls down

        self.health["value"] = max(0.0, min(10.0, self.health["value"] + health_delta))

        # ── SANITY ────────────────────────────────────────────
        sanity_delta = -self.sanity["decay_per_tick"]
        for name, need in self.mental.items():
            weight = need.get("sanity_weight", 0.0)
            pressure = self._compute_pressure(name, need)
            sanity_delta += weight * pressure

        self.sanity["value"] = max(0.0, min(10.0, self.sanity["value"] + sanity_delta))

    # ── PRESSURE ──────────────────────────────────────────────────────────────

    def _compute_pressure(self, name, need):
        val     = need["value"]
        comfort = need["comfort_threshold"]
        crit    = need["critical_threshold"]

        if name == "temperature":
            mid  = 6.5
            dist = abs(val - mid)
            zone = 1.5
            if dist <= zone:
                return 0.0
            return min(1.0, (dist - zone) / (mid - zone))

        if val >= comfort:
            return 0.0
        if val <= crit:
            return 1.0
        return (comfort - val) / (comfort - crit)

    # ── RESILIENCE — dampens engine pressure when health/sanity high ──────────

    def get_resilience(self):
        """
        Returns (somatic_resilience, mental_resilience) in range 0.0–1.0.
        1.0 = full health/sanity → engine pressure halved.
        0.0 = critical → no dampening.
        Used to scale vital pressure before applying it to the engines.
        """
        sr = max(0.0, min(1.0, self.health["value"] / 10.0))
        mr = max(0.0, min(1.0, self.sanity["value"] / 10.0))
        return sr, mr

    # ── INTERNAL PRESSURE → ENGINES ───────────────────────────────────────────

    def get_internal_pressure(self):
        somatic_p = {"V": 0.0, "I": 0.0, "Lv": 0.0, "Gv": 0.0}
        mental_p  = {"P": 0.0, "A": 0.0, "Er": 0.0, "Rr": 0.0}

        sr, mr = self.get_resilience()
        # Resilience dampens pressure: high health = roots push less hard
        somatic_damp = 1.0 - (sr * 0.5)  # 0.5 at full health, 1.0 at zero health
        mental_damp  = 1.0 - (mr * 0.5)

        for name, need in self.somatic.items():
            p = self._compute_pressure(name, need)
            if p <= 0.0:
                continue
            for axis, w in need["somatic_push"].items():
                somatic_p[axis] += p * w * somatic_damp
            for axis, w in need["mental_push"].items():
                mental_p[axis]  += p * w * 0.3 * somatic_damp

        for name, need in self.mental.items():
            p = self._compute_pressure(name, need)
            if p <= 0.0:
                continue
            for axis, w in need["mental_push"].items():
                mental_p[axis]  += p * w * mental_damp
            for axis, w in need["somatic_push"].items():
                somatic_p[axis] += p * w * 0.3 * mental_damp

        somatic_p = {k: min(v, 1.2) for k, v in somatic_p.items()}
        mental_p  = {k: min(v, 0.8) for k, v in mental_p.items()}
        return somatic_p, mental_p

    # ── STATUS ────────────────────────────────────────────────────────────────

    def status(self):
        out = {
            "health": {
                "value":      round(self.health["value"], 2),
                "state":      self._tree_label(self.health["value"]),
            },
            # self.sanity is the value the engine itself reads and updates
            # (get_resilience / _decay_roots / get_internal_pressure), so
            # status() reports that value directly rather than a separate
            # copy that could drift out of sync with it.
            "sanity": {
                "value": round(self.sanity["value"], 2),
                "state": self._tree_label(self.sanity["value"]),
            },
            "somatic": {},
            "mental":  {},
        }
        for name, need in self.somatic.items():
            p = self._compute_pressure(name, need)
            out["somatic"][name] = {
                "value":    round(need["value"], 2),
                "pressure": round(p, 3),
                "state":    self._need_label(need["value"], need["comfort_threshold"],
                                             need["critical_threshold"]),
            }
        for name, need in self.mental.items():
            p = self._compute_pressure(name, need)
            out["mental"][name] = {
                "value":    round(need["value"], 2),
                "pressure": round(p, 3),
                "state":    self._need_label(need["value"], need["comfort_threshold"],
                                             need["critical_threshold"]),
            }
        return out

    def _tree_label(self, val):
        if val >= 8.0:   return "healthy"
        elif val >= 5.0: return "moderate"
        elif val >= 2.0: return "low"
        else:            return "critical"

    def _need_label(self, val, comfort, crit):
        if val >= comfort:      return "satisfied"
        elif val >= crit + 1.5: return "low"
        elif val >= crit:       return "critical"
        else:                   return "depleted"

    def summary_line(self):
        parts = [f"health={self.health['value']:.1f}", f"sanity={self.sanity['value']:.1f}"]
        for n, nd in {**self.somatic, **self.mental}.items():
            parts.append(f"{n}={nd['value']:.1f}")
        return " | ".join(parts)
