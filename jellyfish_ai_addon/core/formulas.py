# core/formulas.py — CCM v6
#
# EVALUATIVE FIELD ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════
#
# The system uses a 4-POINT RHOMBOID in the oriented plane.
# Each factor is an independent vertex — NOT a difference between pairs.
#
#   SOMATIC           mental
#   V  → (0,  +V)     P  → (0,  +P)    axis Y positive
#   I  → (0,  -I)     A  → (0,  -A)    axis Y negative
#   Lv → (+Lv, 0)     Er → (+Er, 0)    axis X positive
#   Gv → (-Gv, 0)     Rr → (-Rr, 0)    axis X negative
#
# SEMANTIC ORIENTATION — stored values are pure magnitudes.
# Polarity is intrinsic to the factor type, not the number.
#   V, Lv, P, Er  →  positive (+1)
#   I, Gv, A, Rr  →  negative (-1)
#
# THREE READING LEVELS OF THE FIELD:
#
#   D1 / C1 — DIRECT impact
#     Center of mass of the original rhomboid.
#     What is happening to the system right now — the raw hit.
#     cx = (Lv - Gv) / 2
#     cy = (V  - I)  / 2
#
#   D2 / C2 — RELATIONAL impact
#     Center of mass of the 4 midpoints.
#     Each midpoint is computed via 45° diagonal intersection between
#     two adjacent cardinal vertices scaled by R = |m1 - m2|.
#     Captures how the impact distributes across factor relationships.
#
#   Df / Cf — impact FINAL  ★ governs the system
#     Center of mass of all 8 points (4 cardinal vertices + 4 midpoints).
#     Emerges from geometry each cycle — not a fixed formula.
#
# SIGN OF THE CENTER OF MASS:
#   cy > 0 → viable / present
#   cy < 0 → inviable / absent
#   cx > 0 → local / emotional
#   cx < 0 → global / rational
#
# ═══════════════════════════════════════════════════════════════════════

SOMATIC_MAX = 400.0
MENTAL_MAX  = 200.0

# Intrinsic polarity of each factor
ORIENTATION = {
    "V":  1, "I": -1, "Lv":  1, "Gv": -1,   # somatic
    "P":  1, "A": -1, "Er":  1, "Rr": -1,    # mental
}

def get_max(keys):
    return SOMATIC_MAX if "V" in keys else MENTAL_MAX

def get_axis_keys(keys):
    """Returns (positive_Y, negative_Y, positive_X, negative_X)"""
    if "V" in keys:
        return "V", "I", "Lv", "Gv"
    else:
        return "P", "A", "Er", "Rr"

def get_rhomboid_center(state, keys):
    """
    Center of mass of the rhomboid — intersection of the two diagonals.

    Each factor is a vertex in the oriented plane:
        V  →  (  0,  +V )
        I  →  (  0,  -I )
        Lv →  ( +Lv,  0 )
        Gv →  ( -Gv,  0 )

    The center of mass is the midpoint of each diagonal:
        cx = ( +Lv + (-Gv) ) / 2
        cy = ( +V  + (-I)  ) / 2

    Mental maximum (0-200): cx/cy_max = 100
    Somatic maximum(0-400): cx/cy_max = 200

    Returns: (cx, cy)
    """
    pY, nY, pX, nX = get_axis_keys(keys)

    cx = ( oriented(pX, state[pX]) + oriented(nX, state[nX]) ) / 2.0
    cy = ( oriented(pY, state[pY]) + oriented(nY, state[nY]) ) / 2.0

    return cx, cy

def get_axes(state, keys):
    """
    Backward compatibility.
    Returns (y, x) of the rhomboid center of mass — scaled ×4
    to maintain the same magnitude as before (V-I, Lv-Gv).
    """
    cx, cy = get_rhomboid_center(state, keys)
    return cy * 4.0, cx * 4.0

