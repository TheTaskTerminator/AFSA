"""Framework-agnostic API definition.

This module provides a DSL for defining API interfaces in a way that is
independent of any specific framework (FastAPI, Django REST, Express, etc.).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class HTTPMethod(Enum):
    """HTTP methods for API endpoints."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ParameterLocation(Enum):
    """Location of API parameters."""

    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class AuthenticationType(Enum):
    """Types of authentication for API endpoints."""

    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"
    OAUTH2 = "oauth2"
    JWT = "jwt"


@dataclass
class ParameterDefinition:
    """Definition of an API parameter.

    Attributes:
        name: Parameter name
        param_type: Data type of the parameter
        location: Where the parameter is located (path, query, header, etc.)
        required: Whether the parameter is required
        description: Human-readable description
        default: Default value
        example: Example value for documentation
        validations: Validation rules
    """

    name: str
    param_type: str  # string, integer, boolean, etc.
    location: ParameterLocation
    required: bool = True
    description: str = ""
    default: Any = None
    example: Any = None
    validations: Dict[str, Any] = field(default_factory=dict)

    # OpenAPI-style validation constraints
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None


@dataclass
class ResponseDefinition:
    """Definition of an API response.

    Attributes:
        status_code: HTTP status code
        description: Human-readable description
        schema: Response schema (field definitions or reference)
        headers: Response headers
        example: Example response body
    """

    status_code: int
    description: str = ""
    schema: Optional[Dict[str, Any]] = None
    headers: Dict[str, str] = field(default_factory=dict)
    example: Any = None

    @classmethod
    def success(
        cls,
        schema: Optional[Dict[str, Any]] = None,
        description: str = "Success",
    ) -> "ResponseDefinition":
        """Create a standard success response."""
        return cls(
            status_code=200,
            description=description,
            schema=schema,
        )

    @classmethod
    def created(
        cls,
        schema: Optional[Dict[str, Any]] = None,
        description: str = "Created",
    ) -> "ResponseDefinition":
        """Create a standard created response."""
        return cls(
            status_code=201,
            description=description,
            schema=schema,
        )

    @classmethod
    def no_content(cls, description: str = "No Content") -> "ResponseDefinition":
        """Create a standard no content response."""
        return cls(
            status_code=204,
            description=description,
        )

    @classmethod
    def bad_request(
        cls,
        description: str = "Bad Request",
    ) -> "ResponseDefinition":
        """Create a bad request response."""
        return cls(
            status_code=400,
            description=description,
            schema={"type": "object", "properties": {"detail": {"type": "string"}}},
        )

    @classmethod
    def unauthorized(
        cls,
        description: str = "Unauthorized",
    ) -> "ResponseDefinition":
        """Create an unauthorized response."""
        return cls(
            status_code=401,
            description=description,
            schema={"type": "object", "properties": {"detail": {"type": "string"}}},
        )

    @classmethod
    def forbidden(
        cls,
        description: str = "Forbidden",
    ) -> "ResponseDefinition":
        """Create a forbidden response."""
        return cls(
            status_code=403,
            description=description,
            schema={"type": "object", "properties": {"detail": {"type": "string"}}},
        )

    @classmethod
    def not_found(
        cls,
        description: str = "Not Found",
    ) -> "ResponseDefinition":
        """Create a not found response."""
        return cls(
            status_code=404,
            description=description,
            schema={"type": "object", "properties": {"detail": {"type": "string"}}},
        )

    @classmethod
    def validation_error(
        cls,
        description: str = "Validation Error",
    ) -> "ResponseDefinition":
        """Create a validation error response."""
        return cls(
            status_code=422,
            description=description,
            schema={
                "type": "object",
                "properties": {
                    "detail": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "loc": {"type": "array", "items": {"type": "string"}},
                                "msg": {"type": "string"},
                                "type": {"type": "string"},
                            },
                        },
                    }
                },
            },
        )

    @classmethod
    def server_error(
        cls,
        description: str = "Internal Server Error",
    ) -> "ResponseDefinition":
        """Create a server error response."""
        return cls(
            status_code=500,
            description=description,
            schema={"type": "object", "properties": {"detail": {"type": "string"}}},
        )


