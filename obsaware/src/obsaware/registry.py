"""One lookup for every mutation operator Paper 3 uses: Paper 3's invisible-channel operators first, then
cart's registries (primary, scale-up, Phase C), which are imported unchanged."""
from __future__ import annotations


def get_any_operator(family: str):
    from obsaware.mutations import MUTATION_OPERATORS_P3
    if family in MUTATION_OPERATORS_P3:
        return MUTATION_OPERATORS_P3[family]
    from cart.events.mutations import MUTATION_OPERATORS
    if family in MUTATION_OPERATORS:
        return MUTATION_OPERATORS[family]
    from cart.events.mutations_scaleup import get_operator_scaleup
    try:
        return get_operator_scaleup(family)
    except KeyError:
        pass
    from cart.events import mutations_phase_c as pc
    reg = getattr(pc, "MUTATION_OPERATORS_PHASE_C", None)
    if reg and family in reg:
        return reg[family]
    raise KeyError(family)