def calculate_D(s):
    """
    D = center of mass of the somatic rhomboid.
    Returns (cx, cy) — the point in the oriented plane.
    Sign of cy: positive=viable, negative=inviable.
    Sign of cx: positive=local,  negative=global.
    """
    cx, cy = get_rhomboid_center(s, ["V", "I", "Lv", "Gv"])
    return cx, cy

def calculate_C(s):
    """
    C = center of mass of the mental rhomboid.
    Returns (cx, cy) — the point in the oriented plane.
    Sign of cy: positive=present, negative=absent.
    Sign of cx: positive=emotional, negative=rational.
    """
    cx, cy = get_rhomboid_center(s, ["P", "A", "Er", "Rr"])
    return cx, cy

def get_distance(state, keys):
    """
    Euclidean distance from center of mass to origin.
    Equivalent to system tension.
    """
    import math
    cx, cy = get_rhomboid_center(state, keys)
    return math.sqrt(cx**2 + cy**2)


def _intersect_diagonal(p1, p2):
    """
    Intersection of line p1→p2 with the 45° diagonal bisecting
    the quadrant of the pair.

    The diagonal through the origin bisecting each quadrant:
      Q1 (+,+) and Q3 (-,-) → y =  x
      Q2 (-,+) and Q4 (+,-) → y = -x

    If the line is parallel to the diagonal, returns the midpoint.
    """
    import math
    cx = (p1[0] + p2[0]) / 2
    cy = (p1[1] + p2[1]) / 2
    s = 1 if (cx >= 0) == (cy >= 0) else -1   # +1 → y=x,  -1 → y=-x

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    denom = dy - s * dx
    if abs(denom) < 1e-10:
        return (cx, cy)
    t = (s * p1[0] - p1[1]) / denom
    x = p1[0] + t * dx
    y = p1[1] + t * dy
    return (x, y)


def _scale_vertex(v, t):
    """Scale vertex v to magnitude t, preserving its direction."""
    import math
    mag = math.sqrt(v[0]**2 + v[1]**2)
    if mag < 1e-10:
        return v
    return (v[0] / mag * t, v[1] / mag * t)


def compute_midpoints(state, keys, coherent=True):
    """
    Computes the 4 midpoints of the 8-point figure.

    For each pair of adjacent cardinal vertices (N,E), (E,S), (S,O), (O,N):
      1. R = |m1 - m2|  (difference of magnitudes)
      2. Temporary points: t1 = m1 ± R,  t2 = m2 ± R  (+ coherent, - incoherent)
      3. Scale each vertex to its temporary magnitude
      4. Intersect the temporary line with the 45° diagonal of that quadrant
      5. The intersection point is the midpoint M

    Returns list of 4 midpoints: [M1(N,E), M2(E,S), M3(S,O), M4(O,N)]
    """
    pY, nY, pX, nX = get_axis_keys(keys)

    V  = state[pY]
    I  = state[nY]
    Lv = state[pX]
    Gv = state[nX]

    # Cardinal vertices in the oriented plane
    N = (0,    V)
    E = (Lv,   0)
    S = (0,   -I)
    O = (-Gv,  0)

    # Adjacent pairs: (vertex1, magnitude1, vertex2, magnitude2)
    adj = [
        (N, V,  E, Lv),
        (E, Lv, S, I),
        (S, I,  O, Gv),
        (O, Gv, N, V),
    ]

    midpoints = []
    for (v1, m1, v2, m2) in adj:
        R = abs(m1 - m2)
        if coherent:
            t1, t2 = m1 + R, m2 + R
        else:
            t1, t2 = abs(m1 - R), abs(m2 - R)

        p1_temp = _scale_vertex(v1, t1)
        p2_temp = _scale_vertex(v2, t2)

        M = _intersect_diagonal(p1_temp, p2_temp)
        midpoints.append(M)

    return midpoints


