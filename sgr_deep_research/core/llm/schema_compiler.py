from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Sequence,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
    Literal,
)

from pydantic import BaseModel

from sgr_deep_research.core.llm.base import SchemaTooComplexError
from sgr_deep_research.core.llm.utils import rename_key


@dataclass(slots=True)
class CompiledShape:
    schema: Dict[str, Any]
    transform: Callable[[Any], Any]
    discriminator_value: str | None = None


@dataclass(slots=True)
class CompiledSchema:
    name: str
    schema: Dict[str, Any]
    transform: Callable[[Mapping[str, Any]], Mapping[str, Any]]


class SchemaCompiler:
    """Compile Pydantic models into simplified JSON schemas for Mistral."""

    def __init__(self, *, allow_additional_properties: bool = False) -> None:
        self.allow_additional_properties = allow_additional_properties

    def compile(self, model: Type[BaseModel]) -> CompiledSchema:
        shape = self._compile_model(model)
        return CompiledSchema(name=model.__name__, schema=shape.schema, transform=shape.transform)

    # Internal helpers -------------------------------------------------

    def _compile_model(self, model: Type[BaseModel]) -> CompiledShape:
        properties: Dict[str, Any] = {}
        required: List[str] = []
        field_transforms: Dict[str, Callable[[Any], Any]] = {}
        renames: Dict[str, str] = {}
        discriminator_value: str | None = None

        for field_name, field_info in model.model_fields.items():
            json_name = field_info.alias or field_name
            annotation = field_info.annotation

            if field_name.endswith("_discriminator"):
                json_name = "kind"
                renames[json_name] = field_name
                disc_default = field_info.default
                if disc_default is None:
                    raise SchemaTooComplexError(
                        f"Field '{field_name}' must have default discriminator value"
                    )
                discriminator_value = str(disc_default)
                properties[json_name] = {
                    "type": "string",
                    "enum": [discriminator_value],
                    "description": field_info.description or "",
                }
                required.append(json_name)
                continue

            field_schema, transform = self._compile_annotation(annotation)
            if transform is not None:
                field_transforms[json_name] = transform

            properties[json_name] = field_schema
            if field_info.is_required():
                required.append(json_name)
            if json_name != field_name:
                renames[json_name] = field_name

        schema: Dict[str, Any] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": self.allow_additional_properties,
        }
        if required:
            schema["required"] = required

        def transform_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
            if not isinstance(payload, Mapping):
                raise TypeError("Structured response must be a mapping")
            converted: Dict[str, Any] = {}
            for json_name, value in payload.items():
                target_name = renames.get(json_name, json_name)
                processor = field_transforms.get(json_name)
                if processor is not None:
                    value = processor(value)
                converted[target_name] = value
            return converted

        return CompiledShape(schema=schema, transform=transform_payload, discriminator_value=discriminator_value)

    def _compile_annotation(self, annotation: Any) -> tuple[Dict[str, Any], Callable[[Any], Any] | None]:
        origin = get_origin(annotation)
        if origin is Annotated:
            annotation = get_args(annotation)[0]
            return self._compile_annotation(annotation)
        if origin is None:
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                nested = self._compile_model(annotation)

                def transform(value: Any) -> Mapping[str, Any]:
                    if isinstance(value, BaseModel):
                        value = value.model_dump()
                    if not isinstance(value, Mapping):
                        raise TypeError("Expected mapping for nested model")
                    return nested.transform(value)

                schema = nested.schema.copy()
                return schema, transform

            if isinstance(annotation, type) and issubclass(annotation, Enum):
                return {"type": "string", "enum": [member.value for member in annotation]}, None

            if annotation in {str, int, float, bool}:
                json_type = {
                    str: "string",
                    int: "integer",
                    float: "number",
                    bool: "boolean",
                }[annotation]
                return {"type": json_type}, None

            raise SchemaTooComplexError(f"Unsupported field annotation: {annotation!r}")

        if origin in (list, List, Sequence):
            (item_type,) = get_args(annotation)
            item_schema, item_transform = self._compile_annotation(item_type)

            def transform_list(value: Any) -> List[Any]:
                if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                    raise TypeError("Expected list for sequence field")
                if item_transform is None:
                    return list(value)
                return [item_transform(item) for item in value]

            return {"type": "array", "items": item_schema}, transform_list

        if origin in (dict, Dict, Mapping):
            raise SchemaTooComplexError("Mapping fields are not supported in structured outputs")

        if origin is Literal:
            raw_values = [arg for arg in get_args(annotation) if arg is not None]
            values = [value.value if isinstance(value, Enum) else value for value in raw_values]
            if not values:
                raise SchemaTooComplexError("Empty Literal union")
            sample = values[0]
            schema = {"enum": values, "type": "string" if isinstance(sample, str) else "number"}
            return schema, None

        if origin in (tuple, Tuple):
            raise SchemaTooComplexError("Tuple types are not supported")

        if origin in (Union, getattr(__import__("types"), "UnionType", Union)):
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if not args:
                raise SchemaTooComplexError("Union must include at least one non-None member")
            if len(args) == 1:
                return self._compile_annotation(args[0])
            if not all(isinstance(arg, type) and issubclass(arg, BaseModel) for arg in args):
                raise SchemaTooComplexError("Only unions of BaseModel are supported")
            compiled_variants = [self._compile_model(arg) for arg in args]
            if not all(variant.discriminator_value for variant in compiled_variants):
                raise SchemaTooComplexError("Discriminator value required for all union variants")
            discriminator_map = {
                variant.discriminator_value: variant for variant in compiled_variants
            }

            def transform_union(value: Any) -> Any:
                if isinstance(value, BaseModel):
                    value = value.model_dump()
                if not isinstance(value, Mapping):
                    raise TypeError("Expected mapping for union value")
                lookup = value.get("kind") or value.get("tool_name_discriminator")
                if lookup is None:
                    raise ValueError("Union payload missing 'kind' discriminator")
                if lookup not in discriminator_map:
                    raise ValueError(f"Unsupported discriminator value '{lookup}'")
                rename_key(value, "kind", "tool_name_discriminator")
                variant = discriminator_map[lookup]
                return variant.transform(value)

            schema = {
                "oneOf": [variant.schema for variant in compiled_variants],
                "discriminator": {"propertyName": "kind"},
            }
            return schema, transform_union

        raise SchemaTooComplexError(f"Unsupported annotation origin: {origin!r}")
