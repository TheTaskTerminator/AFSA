"""Tests for Business DSL definitions."""
import pytest

from app.business.dsl import (
    APIInterface,
    AuthenticationType,
    BusinessModel,
    EndpointDefinition,
    FieldDefinition,
    FieldType,
    HTTPMethod,
    IndexDefinition,
    IndexType,
    ParameterDefinition,
    ParameterLocation,
    PermissionRule,
    RelationshipDefinition,
    RelationshipType,
    ResponseDefinition,
    ValidationRule,
    created_at_field,
    create_endpoint,
    crud_endpoints,
    delete_endpoint,
    deleted_at_field,
    description_field,
    email_field,
    get_endpoint,
    id_field,
    list_endpoint,
    name_field,
    update_endpoint,
    updated_at_field,
)


class TestFieldDefinition:
    """Tests for FieldDefinition."""

    def test_basic_field(self):
        """Test creating a basic field."""
        field = FieldDefinition(
            name="username",
            field_type=FieldType.STRING,
            description="User's username",
        )

        assert field.name == "username"
        assert field.field_type == FieldType.STRING
        assert field.required is True
        assert field.unique is False

    def test_unique_field_adds_validation(self):
        """Test that unique field gets unique validation."""
        field = FieldDefinition(
            name="email",
            field_type=FieldType.EMAIL,
            unique=True,
        )

        unique_validations = [v for v in field.validations if v.rule_type == "unique"]
        assert len(unique_validations) == 1

    def test_required_field_adds_validation(self):
        """Test that required field gets required validation."""
        field = FieldDefinition(
            name="name",
            field_type=FieldType.STRING,
            required=True,
        )

        required_validations = [v for v in field.validations if v.rule_type == "required"]
        assert len(required_validations) == 1


class TestValidationRule:
    """Tests for ValidationRule."""

    def test_min_length(self):
        """Test min_length validation."""
        rule = ValidationRule.min_length(5)
        assert rule.rule_type == "min_length"
        assert rule.value == 5

    def test_max_length(self):
        """Test max_length validation."""
        rule = ValidationRule.max_length(100)
        assert rule.rule_type == "max_length"
        assert rule.value == 100

    def test_pattern(self):
        """Test pattern validation."""
        rule = ValidationRule.pattern(r"^[a-z]+$")
        assert rule.rule_type == "pattern"
        assert rule.value == r"^[a-z]+$"

    def test_email(self):
        """Test email validation."""
        rule = ValidationRule.email()
        assert rule.rule_type == "email"


class TestRelationshipDefinition:
    """Tests for RelationshipDefinition."""

    def test_one_to_many(self):
        """Test one-to-many relationship."""
        rel = RelationshipDefinition(
            name="posts",
            target_model="Post",
            relationship_type=RelationshipType.ONE_TO_MANY,
        )

        assert rel.uselist is True

    def test_one_to_one(self):
        """Test one-to-one relationship."""
        rel = RelationshipDefinition(
            name="profile",
            target_model="Profile",
            relationship_type=RelationshipType.ONE_TO_ONE,
        )

        assert rel.uselist is False


class TestBusinessModel:
    """Tests for BusinessModel."""

    def test_basic_model(self):
        """Test creating a basic model."""
        model = BusinessModel(
            name="User",
            table_name="users",
            description="User model",
            fields=[
                id_field(),
                name_field(),
                email_field(),
            ],
        )

        assert model.name == "User"
        assert model.table_name == "users"
        assert len(model.fields) == 3

    def test_get_field(self):
        """Test getting a field by name."""
        model = BusinessModel(
            name="User",
            table_name="users",
            fields=[
                FieldDefinition(name="id", field_type=FieldType.INTEGER, primary_key=True),
                FieldDefinition(name="name", field_type=FieldType.STRING),
            ],
        )

        field = model.get_field("name")
        assert field is not None
        assert field.name == "name"

        assert model.get_field("nonexistent") is None

    def test_get_primary_key(self):
        """Test getting primary key field."""
        model = BusinessModel(
            name="User",
            table_name="users",
            fields=[
                FieldDefinition(name="id", field_type=FieldType.INTEGER, primary_key=True),
                FieldDefinition(name="name", field_type=FieldType.STRING),
            ],
        )

        pk = model.get_primary_key()
        assert pk is not None
        assert pk.name == "id"

    def test_chained_add(self):
        """Test chained add methods."""
        model = (
            BusinessModel(name="User", table_name="users")
            .add_field(id_field())
            .add_field(name_field())
            .add_relationship(
                RelationshipDefinition(
                    name="posts",
                    target_model="Post",
                    relationship_type=RelationshipType.ONE_TO_MANY,
                )
            )
            .add_index(
                IndexDefinition(
                    name="idx_user_email",
                    fields=["email"],
                    unique=True,
                )
            )
            .add_permission(
                PermissionRule(
                    role="admin",
                    actions={"create", "read", "update", "delete"},
                )
            )
        )

        assert len(model.fields) == 2
        assert len(model.relationships) == 1
        assert len(model.indexes) == 1
        assert len(model.permissions) == 1


