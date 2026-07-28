"""Validate all package records in the configurator data directory."""

from __future__ import annotations

import argparse
from pathlib import Path

from package_configurator.validation import (
    PackageValidationError,
    load_package_records,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Microchip package JSON records."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the package configurator project root.",
    )
    args = parser.parse_args()

    schema_path = args.project_root / "package_configurator" / "data" / "schema" / "package.schema.json"
    packages_directory = args.project_root / "package_configurator" / "data" / "packages"

    try:
        records = load_package_records(packages_directory, schema_path)
    except PackageValidationError as error:
        print(f"Validation failed:\n{error}")
        return 1

    print(f"Validation passed: {len(records)} package records")
    for record in records:
        print(f"- {record['package_code']} ({record['package_sub_family']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
