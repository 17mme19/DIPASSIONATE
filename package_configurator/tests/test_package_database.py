from __future__ import annotations

import unittest
import importlib.util
import os
import sys
from pathlib import Path


_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "leadframe" / "PackageDatabase.py"
)
_SPEC = importlib.util.spec_from_file_location("package_database", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
compatible_packages = _MODULE.compatible_packages
PackageRequirements = _MODULE.PackageRequirements
PackageSpec = _MODULE.PackageSpec
ALL_PACKAGES = _MODULE.ALL_PACKAGES
refresh_ihp_wirebond_metadata = _MODULE.refresh_ihp_wirebond_metadata


class PackageDatabaseCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requirements = {
            "die_length_mm": 1.6,
            "die_width_mm": 1.6,
            "pad_count": 32,
            "pad_arrangement": "peripheral_four_sided",
            "pads_per_side": {"left": 8, "right": 8, "top": 8, "bottom": 8},
            "pad_pitch_mm": 0.114,
            "max_pad_width_mm": 0.07,
            "max_pad_height_mm": 0.07,
        }

    def test_ihp_requirements_retain_qfn32(self) -> None:
        matches = compatible_packages(self.requirements, family="QFN")

        self.assertIn("QFN-32", {package.name for package in matches})
        self.assertIn("M-QFN32W.5", {package.name for package in matches})

    def test_incompatible_pin_count_is_rejected(self) -> None:
        requirements = {**self.requirements, "pad_count": 20}

        matches = compatible_packages(requirements, family="QFN")

        self.assertNotIn("QFN-32", {package.name for package in matches})

    def test_candidates_are_ranked_by_smallest_body_that_fits(self) -> None:
        matches = compatible_packages(self.requirements, family="QFN")

        self.assertEqual(matches[0].name, "QFN-32")

    def test_user_height_constraint_is_applied(self) -> None:
        matches = compatible_packages(
            self.requirements,
            family="QFN",
            constraints={"max_height_mm": 0.88},
        )

        self.assertEqual(
            [package.name for package in matches],
            [
                "HVQFN32-5X5-FSV9522",
                "HVQFN32-5X5-NXP-SOT617-1",
                "HVQFN32-5X5-SC16C550B",
                "M-QFN32W.5",
                "OP-QFN32-A4-FIT-IHP",
            ],
        )

    def test_user_paddle_constraint_is_applied(self) -> None:
        matches = compatible_packages(
            self.requirements,
            family="QFN",
            constraints={"require_die_paddle": True},
        )

        self.assertIn("QFN-32", {package.name for package in matches})

    def test_user_open_cavity_constraint_is_applied(self) -> None:
        matches = compatible_packages(
            self.requirements,
            family="QFN",
            constraints={"require_open_cavity": True},
        )

        self.assertEqual([package.name for package in matches], ["M-QFN32W.5"])

    def test_thermal_requirement_rejects_unknown_or_insufficient_capability(self) -> None:
        packages = [
            PackageSpec(
                "THERMAL-32", "QFN", "test", "validated thermal package",
                5.0, 5.0, 0.9, 32, 8, 8,
                max_power_w=2.0, theta_ja_c_per_w=20.0,
            ),
            PackageSpec(
                "UNKNOWN-32", "QFN", "test", "uncharacterized package",
                5.0, 5.0, 0.9, 32, 8, 8,
            ),
        ]
        matches = compatible_packages(
            self.requirements,
            packages=packages,
            constraints=PackageRequirements(
                max_power_w=1.5,
                max_theta_ja_c_per_w=25.0,
            ),
        )

        self.assertEqual([package.name for package in matches], ["THERMAL-32"])

    def test_rf_requirement_requires_frequency_capability_and_ground(self) -> None:
        packages = [
            PackageSpec(
                "RF-32", "QFN", "test", "validated RF package",
                5.0, 5.0, 0.9, 32, 8, 8,
                rf_capable=True, rf_max_frequency_ghz=20.0,
                exposed_ground=True,
            ),
            PackageSpec(
                "DIGITAL-32", "QFN", "test", "digital package",
                5.0, 5.0, 0.9, 32, 8, 8,
                rf_capable=True, rf_max_frequency_ghz=6.0,
            ),
        ]
        matches = compatible_packages(
            self.requirements,
            packages=packages,
            constraints=PackageRequirements(
                rf_frequency_ghz=13.5,
                require_rf_capable=True,
                require_exposed_ground=True,
            ),
        )

        self.assertEqual([package.name for package in matches], ["RF-32"])

    def test_fsv9522_variant_contains_only_validated_reference_data(self) -> None:
        variant = next(
            package for package in ALL_PACKAGES
            if package.name == "HVQFN32-5X5-FSV9522"
        )

        self.assertEqual(variant.body_height_mm, 0.85)
        self.assertEqual(variant.paddle_length_mm, 3.25)
        self.assertEqual(variant.paddle_width_mm, 3.25)
        self.assertEqual(variant.body_length_min_mm, 4.9)
        self.assertEqual(variant.body_length_max_mm, 5.1)
        self.assertEqual(variant.body_height_min_mm, 0.8)
        self.assertEqual(variant.body_height_max_mm, 0.85)
        self.assertEqual(variant.paddle_length_min_mm, 2.88)
        self.assertEqual(variant.paddle_length_max_mm, 3.25)
        self.assertEqual(variant.max_power_w, 0.20)
        self.assertEqual(variant.theta_ja_c_per_w, 40.0)
        self.assertEqual(variant.max_junction_temp_c, 100.0)
        self.assertEqual(variant.rf_application_frequency_ghz, 0.01356)
        self.assertIsNone(variant.rf_max_frequency_ghz)
        self.assertEqual(variant.source_revision, "Product data sheet Rev. 2.0, 17 Sep 2014")

    def test_fsv9522_variant_is_selected_for_rf_capability_without_max_frequency_claim(self) -> None:
        matches = compatible_packages(
            self.requirements,
            family="QFN",
            constraints=PackageRequirements(require_rf_capable=True),
        )

        self.assertEqual(
            [package.name for package in matches],
            ["HVQFN32-5X5-FSV9522"],
        )

    def test_nxp_sot6171_variant_contains_its_distinct_pcb_reference(self) -> None:
        variant = next(
            package for package in ALL_PACKAGES
            if package.name == "HVQFN32-5X5-NXP-SOT617-1"
        )

        self.assertEqual(variant.body_height_min_mm, 0.85)
        self.assertEqual(variant.body_height_max_mm, 1.0)
        self.assertEqual(variant.paddle_length_min_mm, 2.95)
        self.assertEqual(variant.paddle_length_max_mm, 3.25)
        self.assertEqual(variant.land_pattern_length_mm, 5.3)
        self.assertEqual(variant.land_pattern_width_mm, 5.3)
        self.assertEqual(variant.exposed_pad_land_length_mm, 3.1)
        self.assertEqual(variant.exposed_pad_land_width_mm, 3.1)
        self.assertEqual(variant.solder_paste_length_mm, 1.8)
        self.assertEqual(variant.solder_paste_width_mm, 1.8)
        self.assertEqual(variant.occupied_area_length_mm, 6.25)
        self.assertEqual(variant.occupied_area_width_mm, 6.25)
        self.assertEqual(variant.source_reference, "NXP SOT617-1 HVQFN32 Package Information")

    def test_sc16c550b_reference_keeps_device_limits_separate(self) -> None:
        variant = next(
            package for package in ALL_PACKAGES
            if package.name == "HVQFN32-5X5-SC16C550B"
        )

        self.assertEqual(variant.application_name, "SC16C550B UART")
        self.assertEqual(variant.application_supply_min_v, 2.5)
        self.assertEqual(variant.application_supply_max_v, 5.0)
        self.assertEqual(variant.application_ambient_min_c, -40.0)
        self.assertEqual(variant.application_ambient_max_c, 85.0)
        self.assertEqual(variant.application_power_limit_w, 0.50)
        self.assertEqual(variant.max_power_w, 0.50)
        self.assertTrue(variant.exposed_pad_grounded)
        self.assertTrue(variant.thermal_vias_recommended)
        self.assertEqual(variant.source_revision, "Rev. 6, 16 Dec 2014")

    def test_ihp_bondplan_variant_contains_wirebond_evidence(self) -> None:
        variant = next(
            package for package in ALL_PACKAGES
            if package.name == "OP-QFN32-A4-FIT-IHP"
        )

        self.assertEqual(variant.wire_material, "gold")
        self.assertEqual(variant.wire_diameter_um, 25.0)
        self.assertEqual(variant.max_wire_length_mm, 1.701)
        self.assertEqual(variant.min_wire_gap_um, 72.0)
        self.assertEqual(variant.max_lead_skew_deg, 3.5)
        self.assertFalse(variant.supports_exposed_pad_downbond)
        self.assertIn("Bondplan", variant.source_reference)

    def test_ihp_wirebond_constraints_select_only_validated_variant(self) -> None:
        matches = compatible_packages(
            self.requirements,
            family="QFN",
            constraints=PackageRequirements(
                wire_material="gold",
                wire_diameter_um=25.0,
                max_wire_length_mm=1.7,
                min_wire_gap_um=70.0,
                max_lead_skew_deg=4.0,
            ),
        )

        self.assertEqual([package.name for package in matches], ["OP-QFN32-A4-FIT-IHP"])

    def test_ihp_catalog_refreshes_from_source_files(self) -> None:
        packaging_dir = (
            Path(r"C:\Users\farze\OneDrive\Desktop\IC PACKAGE CONFIGRATOR")
            / "ihp-sg13g2-ams-chip-template-main"
            / "packaging"
        )
        previous = os.environ.get("DIPASSIONATE_IHP_PACKAGING")
        try:
            os.environ["DIPASSIONATE_IHP_PACKAGING"] = str(packaging_dir)
            refresh_ihp_wirebond_metadata()
            variant = next(
                package for package in ALL_PACKAGES
                if package.name == "OP-QFN32-A4-FIT-IHP"
            )
            self.assertIn(variant.wirebond_provenance, {"validated", "reference"})
            self.assertEqual(variant.source_revision, "chip_top / OP_QFN32_A4_FIT; 32 pin mappings")
            self.assertEqual(variant.max_wire_length_mm, 1.701)
        finally:
            if previous is None:
                os.environ.pop("DIPASSIONATE_IHP_PACKAGING", None)
            else:
                os.environ["DIPASSIONATE_IHP_PACKAGING"] = previous
            refresh_ihp_wirebond_metadata()

    def test_known_cavity_clearance_and_die_thickness_are_hard_constraints(self) -> None:
        package = PackageSpec(
            "RULED-32", "QFN", "test", "package with explicit process limits",
            5.0, 5.0, 0.9, 32, 8, 8,
            cavity_length_mm=3.0,
            cavity_width_mm=3.0,
            die_clearance_x_mm=0.9,
            die_clearance_y_mm=0.9,
            max_die_thickness_mm=0.3,
        )
        too_large = {**self.requirements, "die_length_mm": 2.2}
        too_thick = {**self.requirements, "die_thickness_mm": 0.3}

        self.assertEqual(
            compatible_packages(too_large, packages=[package]), []
        )
        self.assertEqual(
            compatible_packages(too_thick, packages=[package]), []
        )

    def test_generic_package_without_process_limits_is_not_rejected_for_unknown_fit(self) -> None:
        package = PackageSpec(
            "UNKNOWN-FIT-32", "QFN", "test", "package without cavity limits",
            5.0, 5.0, 0.9, 32, 8, 8,
        )

        matches = compatible_packages(self.requirements, packages=[package])

        self.assertEqual([item.name for item in matches], ["UNKNOWN-FIT-32"])
if __name__ == "__main__":
    unittest.main()
