# jelly_core.py — Jellyfish AI engine
#
# Implements the single-ping tick from the paper (sec 6.1): one somatic
# pass per 0.2s tick, no mental engine, no cross-recalibration — simpler
# than a back-and-forth ping-pong between layers.

from .engines.somatic_engine import SomaticEngine
from .systems.chemical_system import ChemicalSystem, MODES_BY_NAME
from .systems.vital_system import VitalSystem, NEED_INPUTS
from .layers.muscle_tone import compute_muscle_tone
from .db.db_somatic import TAG_VALUES_SOMATIC
from .motion import build_motion

TICK_SECONDS = 0.2

# Stimulus -> (category, tag) mapping. Reuses existing physiologically
# calibrated tags from db_somatic.py verbatim (paper sec 3.2) — no new
# tag vocabulary invented for the jellyfish.
STIMULUS_TAGS = {
    "danger": ("danger",  "hostile_contact"),
    "food":   ("benefit", "safe_contact"),
}


class JellyfishEngine:
    def __init__(self):
        self.somatic = SomaticEngine()
        self.chem = ChemicalSystem()
        self.vital = VitalSystem()
        self.last_motion = None

    # ── STATE SAVE/LOAD (for chaining baked events into one story) ─────────
    def get_state(self) -> dict:
        """Full internal state, JSON-serializable. See addon event log."""
        return {
            "somatic_current": dict(self.somatic.current),
            "chem_levels": dict(self.chem.levels),
            "chem_reserve": self.chem._reserve,
            "chem_cycle": self.chem._cycle,
            "chem_pending_rebounds": list(self.chem._pending_rebounds),
            "vital_somatic": {k: dict(v) for k, v in self.vital.somatic.items()},
            "vital_mental": {k: dict(v) for k, v in self.vital.mental.items()},
            "vital_health": dict(self.vital.health),
            "vital_sanity": dict(self.vital.sanity),
            "vital_tick": self.vital._tick,
        }

    def set_state(self, state: dict):
        """Restores a state previously returned by get_state()."""
        self.somatic.current = dict(state["somatic_current"])
        self.chem.levels = dict(state["chem_levels"])
        self.chem._reserve = state["chem_reserve"]
        self.chem._cycle = state["chem_cycle"]
        self.chem._pending_rebounds = list(state["chem_pending_rebounds"])
        for k, v in state["vital_somatic"].items():
            self.vital.somatic[k].update(v)
        for k, v in state["vital_mental"].items():
            self.vital.mental[k].update(v)
        self.vital.health.update(state["vital_health"])
        self.vital.sanity.update(state["vital_sanity"])
        self.vital._tick = state["vital_tick"]

    # ── PERCEPTION ENTRY POINT ──────────────────────────────────────────
    # An unidentified presence (not classifiable as food or danger) read as
    # a call to alert the group, not a personal fight/flight matter -- same
    # situation as ALLY_THREATENED: no existing tag is Gv-dominant under
    # "unclassifiable" either, so this is authored the same principled way.
    UNKNOWN_PRESENCE = {"V": 6.0, "I": 4.0, "Lv": 8.0, "Gv": 24.0}

    def stimulate(self, stimulus: str, intensity: float = 1.0):
        """
        stimulus  : "danger" | "food" | "unclassifiable" (an unidentified
                    object -- see paper sec 6.2, Unclassifiable x Gv = signal)
        intensity : 0.0-1.0, e.g. derived from proximity (closer = higher)
        """
        if stimulus == "unclassifiable":
            axis_push = {k: v * intensity for k, v in self.UNKNOWN_PRESENCE.items()}
            self.chem.release_from_axis_push("unclassifiable", axis_push)
            return
        if stimulus not in STIMULUS_TAGS:
            return
        category, tag_name = STIMULUS_TAGS[stimulus]
        raw = TAG_VALUES_SOMATIC[tag_name]
        axis_push = {k: v * intensity for k, v in raw.items()}
        dist = self.somatic.distance()
        self.chem.release_from_axis_push(category, axis_push, somatic_dist=dist)

    def feed(self, food_value: float = 1.0):
        """Call when contact radius with a food object is reached (paper sec
        3.3). food_value comes from that object's own jelly_food_value
        property (user-set, see __init__.py's Mark as Food operator) and
        scales the NEED_INPUTS['food'] deltas -- the jellyfish's own code
        never hardcodes how nutritious another object is."""
        self._feed_this_tick = True
        self._feed_value = food_value

    # ── CONSPECIFICS (paper sec 6.2: Gv/Rr column -- Cooperate/Protect) ─────
    # A healthy same-species neighbor reads as benefit/Gv -> cooperate
    # (schooling). If THIS creature is already injured and a predator is
    # also present, it reads as danger forced onto Gv -> protect: the
    # injured one interposes for the healthier ally instead of fleeing for
    # itself (paper: "the system distributes the threat response outward,
    # defending others... consistent with cooperative threat response").
    # A threat perceived as aimed at the GROUP (an ally in trouble) is
    # physiologically distinct from one aimed at ME (hostile_contact:
    # V2/I32/Lv36/Gv4, Lv/I-heavy). Neither gains (max 1.5x, can't overcome
    # a 9x raw gap) nor the rebound table (flee has none; attack's rebounds
    # to I, not Gv) can turn a personal-threat tag into this reading -- the
    # system has no existing tag whose natural composition is Gv-dominant
    # under danger. So this is authored the same way every tag in
    # db_somatic.py is: a small hand-set concept vector, Gv-dominant
    # because that's what "danger to the group" means, not a runtime
    # override. resolve_winning_axis then picks Gv organically, same as
    # any other stimulus.
    ALLY_THREATENED = {"V": 8.0, "I": 4.0, "Lv": 6.0, "Gv": 30.0}

    def sense_conspecific(self, mode: str, intensity: float = 1.0):
        """mode: 'cooperate' (default, healthy) or 'protect' (self-sacrifice)."""
        if mode == "protect":
            axis_push = {k: v * intensity for k, v in self.ALLY_THREATENED.items()}
            self.chem.release_from_axis_push("danger", axis_push)
        else:
            raw = TAG_VALUES_SOMATIC["oxytocin_a"]
            axis_push = {k: v * intensity for k, v in raw.items()}
            self.chem.release_from_axis_push("benefit", axis_push)

    def take_damage(self, amount: float):
        """Called by the addon when a predator's contact-radius is reached;
        `amount` comes from that object's own jelly_damage property (user-set,
        see __init__.py's Mark as Predator operator). Depletes the
        'structural' need (physical integrity) rather than hitting health
        directly -- health then falls through the normal needs-rollup
        (structural's health_weight=-1.5, see systems/vital_system.py),
        same mechanism every other need already uses."""
        self.vital._apply_delta("structural", -amount)

    # ── TICK ──────────────────────────────────────────────────────────
    def tick(self):
        feed_now = getattr(self, "_feed_this_tick", False)
        feed_value = getattr(self, "_feed_value", 1.0)
        self._feed_this_tick = False

        # 3-4: pushes
        chem_push = self.chem.get_somatic_push()
        vital_push, _mental_p = self.vital.get_internal_pressure()

        # 5: apply
        self.somatic.apply_internal(vital_push)
        self.somatic.apply_internal(chem_push)

        # 6: this tick's reading (before homeostatic pull-back)
        cx, cy = self.somatic.D()
        distance = self.somatic.distance()
        quadrant = self.somatic.quadrant()

        # dominant mode this tick (reported for logging only -- motion no
        # longer picks a single winner, it blends all active modes, see
        # motion.build_motion())
        dominant_name, dominant_level = None, 0.0
        for name, level in self.chem.levels.items():
            if level > dominant_level:
                dominant_name, dominant_level = name, level

        # 7: homeostatic decay (for next tick) + chemical decay/rebound
        intensity = min(1.0, distance / 200.0)
        decay_rate = max(0.05, 0.20 - intensity * 0.10)
        self.somatic.decay_toward_base(decay_rate)

        # 8: muscle tone (cfx=0, cf_dist=0 -- no mental engine, see paper sec 4.4)
        muscle = compute_muscle_tone(dfx=cx, df_dist=distance, cfx=0.0, cf_dist=0.0)

        # motion: weighted blend across every active mode (see motion.py)
        # -- read BEFORE chem.decay() so this tick's motion matches the
        # levels that actually produced this tick's chem_push/D reading.
        motion = build_motion(dict(self.chem.levels), muscle)

        self.chem.decay()

        # 9: vital tick -- food deltas scaled by the eaten object's own
        # jelly_food_value (default 1.0), applied directly rather than via
        # the fixed active_concepts=["food"] amounts. Eating also restores
        # some thirst (prey body water) -- aquatic creatures otherwise have
        # no way to drink; thirst still decays normally between meals.
        self.vital.tick()
        if feed_now:
            for need_name, delta in NEED_INPUTS["food"].items():
                self.vital._apply_delta(need_name, delta * feed_value)
            self.vital._apply_delta("thirst", 1.5 * feed_value)

        self.last_motion = motion
        health = round(self.vital.health["value"], 2)
        if health <= 0.0:
            # health depleted -> hard override to a surrender-like freeze,
            # regardless of what the mode blend computed this tick
            motion = dict(motion)
            motion.update(heading=0.0, speed=0.0, wave=0.0, contraction=0.0, frozen=True)

        return {
            "quadrant":      quadrant,
            "distance":      round(distance, 2),
            "dominant_mode": dominant_name,
            "dominant_level": round(dominant_level, 2),
            "muscle":        muscle,
            "motion":        motion,
            "hunger":        round(self.vital.somatic["hunger"]["value"], 2),
            "energy":        round(self.vital.somatic["energy"]["value"], 2),
            "structural":    round(self.vital.somatic["structural"]["value"], 2),
            "health":        health,
        }