@dataclass
class EndpointDefinition:
    """Definition of an API endpoint.

    Attributes:
        name: Endpoint name (used for operationId)
        method: HTTP method
        path: URL path (e.g., /users/{id})
        summary: Short summary for documentation
        description: Detailed description
        parameters: Request parameters
        request_body: Request body schema
        responses: Possible responses
        tags: Tags for grouping endpoints
        authentication: Required authentication type
        required_roles: Required user roles
        rate_limit: Rate limit (requests per minute)
        deprecated: Whether the endpoint is deprecated
        metadata: Additional metadata for code generation
    """

    name: str
    method: HTTPMethod
    path: str
    summary: str = ""
    description: str = ""
    parameters: List[ParameterDefinition] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    responses: List[ResponseDefinition] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    authentication: AuthenticationType = AuthenticationType.JWT
    required_roles: Set[str] = field(default_factory=set)
    rate_limit: Optional[int] = None
    deprecated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_parameter(self, param: ParameterDefinition) -> "EndpointDefinition":
        """Add a parameter and return self for chaining."""
        self.parameters.append(param)
        return self

    def add_response(self, response: ResponseDefinition) -> "EndpointDefinition":
        """Add a response and return self for chaining."""
        self.responses.append(response)
        return self

    def require_role(self, role: str) -> "EndpointDefinition":
        """Add a required role and return self for chaining."""
        self.required_roles.add(role)
        return self


@dataclass
class APIInterface:
    """Definition of a complete API interface for a resource.

    This represents a collection of endpoints that operate on a specific
    resource or provide related functionality.

    Attributes:
        name: Interface name (e.g., "UserAPI")
        version: API version
        base_path: Base path for all endpoints (e.g., /api/v1/users)
        description: Human-readable description
        endpoints: List of endpoint definitions
        tags: Tags for OpenAPI documentation
        authentication: Default authentication type
        default_roles: Default required roles for all endpoints
        metadata: Additional metadata for code generation
    """

    name: str
    version: str = "1.0.0"
    base_path: str = ""
    description: str = ""
    endpoints: List[EndpointDefinition] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    authentication: AuthenticationType = AuthenticationType.JWT
    default_roles: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_endpoint(self, endpoint: EndpointDefinition) -> "APIInterface":
        """Add an endpoint and return self for chaining."""
        self.endpoints.append(endpoint)
        return self

    def get_endpoint(self, name: str) -> Optional[EndpointDefinition]:
        """Get an endpoint by name."""
        for e in self.endpoints:
            if e.name == name:
                return e
        return None


# Common endpoint factories
def list_endpoint(
    resource_name: str,
    path: str,
    response_schema: Dict[str, Any],
    tags: List[str] = None,
    summary: str = None,
    authentication: AuthenticationType = AuthenticationType.JWT,
    required_roles: Set[str] = None,
) -> EndpointDefinition:
    """Create a standard list (GET collection) endpoint."""
    return EndpointDefinition(
        name=f"list_{resource_name}",
        method=HTTPMethod.GET,
        path=path,
        summary=summary or f"List {resource_name}",
        description=f"Retrieve a paginated list of {resource_name}.",
        parameters=[
            ParameterDefinition(
                name="page",
                param_type="integer",
                location=ParameterLocation.QUERY,
                required=False,
                default=1,
                description="Page number",
                min_value=1,
            ),
            ParameterDefinition(
                name="page_size",
                param_type="integer",
                location=ParameterLocation.QUERY,
                required=False,
                default=20,
                description="Items per page",
                min_value=1,
                max_value=100,
            ),
        ],
        responses=[
            ResponseDefinition.success(schema=response_schema),
            ResponseDefinition.unauthorized(),
            ResponseDefinition.forbidden(),
        ],
        tags=tags or [resource_name],
        authentication=authentication,
        required_roles=required_roles or {"viewer"},
    )


def get_endpoint(
    resource_name: str,
    path: str,
    response_schema: Dict[str, Any],
    tags: List[str] = None,
    summary: str = None,
    authentication: AuthenticationType = AuthenticationType.JWT,
    required_roles: Set[str] = None,
) -> EndpointDefinition:
    """Create a standard get (GET single) endpoint."""
    return EndpointDefinition(
        name=f"get_{resource_name}",
        method=HTTPMethod.GET,
        path=path,
        summary=summary or f"Get {resource_name}",
        description=f"Retrieve a single {resource_name} by ID.",
        parameters=[
            ParameterDefinition(
                name="id",
                param_type="string",
                location=ParameterLocation.PATH,
                required=True,
                description=f"{resource_name} ID",
            ),
        ],
        responses=[
            ResponseDefinition.success(schema=response_schema),
            ResponseDefinition.unauthorized(),
            ResponseDefinition.forbidden(),
            ResponseDefinition.not_found(),
        ],
        tags=tags or [resource_name],
        authentication=authentication,
        required_roles=required_roles or {"viewer"},
    )


def create_endpoint(
    resource_name: str,
    path: str,
    request_schema: Dict[str, Any],
    response_schema: Dict[str, Any],
    tags: List[str] = None,
    summary: str = None,
    authentication: AuthenticationType = AuthenticationType.JWT,
    required_roles: Set[str] = None,
) -> EndpointDefinition:
    """Create a standard create (POST) endpoint."""
    return EndpointDefinition(
        name=f"create_{resource_name}",
        method=HTTPMethod.POST,
        path=path,
        summary=summary or f"Create {resource_name}",
        description=f"Create a new {resource_name}.",
        request_body={
            "required": True,
            "content": {"application/json": {"schema": request_schema}},
        },
        responses=[
            ResponseDefinition.created(schema=response_schema),
            ResponseDefinition.bad_request(),
            ResponseDefinition.unauthorized(),
            ResponseDefinition.forbidden(),
            ResponseDefinition.validation_error(),
        ],
        tags=tags or [resource_name],
        authentication=authentication,
        required_roles=required_roles or {"developer"},
    )


