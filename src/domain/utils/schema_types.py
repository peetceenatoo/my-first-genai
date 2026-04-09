from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FIELD_TYPES = {
    "string",
    "number",
    "integer",
    "boolean",
    "date",
    "enum",
    "object",
    "array",
}


@dataclass
class SchemaField:
    name: str
    field_type: str = "string"
    required: bool = False
    description: str = ""
    example: str = ""
    enum_values: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "type": self.field_type,
            "required": self.required,
            "description": self.description,
            "example": self.example,
        }
        if self.enum_values:
            payload["enum"] = self.enum_values
        return payload


@dataclass
class DocumentSchema:
    name: str
    description: str = ""
    fields: list[SchemaField] = field(default_factory=list)
    version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "version": self.version,
            "fields": [field.to_dict() for field in self.fields],
        }
