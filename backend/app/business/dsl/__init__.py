"""Business DSL module.

This module provides a framework-agnostic DSL for defining business models,
API interfaces, and other business logic. The definitions can be used to
generate code for different frameworks (FastAPI, Django, Express, etc.).
"""
from app.business.dsl.model_definition import (
    BusinessModel,
    FieldDefinition,
    FieldType,
    IndexDefinition,
    IndexType,
    PermissionRule,
    RelationshipDefinition,
    RelationshipType,
    ValidationRule,
    # Common field factories
    created_at_field,
    deleted_at_field,
    description_field,
    email_field,
    id_field,
    name_field,
    updated_at_field,
)
from app.business.dsl.api_definition import (
    APIInterface,
    AuthenticationType,
    EndpointDefinition,
    HTTPMethod,
    ParameterDefinition,
    ParameterLocation,
    ResponseDefinition,
    # Common endpoint factories
    crud_endpoints,
    create_endpoint,
    delete_endpoint,
    get_endpoint,
    list_endpoint,
    update_endpoint,
)

__all__ = [
    # Model DSL
    "BusinessModel",
    "FieldDefinition",
    "FieldType",
    "IndexDefinition",
    "IndexType",
    "PermissionRule",
    "RelationshipDefinition",
    "RelationshipType",
    "ValidationRule",
    # Field factories
    "id_field",
    "name_field",
    "email_field",
    "description_field",
    "created_at_field",
    "updated_at_field",
    "deleted_at_field",
    # API DSL
    "APIInterface",
    "AuthenticationType",
    "EndpointDefinition",
    "HTTPMethod",
    "ParameterDefinition",
    "ParameterLocation",
    "ResponseDefinition",
    # Endpoint factories
    "list_endpoint",
    "get_endpoint",
    "create_endpoint",
    "update_endpoint",
    "delete_endpoint",
    "crud_endpoints",
]