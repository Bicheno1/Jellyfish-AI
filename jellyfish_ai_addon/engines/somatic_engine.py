# engines/somatic_engine.py
# Somatic engine — physical world — range 0-4
# base = fortitude / first resistance — never changes
# current = accumulated state — the one that matters

from ..core.formulas import calculate_D, apply_input, get_quadrant, get_rhomboid_center, get_distance
from ..db.db_somatic import SOMATIC_KEYS, SOMATIC_BASE
import math

class SomaticEngine:
    def __init__(self):
        self.base     = dict(SOMATIC_BASE)   # fixed fortitude — first resistance
        self.current  = dict(SOMATIC_BASE)   # accumulated state
        self.internal = {k: 0.0 for k in SOMATIC_KEYS}
        self.external = dict(SOMATIC_BASE)

    def apply_external(self, input_values):
        # base dampens the input first
        base_input   = apply_input(self.base, input_values, SOMATIC_KEYS)
        # dampened input modifies current
        self.current  = apply_input(self.current, base_input, SOMATIC_KEYS)
        self.external = dict(self.current)

    def apply_internal(self, internal_values):
        self.current  = apply_input(self.current, internal_values, SOMATIC_KEYS)
        self.internal = dict(internal_values)

    def recalibrate(self, C):
        """Cross-recalibration — mental coherence influences somatic state.
        C is (cx, cy) of the mental center of mass.
        cy > 0 → present  → raises V, lowers I
        cy < 0 → absent   → lowers V, raises I
        """
        cx, cy = C
        influence = math.sqrt(cx**2 + cy**2) * 0.1
        sign = 1 if cy >= 0 else -1
        self.current["V"] = max(0.0, min(400.0, self.current["V"] + influence * sign))
        self.current["I"] = max(0.0, min(400.0, self.current["I"] - influence * sign))

    def current_state(self):
        return dict(self.current)

    def D(self):
        return calculate_D(self.current)

    def distance(self):
        return get_distance(self.current, SOMATIC_KEYS)

    def quadrant(self):
        return get_quadrant(self.current, SOMATIC_KEYS)

    def decay_toward_base(self, rate: float = 0.15):
        """
        Homeostatic decay — pushes current toward base each cycle.
        rate=0.15 → each cycle 15% of the difference is closed.
        This is the return mechanism that the internal motor represents.
        """
        for k in ["V", "I", "Lv", "Gv"]:
            diff = self.base[k] - self.current[k]
            self.current[k] += diff * rate
