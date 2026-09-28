# tension.py — reused as-is from output/phrase_builder's sibling
# output/output_layer.py::get_tension_somatic(). Pure arithmetic, no
# language/lexicon dependency, so it is kept verbatim rather than
# reinvented for the motion system (see Jellyfish AI paper §5.3).

def get_tension_somatic(distance: float) -> str:
    """
    Somatic state by distance to center.
    Scale 0-400 per variable -> theoretical maximum distance ~566.
      low        0-40
      medium    40-100
      high     100-180
      critical 180+
    """
    if distance < 40:
        return "low"
    elif distance < 100:
        return "medium"
    elif distance < 180:
        return "high"
    else:
        return "critical"
