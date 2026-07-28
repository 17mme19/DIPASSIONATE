"""Load and validate legacy and catalog-backed package records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


class PackageValidationError(ValueError):
    """Raised when one or more package records fail schema validation."""


def load_property_catalog(
    catalog_path: Path,
    schema_path: Path,
) -> dict[str, dict[str, Any]]:
    """Load a property catalog and return definitions indexed by property ID."""
    catalog_path = Path(catalog_path)
    catalog = _load_json_document(catalog_path, "property catalog")
    schema = load_schema(schema_path)
    errors = list(Draft202012Validator(schema).iter_errors(catalog))
    if errors:
        raise PackageValidationError(_format_validation_errors(catalog_path.name, errors))

    definitions = {
        item["property_id"]: item for item in catalog["properties"]
    }
    if len(definitions) != len(catalog["properties"]):
        raise PackageValidationError(
            f"{catalog_path.name}: duplicate property_id values are not allowed"
        )
    return definitions


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load and validate the schema document itself."""
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackageValidationError(
            f"Could not read schema '{schema_path}': {error}"
        ) from error

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise PackageValidationError(
            f"Schema '{schema_path}' is invalid: {error}"
        ) from error
    return schema


def load_structured_package_records(
    packages_directory: Path,
    package_schema_path: Path,
    catalog_path: Path,
    catalog_schema_path: Path,
) -> list[dict[str, Any]]:
    """Load structured records and validate their catalog references."""
    packages_directory = Path(packages_directory)
    schema = load_schema(package_schema_path)
    catalog = load_property_catalog(catalog_path, catalog_schema_path)
    validator = Draft202012Validator(schema)
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    package_paths = sorted(packages_directory.rglob("*.json"))
    if not package_paths:
        raise PackageValidationError(
            f"No package JSON files found in '{packages_directory}'."
        )

    for package_path in package_paths:
        try:
            record = _load_json_document(package_path, "package record")
        except PackageValidationError as error:
            errors.append(str(error))
            continue

        schema_errors = list(validator.iter_errors(record))
        if schema_errors:
            errors.extend(_format_validation_errors(package_path.name, schema_errors))
            continue

        errors.extend(
            _validate_catalog_references(package_path.name, record, catalog)
        )
        if not any(error.startswith(f"{package_path.name}:") for error in errors):
            records.append(record)

    if errors:
        raise PackageValidationError("\n".join(errors))
    return records


def load_package_records(
    packages_directory: Path,
    schema_path: Path,
) -> list[dict[str, Any]]:
    """Load and validate every JSON package record in a directory."""
    schema = load_schema(schema_path)
    validator = Draft202012Validator(schema)
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    package_paths = sorted(packages_directory.glob("*.json"))
    if not package_paths:
        raise PackageValidationError(
            f"No package JSON files found in '{packages_directory}'."
        )

    for package_path in package_paths:
        try:
            record = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"{package_path.name}: invalid JSON ({error})")
            continue

        validation_errors = sorted(
            validator.iter_errors(record),
            key=lambda error: list(error.absolute_path),
        )
        if validation_errors:
            for error in validation_errors:
                location = ".".join(str(item) for item in error.absolute_path)
                location = location or "<root>"
                errors.append(f"{package_path.name}: {location}: {error.message}")
            continue

        records.append(record)

    if errors:
        raise PackageValidationError("\n".join(errors))

    return records


def _load_json_document(path: Path, document_type: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackageValidationError(
            f"{path.name}: invalid {document_type} JSON ({error})"
        ) from error
    if not isinstance(document, dict):
        raise PackageValidationError(
            f"{path.name}: {document_type} must be a JSON object"
        )
    return document


def _format_validation_errors(filename: str, errors: list[Any]) -> list[str]:
    formatted: list[str] = []
    for error in sorted(errors, key=lambda item: list(item.absolute_path)):
        location = ".".join(str(item) for item in error.absolute_path)
        location = location or "<root>"
        formatted.append(f"{filename}: {location}: {error.message}")
    return formatted


def _validate_catalog_references(
    filename: str,
    record: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    package_family = record["package_family"]
    properties = record["properties"]

    for group_name, entries in properties.items():
        for index, entry in enumerate(entries):
            property_id = entry["property_id"]
            location = f"properties.{group_name}.{index}"
            definition = catalog.get(property_id)
            if definition is None:
                errors.append(
                    f"{filename}: {location}.property_id: "
                    f"unknown property_id '{property_id}'"
                )
                continue

            if definition["group"].lower() != group_name.lower():
                errors.append(
                    f"{filename}: {location}: property '{property_id}' belongs "
                    f"to catalog group '{definition['group']}'"
                )
            if package_family not in definition["applies_to"] and "ALL" not in definition[
                "applies_to"
            ]:
                errors.append(
                    f"{filename}: {location}: property '{property_id}' does not "
                    f"apply to package family '{package_family}'"
                )

            value = entry["value"]
            if value is not None and not _matches_data_type(
                value, definition["data_type"]
            ):
                errors.append(
                    f"{filename}: {location}.value: value for '{property_id}' "
                    f"must have type {definition['data_type']}"
                )

            classifications = entry["classifications"]
            value_statuses = [
                item["code"]
                for item in classifications
                if item["category"] == "value_status"
            ]
            if len(value_statuses) > 1:
                errors.append(
                    f"{filename}: {location}.classifications: at most one "
                    "value_status classification is allowed"
                )
            for classification in classifications:
                if classification["code"] not in definition[
                    "allowed_classifications"
                ]:
                    errors.append(
                        f"{filename}: {location}.classifications: classification "
                        f"'{classification['code']}' is not allowed for "
                        f"'{property_id}'"
                    )
    return errors


def _matches_data_type(value: Any, data_type: str) -> bool:
    if data_type == "TEXT":
        return isinstance(value, str)
    if data_type == "INTEGER":
        return isinstance(value, int) and not isinstance(value, bool)
    if data_type == "DECIMAL":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if data_type == "BOOLEAN":
        return isinstance(value, bool)
    if data_type == "TEXT_ARRAY":
        return (
            isinstance(value, list)
            and len(value) == len(set(value))
            and all(isinstance(item, str) and item for item in value)
        )
    return False
