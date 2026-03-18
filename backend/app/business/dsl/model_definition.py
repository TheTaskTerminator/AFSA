"""Framework-agnostic business model definition.

This module provides a DSL for defining business models in a way that is
independent of any specific framework (FastAPI, Django, Express, etc.).
The definitions can be used to generate code for different frameworks.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class FieldType(Enum):
    """Supported field types for business models."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    TIME = "time"
    UUID = "uuid"
    JSON = "json"
    BINARY = "binary"
    TEXT = "text"
    DECIMAL = "decimal"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"


class RelationshipType(Enum):
    """Types of relationships between models."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class IndexType(Enum):
    """Types of database indexes."""

    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"  # For JSON/full-text search
    GIST = "gist"  # For geometric/full-text search
    UNIQUE = "unique"


@dataclass
class ValidationRule:
    """Validation rule for a field.

    Attributes:
        rule_type: Type of validation (min, max, pattern, custom)
        value: Value for the rule (e.g., min value, regex pattern)
        message: Error message when validation fails
        error_code: Error code for API responses
    """

    rule_type: str
    value: Any = None
    message: str = ""
    error_code: str = "VALIDATION_ERROR"

    # Common validation rules
    @classmethod
    def min_length(cls, length: int, message: str = None) -> "ValidationRule":
        return cls(
            rule_type="min_length",
            value=length,
            message=message or f"Minimum length is {length}",
        )

    @classmethod
    def max_length(cls, length: int, message: str = None) -> "ValidationRule":
        return cls(
            rule_type="max_length",
            value=length,
            message=message or f"Maximum length is {length}",
        )

    @classmethod
    def min_value(cls, value: Any, message: str = None) -> "ValidationRule":
        return cls(
            rule_type="min_value",
            value=value,
            message=message or f"Minimum value is {value}",
        )

    @classmethod
    def max_value(cls, value: Any, message: str = None) -> "ValidationRule":
        return cls(
            rule_type="max_value",
            value=value,
            message=message or f"Maximum value is {value}",
        )

    @classmethod
    def pattern(cls, regex: str, message: str = None) -> "ValidationRule":
        return cls(
            rule_type="pattern",
            value=regex,
            message=message or f"Must match pattern: {regex}",
        )

    @classmethod
    def email(cls, message: str = "Invalid email format") -> "ValidationRule":
        return cls(rule_type="email", message=message)

    @classmethod
    def url(cls, message: str = "Invalid URL format") -> "ValidationRule":
        return cls(rule_type="url", message=message)

    @classmethod
    def phone(cls, message: str = "Invalid phone number format") -> "ValidationRule":
        return cls(rule_type="phone", message=message)

    @classmethod
    def required(cls, message: str = "This field is required") -> "ValidationRule":
        return cls(rule_type="required", message=message)

    @classmethod
    def unique(cls, message: str = "This value must be unique") -> "ValidationRule":
        return cls(rule_type="unique", message=message)


@dataclass
class FieldDefinition:
    """Definition of a field in a business model.

    Attributes:
        name: Field name (snake_case recommended)
        field_type: Type of the field
        description: Human-readable description
        required: Whether the field is required
        unique: Whether the field value must be unique
        default: Default value for the field
        default_factory: Factory function for default value
        primary_key: Whether this is the primary key
        auto_increment: Whether the field auto-increments
        nullable: Whether the field can be null
        index: Whether to create an index on this field
        index_type: Type of index to create
        validations: List of validation rules
        foreign_key: Foreign key reference (model_name.field_name)
        choices: List of allowed values
        examples: Example values for documentation
        metadata: Additional metadata for code generation
    """

    name: str
    field_type: FieldType
    description: str = ""
    required: bool = True
    unique: bool = False
    default: Any = None
    default_factory: Optional[str] = None  # Factory function name
    primary_key: bool = False
    auto_increment: bool = False
    nullable: bool = False
    index: bool = False
    index_type: IndexType = IndexType.BTREE
    validations: List[ValidationRule] = field(default_factory=list)
    foreign_key: Optional[str] = None  # Format: "ModelName.field_name"
    choices: Optional[List[Any]] = None
    examples: Optional[List[Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Add unique validation if field is unique
        if self.unique:
            unique_rules = [v for v in self.validations if v.rule_type == "unique"]
            if not unique_rules:
                self.validations.append(ValidationRule.unique())

        # Add required validation if field is required
        if self.required and not self.nullable:
            required_rules = [v for v in self.validations if v.rule_type == "required"]
            if not required_rules:
                self.validations.append(ValidationRule.required())


@dataclass
class RelationshipDefinition:
    """Definition of a relationship between models.

    Attributes:
        name: Relationship name
        target_model: Name of the related model
        relationship_type: Type of relationship
        foreign_key: Foreign key field name
        back_populates: Name of the reverse relationship
        cascade: Cascade behavior (delete, update, etc.)
        lazy: Lazy loading strategy (select, joined, subquery, dynamic)
        uselist: For one-to-one relationships, set to False
    """

    name: str
    target_model: str
    relationship_type: RelationshipType
    foreign_key: Optional[str] = None
    back_populates: Optional[str] = None
    cascade: str = "save-update, merge"
    lazy: str = "select"
    uselist: Optional[bool] = None  # Auto-determined from relationship_type

    def __post_init__(self):
        if self.uselist is None:
            self.uselist = self.relationship_type in (
                RelationshipType.ONE_TO_MANY,
                RelationshipType.MANY_TO_MANY,
            )


@dataclass
class IndexDefinition:
    """Definition of a database index.

    Attributes:
        name: Index name
        fields: List of field names
        unique: Whether the index is unique
        index_type: Type of index
        condition: Partial index condition
    """

    name: str
    fields: List[str]
    unique: bool = False
    index_type: IndexType = IndexType.BTREE
    condition: Optional[str] = None


@dataclass
class PermissionRule:
    """Permission rule for a model.

    Attributes:
        role: Role name (admin, developer, viewer, etc.)
        actions: Allowed actions (create, read, update, delete)
        condition: Optional condition for row-level security
    """

    role: str
    actions: Set[str]  # create, read, update, delete
    condition: Optional[str] = None  # SQL-like condition for RLS


@dataclass
class BusinessModel:
    """Framework-agnostic business model definition.

    This is the core DSL class that defines a business entity with its
    fields, relationships, validations, and permissions. It can be used
    to generate code for different frameworks.

    Attributes:
        name: Model name (PascalCase recommended)
        table_name: Database table name (snake_case)
        description: Human-readable description
        fields: List of field definitions
        relationships: List of relationship definitions
        indexes: List of index definitions
        permissions: List of permission rules
        soft_delete: Whether to enable soft delete
        timestamps: Whether to add created_at/updated_at fields
        version: Model version for migration tracking
        zone: Zone classification (mutable/immutable)
        metadata: Additional metadata for code generation
    """

    name: str
    table_name: str
    description: str = ""
    fields: List[FieldDefinition] = field(default_factory=list)
    relationships: List[RelationshipDefinition] = field(default_factory=list)
    indexes: List[IndexDefinition] = field(default_factory=list)
    permissions: List[PermissionRule] = field(default_factory=list)
    soft_delete: bool = False
    timestamps: bool = True
    version: str = "1.0.0"
    zone: str = "mutable"  # mutable or immutable
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_field(self, name: str) -> Optional[FieldDefinition]:
        """Get a field by name."""
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def get_primary_key(self) -> Optional[FieldDefinition]:
        """Get the primary key field."""
        for f in self.fields:
            if f.primary_key:
                return f
        return None

    def get_relationship(self, name: str) -> Optional[RelationshipDefinition]:
        """Get a relationship by name."""
        for r in self.relationships:
            if r.name == name:
                return r
        return None

    def add_field(self, field_def: FieldDefinition) -> "BusinessModel":
        """Add a field and return self for chaining."""
        self.fields.append(field_def)
        return self

    def add_relationship(self, rel_def: RelationshipDefinition) -> "BusinessModel":
        """Add a relationship and return self for chaining."""
        self.relationships.append(rel_def)
        return self

    def add_index(self, index_def: IndexDefinition) -> "BusinessModel":
        """Add an index and return self for chaining."""
        self.indexes.append(index_def)
        return self

    def add_permission(self, perm_def: PermissionRule) -> "BusinessModel":
        """Add a permission and return self for chaining."""
        self.permissions.append(perm_def)
        return self


# Common field factories
def id_field(name: str = "id", auto_increment: bool = True) -> FieldDefinition:
    """Create a standard ID field."""
    return FieldDefinition(
        name=name,
        field_type=FieldType.UUID if not auto_increment else FieldType.INTEGER,
        primary_key=True,
        auto_increment=auto_increment,
        description="Unique identifier",
    )


def created_at_field() -> FieldDefinition:
    """Create a created_at timestamp field."""
    return FieldDefinition(
        name="created_at",
        field_type=FieldType.DATETIME,
        required=True,
        description="Creation timestamp",
    )


def updated_at_field() -> FieldDefinition:
    """Create an updated_at timestamp field."""
    return FieldDefinition(
        name="updated_at",
        field_type=FieldType.DATETIME,
        required=True,
        description="Last update timestamp",
    )


def deleted_at_field() -> FieldDefinition:
    """Create a deleted_at soft delete field."""
    return FieldDefinition(
        name="deleted_at",
        field_type=FieldType.DATETIME,
        nullable=True,
        description="Soft delete timestamp",
    )


def name_field(
    name: str = "name",
    max_length: int = 255,
    required: bool = True,
    description: str = "Name",
) -> FieldDefinition:
    """Create a standard name field."""
    return FieldDefinition(
        name=name,
        field_type=FieldType.STRING,
        required=required,
        description=description,
        validations=[
            ValidationRule.max_length(max_length),
            ValidationRule.min_length(1),
        ],
    )


def email_field(name: str = "email", required: bool = True) -> FieldDefinition:
    """Create a standard email field."""
    return FieldDefinition(
        name=name,
        field_type=FieldType.EMAIL,
        required=required,
        unique=True,
        description="Email address",
        validations=[ValidationRule.email()],
    )


def description_field(
    name: str = "description",
    max_length: int = 2000,
    required: bool = False,
) -> FieldDefinition:
    """Create a standard description field."""
    return FieldDefinition(
        name=name,
        field_type=FieldType.TEXT,
        required=required,
        nullable=True,
        description="Description",
        validations=[ValidationRule.max_length(max_length)],
    )