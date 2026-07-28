"""Search validated package records from the command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from package_configurator.properties import get_property_value
from package_configurator.repository import PackageRepository
from package_configurator.validation import (
    PackageValidationError,
    load_package_records,
    load_structured_package_records,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search Microchip semiconductor package records."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the package configurator project root.",
    )
    parser.add_argument("--family", help="Package family, for example BGA.")
    parser.add_argument("--sub-family", help="Package sub-family, for example LFBGA.")
    parser.add_argument("--terminal-count", type=int)
    parser.add_argument("--max-length-mm", type=float)
    parser.add_argument("--max-width-mm", type=float)
    parser.add_argument("--max-height-mm", type=float)
    parser.add_argument(
        "--structured",
        action="store_true",
        help="Search catalog-backed records instead of legacy records.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.structured:
            records = load_structured_package_records(
                args.project_root
                / "package_configurator"
                / "data"
                / "packages"
                / "structured",
                args.project_root
                / "package_configurator"
                / "data"
                / "schema"
                / "package-record.schema.json",
                args.project_root
                / "package_configurator"
                / "data"
                / "catalog"
                / "bga-properties.json",
                args.project_root
                / "package_configurator"
                / "data"
                / "schema"
                / "property-catalog.schema.json",
            )
        else:
            records = load_package_records(
                args.project_root
                / "package_configurator"
                / "data"
                / "packages",
                args.project_root
                / "package_configurator"
                / "data"
                / "schema"
                / "package.schema.json",
            )
    except PackageValidationError as error:
        print(f"Validation failed:\n{error}")
        return 1

    matches = PackageRepository(records).filter(
        package_family=args.family,
        package_sub_family=args.sub_family,
        terminal_count=args.terminal_count,
        max_length_mm=args.max_length_mm,
        max_width_mm=args.max_width_mm,
        max_height_mm=args.max_height_mm,
    )

    if not matches:
        print("No matching packages found.")
        return 0

    print("CODE  FAMILY  SUB-FAMILY  PINS  BODY (L x W x H mm)")
    for record in matches:
        length = _display_dimension(record, "overall_package_length")
        width = _display_dimension(record, "overall_package_width")
        height = _display_dimension(record, "overall_package_height")
        terminal_count = get_property_value(record, "terminal_count")
        print(
            f"{record['package_code']:<5} "
            f"{record['package_family']:<7} "
            f"{record['package_sub_family'] or '-':<11} "
            f"{terminal_count or '-':<5} "
            f"{length} x {width} x {height}"
        )
    print(f"\nMatches: {len(matches)}")
    return 0


def _display_dimension(record: dict[str, object], dimension: str) -> str:
    value = get_property_value(record, dimension)
    return "-" if value is None else f"{value:g}"


if __name__ == "__main__":
    raise SystemExit(main())
