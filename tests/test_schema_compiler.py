import pytest

from sgr_deep_research.core.llm.schema_compiler import SchemaCompiler
from sgr_deep_research.core.tools import NextStepToolsBuilder, research_agent_tools


def test_schema_compiler_generates_discriminated_union():
    compiler = SchemaCompiler()
    next_step_model = NextStepToolsBuilder.build_NextStepTools(research_agent_tools)
    compiled = compiler.compile(next_step_model)

    schema = compiled.schema
    assert schema["type"] == "object"
    assert schema["properties"]["function"]["discriminator"] == {"propertyName": "kind"}
    variants = schema["properties"]["function"]["oneOf"]
    assert len(variants) == len(research_agent_tools)
    for variant in variants:
        assert variant["properties"]["kind"]["enum"]
        assert variant["properties"]["kind"]["type"] == "string"
        assert variant["additionalProperties"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {
            "kind": "createreporttool",
            "reasoning": "Ready to summarise",
            "title": "Summary",
            "user_request_language_reference": "English",
            "content": "Report content",
            "confidence": "high",
        }
    ],
)
def test_schema_compiler_transform_applies_kind(payload):
    compiler = SchemaCompiler()
    next_step_model = NextStepToolsBuilder.build_NextStepTools(research_agent_tools)
    compiled = compiler.compile(next_step_model)
    kind = payload["kind"]
    transformed = compiled.transform({"function": dict(payload)})
    assert "function" in transformed
    assert transformed["function"]["tool_name_discriminator"] == kind
