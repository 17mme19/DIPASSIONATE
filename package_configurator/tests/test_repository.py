from __future__ import annotations

import unittest
from pathlib import Path

from package_configurator.repository import PackageRepository
from package_configurator.validation import load_package_records
from package_configurator.validation import load_structured_package_records


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    PROJECT_ROOT
    / "package_configurator"
    / "data"
    / "schema"
    / "package.schema.json"
)
PACKAGES_PATH = PROJECT_ROOT / "package_configurator" / "data" / "packages"


class PackageRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = PackageRepository(
            load_package_records(PACKAGES_PATH, SCHEMA_PATH)
        )

    def test_returns_all_records(self) -> None:
        self.assertEqual(len(self.repository.all()), 5)

    def test_filters_by_sub_family(self) -> None:
        records = self.repository.filter(package_sub_family="lfbga")

        self.assertEqual(
            {record["package_code"] for record in records},
            {"6RW", "AKB", "ALB", "ASB", "ATB"},
        )

    def test_filters_by_terminal_count(self) -> None:
        records = self.repository.filter(terminal_count=225)

        self.assertEqual([record["package_code"] for record in records], ["AKB"])

    def test_filters_by_maximum_body_size(self) -> None:
        records = self.repository.filter(max_length_mm=13.0, max_width_mm=13.0)

        self.assertEqual(
            {record["package_code"] for record in records},
            {"6RW", "AKB", "ALB"},
        )

    def test_filters_catalog_backed_record(self) -> None:
        structured_path = PROJECT_ROOT / "package_configurator" / "data" / "packages" / "structured"
        records = load_structured_package_records(
            structured_path,
            PROJECT_ROOT / "package_configurator" / "data" / "schema" / "package-record.schema.json",
            PROJECT_ROOT / "package_configurator" / "data" / "catalog" / "bga-properties.json",
            PROJECT_ROOT / "package_configurator" / "data" / "schema" / "property-catalog.schema.json",
        )

        matches = PackageRepository(records).filter(
            terminal_count=144,
            max_length_mm=10.0,
            max_width_mm=10.0,
        )

        self.assertEqual([record["package_code"] for record in matches], ["6RW"])

    def test_filters_with_value_status_preferences(self) -> None:
        records = self.repository.filter(
            max_height_mm=1.25,
            value_status_preferences={"overall_package_height": "MIN"},
        )

        self.assertEqual(
            {record["package_code"] for record in records},
            {"AKB", "ATB"},
        )

    def test_missing_dimension_value_does_not_match_dimension_filter(self) -> None:
        records = self.repository.filter(max_height_mm=1.4)

        self.assertEqual(
            {record["package_code"] for record in records},
            {"ATB"},
        )


if __name__ == "__main__":
    unittest.main()
