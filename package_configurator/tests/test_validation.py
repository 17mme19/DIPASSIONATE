from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from package_configurator.validation import (
    PackageValidationError,
    load_package_records,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    PROJECT_ROOT
    / "package_configurator"
    / "data"
    / "schema"
    / "package.schema.json"
)
PACKAGES_PATH = PROJECT_ROOT / "package_configurator" / "data" / "packages"


class PackageValidationTests(unittest.TestCase):
    def test_all_current_package_records_are_valid(self) -> None:
        records = load_package_records(PACKAGES_PATH, SCHEMA_PATH)

        self.assertEqual(
            {record["package_code"] for record in records},
            {"6RW", "AKB", "ALB", "ASB", "ATB"},
        )

    def test_invalid_json_is_reported_with_filename(self) -> None:
        with self._temporary_package_directory() as directory:
            directory = Path(directory)
            (directory / "broken.json").write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(
                PackageValidationError,
                r"broken\.json: invalid JSON",
            ):
                load_package_records(directory, SCHEMA_PATH)

    def test_missing_required_property_is_rejected(self) -> None:
        record = self._valid_record()
        del record["package_code"]

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"package_code.*required property",
            ):
                load_package_records(Path(directory), SCHEMA_PATH)

    def test_wrong_property_type_is_rejected(self) -> None:
        record = self._valid_record()
        record["terminal_count"] = "144"

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"terminal_count.*not of type",
            ):
                load_package_records(Path(directory), SCHEMA_PATH)

    def test_unknown_property_is_rejected(self) -> None:
        record = self._valid_record()
        record["unexpected_property"] = "not allowed"

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"unexpected_property.*unexpected",
            ):
                load_package_records(Path(directory), SCHEMA_PATH)

    def test_non_positive_dimension_is_rejected(self) -> None:
        record = self._valid_record()
        record["overall_length_nom_mm"] = -10.0

        with self._temporary_record(record) as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"overall_length_nom_mm.*minimum of 0",
            ):
                load_package_records(Path(directory), SCHEMA_PATH)

    def test_empty_package_directory_is_rejected(self) -> None:
        with self._temporary_package_directory() as directory:
            with self.assertRaisesRegex(
                PackageValidationError,
                r"No package JSON files found",
            ):
                load_package_records(Path(directory), SCHEMA_PATH)

    def _valid_record(self) -> dict[str, Any]:
        path = PACKAGES_PATH / "microchip_lfbga_6rw.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _temporary_package_directory(self):
        return tempfile.TemporaryDirectory()

    def _temporary_record(self, record: dict[str, Any]):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "test_record.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return directory


if __name__ == "__main__":
    unittest.main()
