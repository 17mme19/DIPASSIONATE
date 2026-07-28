"""Read package values from legacy or catalog-backed records."""

from __future__ import annotations

from typing import Any

VALID_VALUE_STATUSES = ("MIN", "NOM", "MAX")

_LEGACY_PROPERTY_NAMES = {
    "terminal_count": ("terminal_count",),
    "overall_package_length": (
        "overall_length_max_mm",
        "overall_length_nom_mm",
        "overall_length_min_mm",
    ),
    "overall_package_width": (
        "overall_width_max_mm",
        "overall_width_nom_mm",
        "overall_width_min_mm",
    ),
    "overall_package_height": (
        "overall_height_max_mm",
        "overall_height_nom_mm",
        "overall_height_min_mm",
    ),
}

_LEGACY_STATUS_FIELDS = {
    "overall_package_length": {
        "MIN": "overall_length_min_mm",
        "NOM": "overall_length_nom_mm",
        "MAX": "overall_length_max_mm",
    },
    "overall_package_width": {
        "MIN": "overall_width_min_mm",
        "NOM": "overall_width_nom_mm",
        "MAX": "overall_width_max_mm",
    },
    "overall_package_height": {
        "MIN": "overall_height_min_mm",
        "NOM": "overall_height_nom_mm",
        "MAX": "overall_height_max_mm",
    },
}


def get_property_value(
    record: dict[str, Any],
    property_id: str,
    *,
    classifications: tuple[str, ...] = ("MAX", "NOM", "MIN"),
    value_status_preferences: dict[str, str] | None = None,
) -> Any:
    """Return a package value from either record format."""
    legacy_names = _LEGACY_PROPERTY_NAMES.get(property_id)
    selected_status = None
    if value_status_preferences and property_id in value_status_preferences:
        selected_status = value_status_preferences[property_id].upper()
        if selected_status not in VALID_VALUE_STATUSES:
            raise ValueError(
                f"Invalid value status '{selected_status}' for '{property_id}'."
            )
        selected_field = _LEGACY_STATUS_FIELDS.get(property_id, {}).get(
            selected_status
        )
        if selected_field and selected_field in record:
            return record[selected_field]
    if property_id in record or (
        legacy_names is not None and any(name in record for name in legacy_names)
    ):
        return _first_non_null(
            record.get(name) for name in (legacy_names or (property_id,))
        )

    if value_status_preferences and property_id in value_status_preferences:
        classifications = (selected_status,)

    entries = _structured_entries(record, property_id)
    for entry in entries:
        entry_status = {
            item["code"]
            for item in entry.get("classifications", [])
            if item["category"] == "value_status"
        }
        if not entry_status and entry.get("value") is not None:
            return entry.get("value")

    for status in classifications:
        for entry in entries:
            entry_status = {
                item["code"]
                for item in entry.get("classifications", [])
                if item["category"] == "value_status"
            }
            if status in entry_status and entry.get("value") is not None:
                return entry.get("value")

    return None


def eligible_value_statuses(
    catalog: dict[str, Any],
) -> dict[str, tuple[str, ...]]:
    """Return MIN/NOM/MAX choices for filterable/generative properties."""
    eligible: dict[str, tuple[str, ...]] = {}
    for definition in catalog.get("properties", []):
        if not {"FILTERING", "GEOMETRY_GENERATION"}.intersection(
            definition.get("used_for", [])
        ):
            continue
        statuses = tuple(
            status
            for status in VALID_VALUE_STATUSES
            if status in definition.get("allowed_classifications", [])
        )
        if len(statuses) >= 2:
            eligible[definition["property_id"]] = statuses
    return eligible


def available_value_statuses(
    record: dict[str, Any],
    property_id: str,
) -> tuple[str, ...]:
    """Return non-null MIN/NOM/MAX statuses available in one package record."""
    legacy_fields = _LEGACY_STATUS_FIELDS.get(property_id, {})
    if legacy_fields and any(field in record for field in legacy_fields.values()):
        return tuple(
            status
            for status in VALID_VALUE_STATUSES
            if record.get(legacy_fields[status]) is not None
        )

    statuses: list[str] = []
    for entry in _structured_entries(record, property_id):
        if entry.get("value") is None:
            continue
        for classification in entry.get("classifications", []):
            code = classification.get("code")
            if (
                classification.get("category") == "value_status"
                and code in VALID_VALUE_STATUSES
                and code not in statuses
            ):
                statuses.append(code)
    return tuple(status for status in VALID_VALUE_STATUSES if status in statuses)


def _structured_entries(
    record: dict[str, Any],
    property_id: str,
) -> list[dict[str, Any]]:
    properties = record.get("properties")
    if not isinstance(properties, dict):
        return []
    return [
        entry
        for entries in properties.values()
        if isinstance(entries, list)
        for entry in entries
        if entry.get("property_id") == property_id
    ]


def _first_non_null(values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None