def update_endpoint(
    resource_name: str,
    path: str,
    request_schema: Dict[str, Any],
    response_schema: Dict[str, Any],
    tags: List[str] = None,
    summary: str = None,
    authentication: AuthenticationType = AuthenticationType.JWT,
    required_roles: Set[str] = None,
    partial: bool = False,
) -> EndpointDefinition:
    """Create a standard update (PUT/PATCH) endpoint."""
    method = HTTPMethod.PATCH if partial else HTTPMethod.PUT
    operation = "partially update" if partial else "update"

    return EndpointDefinition(
        name=f"{'partial_' if partial else ''}update_{resource_name}",
        method=method,
        path=path,
        summary=summary or f"{operation.capitalize()} {resource_name}",
        description=f"{operation.capitalize()} an existing {resource_name}.",
        parameters=[
            ParameterDefinition(
                name="id",
                param_type="string",
                location=ParameterLocation.PATH,
                required=True,
                description=f"{resource_name} ID",
            ),
        ],
        request_body={
            "required": True,
            "content": {"application/json": {"schema": request_schema}},
        },
        responses=[
            ResponseDefinition.success(schema=response_schema),
            ResponseDefinition.bad_request(),
            ResponseDefinition.unauthorized(),
            ResponseDefinition.forbidden(),
            ResponseDefinition.not_found(),
            ResponseDefinition.validation_error(),
        ],
        tags=tags or [resource_name],
        authentication=authentication,
        required_roles=required_roles or {"developer"},
    )


def delete_endpoint(
    resource_name: str,
    path: str,
    tags: List[str] = None,
    summary: str = None,
    authentication: AuthenticationType = AuthenticationType.JWT,
    required_roles: Set[str] = None,
) -> EndpointDefinition:
    """Create a standard delete (DELETE) endpoint."""
    return EndpointDefinition(
        name=f"delete_{resource_name}",
        method=HTTPMethod.DELETE,
        path=path,
        summary=summary or f"Delete {resource_name}",
        description=f"Delete an existing {resource_name}.",
        parameters=[
            ParameterDefinition(
                name="id",
                param_type="string",
                location=ParameterLocation.PATH,
                required=True,
                description=f"{resource_name} ID",
            ),
        ],
        responses=[
            ResponseDefinition.no_content(),
            ResponseDefinition.unauthorized(),
            ResponseDefinition.forbidden(),
            ResponseDefinition.not_found(),
        ],
        tags=tags or [resource_name],
        authentication=authentication,
        required_roles=required_roles or {"admin"},
    )


def crud_endpoints(
    resource_name: str,
    base_path: str,
    list_schema: Dict[str, Any],
    detail_schema: Dict[str, Any],
    create_schema: Dict[str, Any],
    update_schema: Dict[str, Any],
    tags: List[str] = None,
    authentication: AuthenticationType = AuthenticationType.JWT,
    list_roles: Set[str] = None,
    detail_roles: Set[str] = None,
    create_roles: Set[str] = None,
    update_roles: Set[str] = None,
    delete_roles: Set[str] = None,
) -> List[EndpointDefinition]:
    """Create a complete set of CRUD endpoints for a resource."""
    return [
        list_endpoint(
            resource_name,
            base_path,
            list_schema,
            tags=tags,
            authentication=authentication,
            required_roles=list_roles,
        ),
        get_endpoint(
            resource_name,
            f"{base_path}/{{id}}",
            detail_schema,
            tags=tags,
            authentication=authentication,
            required_roles=detail_roles,
        ),
        create_endpoint(
            resource_name,
            base_path,
            create_schema,
            detail_schema,
            tags=tags,
            authentication=authentication,
            required_roles=create_roles,
        ),
        update_endpoint(
            resource_name,
            f"{base_path}/{{id}}",
            update_schema,
            detail_schema,
            tags=tags,
            authentication=authentication,
            required_roles=update_roles,
        ),
        update_endpoint(
            resource_name,
            f"{base_path}/{{id}}",
            update_schema,
            detail_schema,
            tags=tags,
            authentication=authentication,
            required_roles=update_roles,
            partial=True,
        ),
        delete_endpoint(
            resource_name,
            f"{base_path}/{{id}}",
            tags=tags,
            authentication=authentication,
            required_roles=delete_roles,
        ),
    ]