class TestFieldFactories:
    """Tests for field factory functions."""

    def test_id_field_uuid(self):
        """Test UUID ID field."""
        field = id_field(auto_increment=False)
        assert field.field_type == FieldType.UUID
        assert field.primary_key is True
        assert field.auto_increment is False

    def test_id_field_integer(self):
        """Test integer ID field."""
        field = id_field()
        assert field.field_type == FieldType.INTEGER
        assert field.primary_key is True
        assert field.auto_increment is True

    def test_name_field(self):
        """Test name field factory."""
        field = name_field()
        assert field.name == "name"
        assert field.field_type == FieldType.STRING
        assert any(v.rule_type == "max_length" for v in field.validations)

    def test_email_field(self):
        """Test email field factory."""
        field = email_field()
        assert field.name == "email"
        assert field.field_type == FieldType.EMAIL
        assert field.unique is True

    def test_timestamp_fields(self):
        """Test timestamp field factories."""
        created = created_at_field()
        updated = updated_at_field()
        deleted = deleted_at_field()

        assert created.field_type == FieldType.DATETIME
        assert updated.field_type == FieldType.DATETIME
        assert deleted.field_type == FieldType.DATETIME
        assert deleted.nullable is True


class TestParameterDefinition:
    """Tests for ParameterDefinition."""

    def test_path_parameter(self):
        """Test path parameter."""
        param = ParameterDefinition(
            name="id",
            param_type="string",
            location=ParameterLocation.PATH,
            required=True,
        )

        assert param.location == ParameterLocation.PATH
        assert param.required is True

    def test_query_parameter(self):
        """Test query parameter."""
        param = ParameterDefinition(
            name="page",
            param_type="integer",
            location=ParameterLocation.QUERY,
            required=False,
            default=1,
        )

        assert param.location == ParameterLocation.QUERY
        assert param.default == 1


class TestResponseDefinition:
    """Tests for ResponseDefinition."""

    def test_factory_methods(self):
        """Test response factory methods."""
        success = ResponseDefinition.success()
        assert success.status_code == 200

        created = ResponseDefinition.created()
        assert created.status_code == 201

        no_content = ResponseDefinition.no_content()
        assert no_content.status_code == 204

        not_found = ResponseDefinition.not_found()
        assert not_found.status_code == 404


class TestEndpointDefinition:
    """Tests for EndpointDefinition."""

    def test_basic_endpoint(self):
        """Test creating a basic endpoint."""
        endpoint = EndpointDefinition(
            name="get_user",
            method=HTTPMethod.GET,
            path="/users/{id}",
            summary="Get a user by ID",
        )

        assert endpoint.method == HTTPMethod.GET
        assert endpoint.path == "/users/{id}"

    def test_chained_methods(self):
        """Test chained endpoint methods."""
        endpoint = (
            EndpointDefinition(
                name="update_user",
                method=HTTPMethod.PUT,
                path="/users/{id}",
            )
            .add_parameter(
                ParameterDefinition(
                    name="id",
                    param_type="string",
                    location=ParameterLocation.PATH,
                )
            )
            .add_response(ResponseDefinition.success())
            .require_role("developer")
        )

        assert len(endpoint.parameters) == 1
        assert len(endpoint.responses) == 1
        assert "developer" in endpoint.required_roles


