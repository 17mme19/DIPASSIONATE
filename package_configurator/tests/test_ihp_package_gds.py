import importlib.util
import sys
import unittest
from pathlib import Path


try:
    import gdstk  # noqa: F401
except ImportError:
    gdstk = None


_MODULE_PATH = Path(__file__).resolve().parents[2] / "leadframe" / "IHPPackageGDS.py"
if gdstk:
    _SPEC = importlib.util.spec_from_file_location("ihp_package_gds", _MODULE_PATH)
    _MODULE = importlib.util.module_from_spec(_SPEC)
    assert _SPEC.loader is not None
    sys.modules[_SPEC.name] = _MODULE
    _SPEC.loader.exec_module(_MODULE)
    extract_ihp_package_geometry = _MODULE.extract_ihp_package_geometry
    validate_bond_mappings = _MODULE.validate_bond_mappings

    _WIREBOND_PATH = Path(__file__).resolve().parents[2] / "leadframe" / "IHPWirebond.py"
    _WIREBOND_SPEC = importlib.util.spec_from_file_location("ihp_wirebond_for_gds", _WIREBOND_PATH)
    _WIREBOND_MODULE = importlib.util.module_from_spec(_WIREBOND_SPEC)
    assert _WIREBOND_SPEC.loader is not None
    sys.modules[_WIREBOND_SPEC.name] = _WIREBOND_MODULE
    _WIREBOND_SPEC.loader.exec_module(_WIREBOND_MODULE)
    extract_ihp_wirebond_requirements = _WIREBOND_MODULE.extract_ihp_wirebond_requirements


PACKAGE_GDS = (
    Path(r"C:\Users\farze\OneDrive\Desktop\IC PACKAGE CONFIGRATOR")
    / "ihp-sg13g2-ams-chip-template-main"
    / "packaging"
    / "layout"
    / "OP_QFN32_A4_FIT.gds"
)
PACKAGING_DIR = PACKAGE_GDS.parents[1]


@unittest.skipUnless(gdstk and PACKAGE_GDS.exists(), "IHP GDS fixture unavailable")
class IHPPackageGDSTests(unittest.TestCase):
    def test_extracts_all_numbered_leads(self) -> None:
        geometry = extract_ihp_package_geometry(PACKAGE_GDS)

        self.assertEqual(len(geometry.leads), 32)
        self.assertEqual(geometry.pin_numbers, tuple(range(1, 33)))
        self.assertEqual(geometry.lead_layer, 210)
        self.assertEqual(geometry.pin_label_layer, 211)
        self.assertLess(geometry.footprint_bbox_um[0], 0)
        self.assertGreater(geometry.footprint_bbox_um[2], 0)

    def test_bondplan_mappings_match_leads_with_translation(self) -> None:
        geometry = extract_ihp_package_geometry(PACKAGE_GDS)
        requirements = extract_ihp_wirebond_requirements(
            PACKAGING_DIR / "config.yaml",
            PACKAGING_DIR / "result.md",
        )

        result = validate_bond_mappings(geometry, requirements.mappings)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.mismatched_pins, ())
        self.assertEqual(len(result.checks), 32)
        self.assertAlmostEqual(result.coordinate_offset_um[0], 4705.0, places=0)
        self.assertAlmostEqual(result.coordinate_offset_um[1], 9209.7, places=0)


if __name__ == "__main__":
    unittest.main()
