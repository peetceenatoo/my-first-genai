from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.utils.schema_types import DocumentSchema, FIELD_TYPES


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_schema(schema: DocumentSchema) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not schema.name.strip():
        errors.append("Schema name is required.")

    if not schema.fields:
        warnings.append("Schema has no fields defined.")

    seen = set()
    for idx, field in enumerate(schema.fields, start=1):  # noqa: F402
        field_name = field.name.strip()
        if not field_name:
            errors.append(f"Field #{idx} is missing a name.")
            continue
        if field_name in seen:
            errors.append(f"Field '{field_name}' is duplicated.")
        seen.add(field_name)

        if field.field_type not in FIELD_TYPES:
            errors.append(
                f"Field '{field_name}' has invalid type '{field.field_type}'."
            )
        if field.field_type == "enum" and not field.enum_values:
            errors.append(f"Field '{field_name}' is enum but has no values.")

    return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)