class TestEndpointFactories:
    """Tests for endpoint factory functions."""

    def test_list_endpoint(self):
        """Test list endpoint factory."""
        endpoint = list_endpoint(
            resource_name="users",
            path="/users",
            response_schema={"type": "array"},
        )

        assert endpoint.method == HTTPMethod.GET
        assert endpoint.path == "/users"
        assert "page" in [p.name for p in endpoint.parameters]

    def test_get_endpoint(self):
        """Test get endpoint factory."""
        endpoint = get_endpoint(
            resource_name="user",
            path="/users/{id}",
            response_schema={"type": "object"},
        )

        assert endpoint.method == HTTPMethod.GET
        assert "{id}" in endpoint.path

    def test_create_endpoint(self):
        """Test create endpoint factory."""
        endpoint = create_endpoint(
            resource_name="user",
            path="/users",
            request_schema={"type": "object"},
            response_schema={"type": "object"},
        )

        assert endpoint.method == HTTPMethod.POST
        assert endpoint.request_body is not None

    def test_update_endpoint(self):
        """Test update endpoint factory."""
        endpoint = update_endpoint(
            resource_name="user",
            path="/users/{id}",
            request_schema={"type": "object"},
            response_schema={"type": "object"},
        )

        assert endpoint.method == HTTPMethod.PUT

        partial = update_endpoint(
            resource_name="user",
            path="/users/{id}",
            request_schema={"type": "object"},
            response_schema={"type": "object"},
            partial=True,
        )

        assert partial.method == HTTPMethod.PATCH

    def test_delete_endpoint(self):
        """Test delete endpoint factory."""
        endpoint = delete_endpoint(
            resource_name="user",
            path="/users/{id}",
        )

        assert endpoint.method == HTTPMethod.DELETE
        assert "admin" in endpoint.required_roles

    def test_crud_endpoints(self):
        """Test CRUD endpoints factory."""
        endpoints = crud_endpoints(
            resource_name="user",
            base_path="/users",
            list_schema={"type": "array"},
            detail_schema={"type": "object"},
            create_schema={"type": "object"},
            update_schema={"type": "object"},
        )

        assert len(endpoints) == 6
        methods = [e.method for e in endpoints]
        assert HTTPMethod.GET in methods
        assert HTTPMethod.POST in methods
        assert HTTPMethod.PUT in methods
        assert HTTPMethod.PATCH in methods
        assert HTTPMethod.DELETE in methods


class TestAPIInterface:
    """Tests for APIInterface."""

    def test_basic_interface(self):
        """Test creating a basic API interface."""
        api = APIInterface(
            name="UserAPI",
            base_path="/api/v1/users",
            endpoints=[
                list_endpoint("users", "/users", {"type": "array"}),
            ],
        )

        assert api.name == "UserAPI"
        assert len(api.endpoints) == 1

    def test_chained_add(self):
        """Test chained add endpoint."""
        api = (
            APIInterface(name="UserAPI", base_path="/users")
            .add_endpoint(
                get_endpoint("user", "/users/{id}", {"type": "object"})
            )
        )

        assert len(api.endpoints) == 1


class TestCompleteUserModel:
    """Test creating a complete User model with DSL."""

    def test_complete_user_model(self):
        """Create a complete User model definition."""
        user_model = (
            BusinessModel(
                name="User",
                table_name="users",
                description="Application user",
                timestamps=True,
                soft_delete=True,
            )
            .add_field(id_field())
            .add_field(name_field("username", required=True))
            .add_field(email_field())
            .add_field(
                FieldDefinition(
                    name="password_hash",
                    field_type=FieldType.STRING,
                    description="Hashed password",
                    validations=[ValidationRule.min_length(60)],
                )
            )
            .add_field(
                FieldDefinition(
                    name="is_active",
                    field_type=FieldType.BOOLEAN,
                    default=True,
                    description="Whether user is active",
                )
            )
            .add_field(created_at_field())
            .add_field(updated_at_field())
            .add_field(deleted_at_field())
            .add_index(
                IndexDefinition(
                    name="idx_user_email",
                    fields=["email"],
                    unique=True,
                )
            )
            .add_permission(
                PermissionRule(
                    role="admin",
                    actions={"create", "read", "update", "delete"},
                )
            )
            .add_permission(
                PermissionRule(
                    role="developer",
                    actions={"create", "read", "update"},
                )
            )
            .add_permission(
                PermissionRule(
                    role="viewer",
                    actions={"read"},
                )
            )
        )

        # Verify model structure
        assert user_model.name == "User"
        assert len(user_model.fields) == 8  # id, username, email, password_hash, is_active, created_at, updated_at, deleted_at
        assert len(user_model.indexes) == 1
        assert len(user_model.permissions) == 3

        # Verify primary key
        pk = user_model.get_primary_key()
        assert pk is not None
        assert pk.name == "id"