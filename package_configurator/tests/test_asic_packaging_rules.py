import importlib.util
import sys
import unittest
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[2] / "leadframe" / "ASICPackagingRules.py"
_SPEC = importlib.util.spec_from_file_location("asic_packaging_rules", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
ASIC_PROTOTYPE_2024_RULES = _MODULE.ASIC_PROTOTYPE_2024_RULES
load_asic_prototype_rules = _MODULE.load_asic_prototype_rules


RULES_PDF = (
    Path(r"C:\Users\farze\OneDrive\Desktop\IC PACKAGE CONFIGRATOR")
    / "Phase 1 Package property analyse and compare"
    / "Monolithic power"
    / "ASIC_Prototype_Packaging_Design_Rules_2024.pdf"
)


class ASICPackagingRulesTests(unittest.TestCase):
    def test_standard_25_um_rule_is_process_specific(self) -> None:
        rules = ASIC_PROTOTYPE_2024_RULES

        self.assertEqual(rules.source_kind, "assembly-house-standard-service-guideline")
        self.assertEqual(rules.standard_wire_material, "gold")
        self.assertEqual(rules.standard_wire_rule.minimum_pad_size_um, 55.0)
        self.assertEqual(rules.standard_wire_rule.minimum_pad_pitch_um, 65.0)
        self.assertEqual(rules.standard_wire_rule.maximum_length_mm, 6.0)
        self.assertEqual(rules.standard_wire_rule.maximum_angle_deg, 45.0)
        self.assertFalse(rules.wire_crossing_allowed)
        self.assertTrue(rules.bonding_diagram_review_required)

    def test_rules_cover_die_and_assembly_constraints(self) -> None:
        rules = ASIC_PROTOTYPE_2024_RULES

        self.assertEqual(rules.qfn_max_die_thickness_um, 300.0)
        self.assertEqual(rules.manual_die_placement_tolerance_um, 100.0)
        self.assertEqual(rules.minimum_die_metal_width_um, 20.0)
        self.assertEqual(rules.maximum_wires_per_package_finger, 2)
        self.assertEqual(rules.approved_conductive_die_attach, "Epotek H20E")

    @unittest.skipUnless(RULES_PDF.exists(), "ASIC packaging rules PDF unavailable")
    def test_source_path_is_preserved(self) -> None:
        rules = load_asic_prototype_rules(RULES_PDF)

        self.assertEqual(Path(rules.source), RULES_PDF)
        self.assertEqual(rules.source_revision, ASIC_PROTOTYPE_2024_RULES.source_revision)


if __name__ == "__main__":
    unittest.main()
