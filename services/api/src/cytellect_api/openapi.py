"""Register contracts carried by typed headers or generic job-result envelopes."""
from fastapi import FastAPI
from pydantic import BaseModel


def register_contract_schemas(api: FastAPI, *models: type[BaseModel]) -> None:
    original = api.openapi

    def schema():
        document = original()
        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        for model in models:
            definition = model.model_json_schema(ref_template="#/components/schemas/{model}")
            schemas.update(definition.pop("$defs", {}))
            schemas[model.__name__] = definition
        return document

    api.openapi = schema  # type: ignore[method-assign]  # FastAPI's custom OpenAPI extension point.