def calculate_d2(state, keys):
    """
    D2 / C2 — Relational centroid: center of mass of the 4 midpoints.

    Coherence is determined by the sign of D1's cy:
      cy > 0 → coherent  (viable / present)
      cy < 0 → incoherent
    """
    cx1, cy1 = get_rhomboid_center(state, keys)
    coherent  = cy1 >= 0
    midpoints = compute_midpoints(state, keys, coherent=coherent)
    cx2 = sum(m[0] for m in midpoints) / 4
    cy2 = sum(m[1] for m in midpoints) / 4
    return cx2, cy2


def calculate_df(state, keys):
    """
    Df / Cf — Coherence centroid: center of mass of all 8 points.

    4 cardinal vertices + 4 midpoints.
    This is the governing state of the system each cycle.
    Emerges from geometry — not a fixed formula.
    """
    pY, nY, pX, nX = get_axis_keys(keys)
    V  = state[pY]
    I  = state[nY]
    Lv = state[pX]
    Gv = state[nX]

    # Cardinal vertices
    N = (0,    V)
    E = (Lv,   0)
    S = (0,   -I)
    O = (-Gv,  0)

    # Midpoints
    cx1, cy1   = get_rhomboid_center(state, keys)
    coherent   = cy1 >= 0
    midpoints  = compute_midpoints(state, keys, coherent=coherent)

    all8 = [N, E, S, O] + midpoints
    cx = sum(p[0] for p in all8) / 8
    cy = sum(p[1] for p in all8) / 8
    return cx, cy

def get_sign(x):
    return 1 if x >= 0 else -1

def get_quadrant(state, keys):
    """
    The quadrant is determined by the position of the rhomboid center of mass.
    cy > 0 → viable/present     cy < 0 → inviable/absent
    cx > 0 → local/emotional    cx < 0 → global/rational
    """
    cx, cy = get_rhomboid_center(state, keys)
    if "V" in keys:
        if   cy >= 0 and cx >= 0: return "viable-localized"
        elif cy >= 0 and cx <  0: return "viable-globalized"
        elif cy <  0 and cx >= 0: return "inviable-localized"
        else:                      return "inviable-globalized"
    else:
        if   cy >= 0 and cx >= 0: return "present-emotional"
        elif cy >= 0 and cx <  0: return "present-rational"
        elif cy <  0 and cx >= 0: return "absent-emotional"
        else:                      return "absent-rational"

def oriented(factor, magnitude):
    """
    Converts a stored magnitude to its oriented value.
    Polarity comes from the factor type, not the number.

        oriented("I", 36)  →  -36
        oriented("V", 8)   →   +8
    """
    return magnitude * ORIENTATION[factor]


def magnitude(factor, oriented_value):
    """
    Converts an oriented value back to magnitude (always >= 0).
    Used to store the result while maintaining system convention.
    """
    return abs(oriented_value)


def apply_input(current_state, input_values, keys):
    """
    Vector interference with semantic orientation.

    Stored values are pure MAGNITUDES. Each factor has
    intrinsic polarity (ORIENTATION). Before operating they are converted
    to oriented values — then combined — then returned as magnitudes.

    Flow:
      1. current_oriented[k] = current[k] * ORIENTATION[k]
      2. input_oriented[k]   = input[k]   * ORIENTATION[k]
      3. result_oriented[k]  = current_oriented[k] + input_oriented[k]
         (negative polarity is preserved — inviability remains inviability)
      4. result[k] = abs(result_oriented[k])  → magnitude back

    Example:
      current I=2  →  oriented = -2
      input   I=36 →  oriented = -36
      result       →  -2 + (-36) = -38  →  magnitude 38
      NOT: -2 - (-36) = 34   ← that would be classic scalar algebra, incorrect in CCM
    """
    MAX = get_max(keys)
    result = {}
    for k in keys:
        cur_oriented = oriented(k, current_state.get(k, 0.0))
        inp_oriented = oriented(k, input_values.get(k, 0.0))
        combined     = cur_oriented + inp_oriented
        result[k]    = max(0.0, min(MAX, magnitude(k, combined)))
    return result
