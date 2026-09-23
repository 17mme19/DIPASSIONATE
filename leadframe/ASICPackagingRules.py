"""Provenance-aware assembly rules from the ASIC prototype packaging guide."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class WireProcessRule:
    diameter_um: float
    minimum_pad_size_um: float
    minimum_pad_pitch_um: float
    maximum_length_mm: float
    maximum_angle_deg: float


@dataclass(frozen=True)
class ASICPackagingRules:
    source: str
    source_kind: str
    standard_wire_material: str
    standard_wire_diameter_um: float
    standard_wire_rule: WireProcessRule
    alternative_wire_rules: Tuple[WireProcessRule, ...]
    qfn_max_die_thickness_um: float
    manual_die_placement_tolerance_um: float
    minimum_die_metal_width_um: float
    minimum_corner_bond_clearance_um: float
    minimum_die_to_die_distance_um: float
    maximum_wires_per_package_finger: int
    maximum_wires_per_package: int
    wire_crossing_allowed: bool
    default_die_attach: str
    approved_conductive_die_attach: str
    approved_nonconductive_die_attach: str
    bonding_diagram_review_required: bool
    source_revision: str


ASIC_PROTOTYPE_2024_RULES = ASICPackagingRules(
    source="ASIC_Prototype_Packaging_Design_Rules_2024.pdf",
    source_kind="assembly-house-standard-service-guideline",
    standard_wire_material="gold",
    standard_wire_diameter_um=25.0,
    standard_wire_rule=WireProcessRule(25.0, 55.0, 65.0, 6.0, 45.0),
    alternative_wire_rules=(
        WireProcessRule(17.5, 40.0, 50.0, 4.5, 45.0),
        WireProcessRule(20.0, 46.0, 56.0, 5.0, 45.0),
        WireProcessRule(33.0, 70.0, 80.0, 7.0, 45.0),
    ),
    qfn_max_die_thickness_um=300.0,
    manual_die_placement_tolerance_um=100.0,
    minimum_die_metal_width_um=20.0,
    minimum_corner_bond_clearance_um=20.0,
    minimum_die_to_die_distance_um=250.0,
    maximum_wires_per_package_finger=2,
    maximum_wires_per_package=256,
    wire_crossing_allowed=False,
    default_die_attach="conductive epoxy",
    approved_conductive_die_attach="Epotek H20E",
    approved_nonconductive_die_attach="Epotek H70E",
    bonding_diagram_review_required=True,
    source_revision="2024 guide; standard-service Table 1 and Table 2",
)


def load_asic_prototype_rules(pdf_path: str | Path) -> ASICPackagingRules:
    """Return the typed rule set with the supplied PDF as its provenance."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"Packaging rules PDF not found: {path}")
    return ASICPackagingRules(
        **{
            **ASIC_PROTOTYPE_2024_RULES.__dict__,
            "source": str(path),
        }
    )
