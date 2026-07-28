from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from package_configurator.bga_generator import (
    BgaGeometryError,
    DEFAULT_BGA_COLUMN_LABELS,
    build_bga_model,
    get_bga_geometry,
    parse_depopulation_pattern,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRUCTURED_PATH = (
    PROJECT_ROOT
    / "package_configurator"
    / "data"
    / "packages"
    / "structured"
)


class BgaGeneratorTests(unittest.TestCase):
    def test_extracts_nominal_geometry_from_akb(self) -> None:
        record = self._record("microchip_lfbga_akb.json")

        geometry = get_bga_geometry(
            record,
            value_status_preferences={
                "overall_package_height": "NOM",
                "ball_height": "NOM",
                "ball_diameter": "NOM",
            },
        )

        self.assertEqual(geometry.columns, 15)
        self.assertEqual(geometry.rows, 15)
        self.assertEqual(geometry.length_mm, 13.0)
        self.assertEqual(geometry.ball_diameter_mm, 0.4)

    def test_6rw_requires_explicit_available_diameter_status(self) -> None:
        record = self._record("microchip_lfbga_6rw.json")

        with self.assertRaisesRegex(
            BgaGeometryError,
            r"choose a value status for ball_diameter",
        ):
            get_bga_geometry(record)

        minimum = get_bga_geometry(
            record,
            value_status_preferences={
                "overall_package_height": "MAX",
                "ball_height": "MIN",
                "ball_diameter": "MIN",
            },
        )
        maximum = get_bga_geometry(
            record,
            value_status_preferences={
                "overall_package_height": "MAX",
                "ball_height": "MAX",
                "ball_diameter": "MAX",
            },
        )

        self.assertEqual(minimum.ball_diameter_mm, 0.4)
        self.assertEqual(maximum.ball_diameter_mm, 0.5)

    def test_rejects_invalid_value_status(self) -> None:
        record = self._record("microchip_lfbga_akb.json")

        with self.assertRaisesRegex(BgaGeometryError, r"Invalid value status"):
            get_bga_geometry(
                record,
                value_status_preferences={"ball_diameter": "TYP"},
            )

    def test_applies_preferences_to_all_selectable_dimensions(self) -> None:
        record = self._record("microchip_lfbga_akb.json")

        geometry = get_bga_geometry(
            record,
            value_status_preferences={
                "overall_package_height": "MIN",
                "ball_height": "MAX",
                "ball_diameter": "MIN",
            },
        )

        self.assertEqual(geometry.height_mm, 1.24)
        self.assertEqual(geometry.ball_height_mm, 0.35)
        self.assertEqual(geometry.ball_diameter_mm, 0.35)

    def test_parses_depopulated_record_coordinates(self) -> None:
        record = self._record("microchip_lfbga_alb.json")

        coordinates = next(
            entry["value"]
            for entry in record["properties"]["interconnection"]
            if entry["property_id"] == "unpopulated_array_coordinates"
        )

        self.assertEqual(len(coordinates), 49)
        self.assertIn("E5", coordinates)
        self.assertIn("L11", coordinates)

    def test_parses_manufacturer_depopulation_notation(self) -> None:
        coordinates = parse_depopulation_pattern("5-11 X (E-H,J-L)")

        self.assertEqual(len(coordinates), 49)
        self.assertEqual(coordinates[0], "E5")
        self.assertEqual(coordinates[-1], "L11")

    def test_bga_column_labels_omit_reserved_letters(self) -> None:
        self.assertEqual(
            DEFAULT_BGA_COLUMN_LABELS[:17],
            ("A", "B", "C", "D", "E", "F", "G", "H",
             "J", "K", "L", "M", "N", "P", "R", "T", "U"),
        )

    def _record(self, filename: str) -> dict[str, object]:
        return copy.deepcopy(
            json.loads((STRUCTURED_PATH / filename).read_text(encoding="utf-8"))
        )


if __name__ == "__main__":
    unittest.main()
