import unittest
import importlib.util
import sys
from pathlib import Path


_MODULE_PATH = Path(__file__).resolve().parents[2] / "leadframe" / "IHPWirebond.py"
_SPEC = importlib.util.spec_from_file_location("ihp_wirebond", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
extract_ihp_wirebond_requirements = _MODULE.extract_ihp_wirebond_requirements


IHP_ROOT = Path(
    r"C:\Users\farze\OneDrive\Desktop\IC PACKAGE CONFIGRATOR"
) / "ihp-sg13g2-ams-chip-template-main" / "packaging"


@unittest.skipUnless(
    (IHP_ROOT / "config.yaml").exists()
    and (IHP_ROOT / "result.md").exists(),
    "IHP reference files are not available",
)
class IHPWirebondExtractionTests(unittest.TestCase):
    def test_extracts_summary_and_config_evidence(self) -> None:
        requirements = extract_ihp_wirebond_requirements(
            IHP_ROOT / "config.yaml",
            IHP_ROOT / "result.md",
        )

        self.assertEqual(requirements.design, "chip_top")
        self.assertEqual(requirements.package_name, "OP_QFN32_A4_FIT")
        self.assertEqual(requirements.wire_material, "gold")
        self.assertEqual(requirements.wire_diameter_um, 25.0)
        self.assertEqual(requirements.observed_wire_length_min_um, 1296.0)
        self.assertEqual(requirements.observed_wire_length_max_um, 1701.0)
        self.assertEqual(requirements.configured_max_wire_length_um, 3500.0)
        self.assertEqual(requirements.minimum_wire_gap_um, 72.0)
        self.assertEqual(requirements.configured_guard_spacing_um, 60.0)
        self.assertEqual(requirements.observed_max_lead_skew_deg, 3.5)
        self.assertEqual(requirements.configured_max_lead_skew_deg, 30.0)
        self.assertEqual(requirements.pad_pitch_um, 114.0)
        self.assertEqual(requirements.pad_opening_um, 65.8)
        self.assertEqual(requirements.die_orientation, "N")
        self.assertEqual(requirements.die_attach, "conductive epoxy")
        self.assertIsNone(requirements.loop_height_um)
        self.assertEqual(requirements.exposed_pad_downbond_count, 0)

    def test_extracts_all_unique_pin_mappings(self) -> None:
        requirements = extract_ihp_wirebond_requirements(
            IHP_ROOT / "config.yaml",
            IHP_ROOT / "result.md",
        )

        self.assertEqual(len(requirements.mappings), 32)
        self.assertEqual(set(requirements.mapping_by_pin), set(range(1, 33)))
        self.assertEqual(requirements.mapping_by_pin[1].die_pad, "clk_PAD")
        self.assertEqual(requirements.mapping_by_pin[32].die_pad, "output_PAD[0]")


if __name__ == "__main__":
    unittest.main()
