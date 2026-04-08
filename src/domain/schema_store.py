from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from src.domain.models import DocumentSchema, SchemaField
from src.domain.validation import validate_schema, ValidationResult


class SchemaStore:
    def __init__(self, schemas_path: Path):
        self.schemas_path = schemas_path
        self.schemas_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.schemas_path.exists():
            self._write_payload(self.schemas_path, {})

    def list_schemas(self) -> list[DocumentSchema]:
        payload = self._load_payload(self.schemas_path)
        schemas = self._parse_payload_map(payload)
        return sorted(schemas.values(), key=lambda s: s.name.lower())

    def get_schema(self, name: str) -> DocumentSchema | None:
        payload = self._load_payload(self.schemas_path)
        if name in payload:
            return self._parse_payload_map({name: payload[name]}).get(name)
        return None

    def save_schema(
        self,
        schema: DocumentSchema,
        *,
        original_name: str | None = None,
    ) -> ValidationResult:
        validation = validate_schema(schema)
        if not validation.is_valid:
            return validation

        payload = self._load_payload(self.schemas_path)
        name_in_use = schema.name in payload
        is_rename = bool(original_name and original_name != schema.name)

        if original_name is None and name_in_use:
            return ValidationResult(
                is_valid=False,
                errors=[f"Schema '{schema.name}' already exists."],
                warnings=[],
            )

        if is_rename and name_in_use:
            return ValidationResult(
                is_valid=False,
                errors=[f"Schema '{schema.name}' already exists."],
                warnings=[],
            )

        if original_name and original_name != schema.name:
            payload.pop(original_name, None)

        payload[schema.name] = schema.to_dict()
        self._write_payload(self.schemas_path, payload)
        return validation

    def delete_schema(self, name: str) -> bool:
        payload = self._load_payload(self.schemas_path)
        if name in payload:
            payload.pop(name)
            self._write_payload(self.schemas_path, payload)
            return True
        return False

    def export_schema(self, schema: DocumentSchema) -> str:
        return json.dumps({schema.name: schema.to_dict()}, indent=2, ensure_ascii=False)

    @staticmethod
    def _load_payload(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            return {}
        return {}

    @staticmethod
    def _write_payload(path: Path, payload: dict) -> None:
        with path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2, ensure_ascii=False)

    def _parse_payload_map(self, payload: dict) -> dict[str, DocumentSchema]:
        schemas: dict[str, DocumentSchema] = {}
        for name, data in payload.items():
            if isinstance(data, list):
                fields = [self._parse_field(field) for field in data]
                schemas[name] = DocumentSchema(name=name, fields=fields)
                continue

            description = data.get("description", "")
            version = data.get("version", "v1")
            raw_fields = data.get("fields", [])
            fields = [self._parse_field(field) for field in raw_fields]
            schemas[name] = DocumentSchema(
                name=name,
                description=description,
                fields=fields,
                version=version,
            )
        return schemas

    @staticmethod
    def _parse_field(field: dict) -> SchemaField:
        raw_enum = field.get("enum", field.get("enum_values", [])) or []
        enum_values = [
            str(item).lower() if isinstance(item, bool) else str(item)
            for item in list(raw_enum)
        ]
        return SchemaField(
            name=str(field.get("name", "")).strip(),
            field_type=field.get("type", field.get("field_type", "string")),
            required=bool(field.get("required", False)),
            description=str(field.get("description", "")),
            example=str(field.get("example", "")),
            enum_values=enum_values,
        )


def schemas_to_table(schema: DocumentSchema) -> list[dict]:
    return [
        {
            "name": field.name,
            "type": field.field_type,
            "required": field.required,
            "description": field.description,
            "example": field.example,
            "enum": ", ".join(field.enum_values),
        }
        for field in schema.fields
    ]


def table_to_schema(
    name: str, description: str, rows: Iterable[dict]
) -> DocumentSchema:
    fields: list[SchemaField] = []
    for row in rows:
        enum_values = [
            item.strip() for item in str(row.get("enum", "")).split(",") if item.strip()
        ]
        fields.append(
            SchemaField(
                name=str(row.get("name", "")).strip(),
                field_type=row.get("type", "string"),
                required=bool(row.get("required", False)),
                description=str(row.get("description", "")).strip(),
                example=str(row.get("example", "")).strip(),
                enum_values=enum_values,
            )
        )
    return DocumentSchema(name=name, description=description, fields=fields)
