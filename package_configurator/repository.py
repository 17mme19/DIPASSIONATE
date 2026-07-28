"""Query validated semiconductor package records."""

from __future__ import annotations

from typing import Any

from package_configurator.properties import get_property_value


class PackageRepository:
    """In-memory repository for validated package records."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = tuple(records)

    def all(self) -> list[dict[str, Any]]:
        """Return all records in source order."""
        return list(self._records)

    def filter(
        self,
        *,
        package_family: str | None = None,
        package_sub_family: str | None = None,
        terminal_count: int | None = None,
        max_length_mm: float | None = None,
        max_width_mm: float | None = None,
        max_height_mm: float | None = None,
        value_status_preferences: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return records matching all supplied criteria."""
        return [
            record
            for record in self._records
            if (
                package_family is None
                or record["package_family"].upper() == package_family.upper()
            )
            and (
                package_sub_family is None
                or (
                    record["package_sub_family"] is not None
                    and record["package_sub_family"].upper()
                    == package_sub_family.upper()
                )
            )
            and (
                terminal_count is None
                or get_property_value(
                    record,
                    "terminal_count",
                    value_status_preferences=value_status_preferences,
                )
                == terminal_count
            )
            and self._dimension_fits(
                record, "overall_package_length", max_length_mm,
                value_status_preferences,
            )
            and self._dimension_fits(
                record, "overall_package_width", max_width_mm,
                value_status_preferences,
            )
            and self._dimension_fits(
                record, "overall_package_height", max_height_mm,
                value_status_preferences,
            )
        ]

    @staticmethod
    def _dimension_fits(
        record: dict[str, Any],
        dimension: str,
        limit_mm: float | None,
        value_status_preferences: dict[str, str] | None = None,
    ) -> bool:
        if limit_mm is None:
            return True

        value = get_property_value(
            record,
            dimension,
            value_status_preferences=value_status_preferences,
        )
        return value is not None and value <= limit_mm
