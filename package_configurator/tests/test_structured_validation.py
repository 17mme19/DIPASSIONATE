from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from package_configurator.validation import (
    PackageValidationError,
    load_structured_package_records,
)
from package_configurator.properties import eligible_value_statuses


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SCHEMA_PATH = (
    PROJECT_ROOT
    / "package_configurator"
    / "data"
    / "schema"
    / "package-record.schema.json"
)
CATALOG_SCHEMA_PATH = (
    PROJECT_ROOT
    / "package_configurator"
    / "data"
    / "schema"
    / "property-catalog.schema.json"
)
CATALOG_PATH = (
    PROJECT_ROOT
    / "package_configurator"
    / "data"
    / "catalog"
    / "bga-properties.json"
)
STRUCTURED_RECORD_PATH = (
    PROJECT_ROOT
    / "package_configurator"
    / "data"
    / "packages"
    / "structured"
    / "microchip_lfbga_6rw.json"
)


class StructuredValidationTests(unittest.TestCase):
    def test_structured_record_and_catalog_are_valid(self) -> None:
        records = load_structured_package_records(
            STRUCTURED_RECORD_PATH.parent,
            PACKAGE_SCHEMA_PATH,
            CATALOG_PATH,
            CATALOG_SCHEMA_PATH,
        )

        self.assertEqual(
            {record["package_code"] for record in records},
            {"6RW", "AKB", "ALB", "ASB", "ATB"},
        )

    def test_catalog_exposes_eligible_value_status_choices(self) -> None:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

        eligible = eligible_value_statuses(catalog)

        self.assertEqual(eligible["ball_diameter"], ("MIN", "NOM", "MAX"))
        self.assertEqual(
            eligible["overall_package_height"],
            ("MIN", "NOM", "MAX"),
        )
        self.assertNotIn("ball_pitch", eligible)

    def test_unknown_property_id_is_rejected(self) -> None:
        record = self._record()
        record["properties"]["interconnection"][0]["property_id"] = "unknown"

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"unknown property_id 'unknown'",
            ):
                self._load(directory)

    def test_wrong_catalog_value_type_is_rejected(self) -> None:
        record = self._record()
        record["properties"]["interconnection"][0]["value"] = "144"

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"must have type INTEGER",
            ):
                self._load(directory)

    def test_disallowed_classification_is_rejected(self) -> None:
        record = self._record()
        record["properties"]["interconnection"][0]["classifications"] = [
            {"code": "MAX", "category": "value_status"}
        ]

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"classification 'MAX' is not allowed for 'terminal_count'",
            ):
                self._load(directory)

    def test_multiple_value_statuses_are_rejected(self) -> None:
        record = self._record()
        record["properties"]["interconnection"][0]["classifications"] = [
            {"code": "NOM", "category": "value_status"},
            {"code": "MAX", "category": "value_status"},
        ]

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"at most one value_status classification",
            ):
                self._load(directory)

    def _record(self) -> dict[str, Any]:
        return copy.deepcopy(
            json.loads(STRUCTURED_RECORD_PATH.read_text(encoding="utf-8"))
        )

    def _load(self, directory: Path) -> list[dict[str, Any]]:
        return load_structured_package_records(
            directory,
            PACKAGE_SCHEMA_PATH,
            CATALOG_PATH,
            CATALOG_SCHEMA_PATH,
        )

    def _temporary_record(self, record: dict[str, Any]):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "test_record.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return directory


if __name__ == "__main__":
    unittest.main()
