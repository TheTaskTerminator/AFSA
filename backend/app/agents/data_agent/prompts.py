"""Data Agent prompts for database schema design and migration analysis."""

DATA_SYSTEM_PROMPT = """You are the Data Agent, a database specialist in the AFSA system.

Your responsibilities include:
1. Database schema design - Design optimal table structures, indexes, and relationships
2. Migration script generation - Create safe, reversible database migrations
3. Data change verification - Validate data integrity and schema changes
4. Performance optimization - Analyze and optimize database queries and structures

You work with other agents to ensure database changes are safe, performant, and follow best practices.

When reviewing database changes, consider:
- Is the schema design normalized appropriately?
- Are indexes properly defined for query patterns?
- Are foreign key constraints properly set?
- Is the migration safe and reversible?
- What is the impact on existing data?
- Are there any breaking changes for applications?
- Is the data migration strategy sound?

Provide clear, structured feedback with:
- Schema recommendations
- Migration scripts
- Data integrity checks
- Performance considerations
- Rollback strategies
"""

SCHEMA_DESIGN_PROMPT = """Design an optimal database schema for the following requirements:

Requirements:
{requirements}

Context:
{context}

Provide:
1. Table Definitions (with columns, types, constraints)
2. Primary Keys and Indexes
3. Foreign Key Relationships
4. Data Integrity Constraints
5. Naming Conventions
6. Performance Considerations
"""

MIGRATION_GENERATION_PROMPT = """Generate a database migration for the following changes:

Changes:
{changes}

Current Schema:
{current_schema}

Target Schema:
{target_schema}

Provide:
1. Migration Script (upgrade and downgrade)
2. Data Migration Strategy
3. Safety Checks
4. Estimated Execution Time
5. Rollback Strategy
6. Dependencies on Other Migrations
"""

DATA_VALIDATION_PROMPT = """Validate the following database changes:

Changes:
{changes}

Existing Data:
{existing_data}

Constraints:
{constraints}

Check for:
1. Data Integrity Issues
2. Constraint Violations
3. Referential Integrity
4. Null Handling
5. Default Value Consistency
6. Breaking Changes for Applications
"""

QUERY_OPTIMIZATION_PROMPT = """Analyze and optimize the following query/database structure:

Query/Structure:
{query}

Current Performance:
{performance}

Provide:
1. Performance Analysis
2. Index Recommendations
3. Query Optimization Suggestions
4. Potential Bottlenecks
5. Scaling Considerations
"""

MIGRATION_REVIEW_PROMPT = """Review the following database migration:

Migration:
{migration}

Context:
{context}

Analyze:
1. Safety (can it be rolled back?)
2. Performance Impact
3. Lock Duration Estimation
4. Data Integrity
5. Application Compatibility
6. Best Practices Compliance
"""


def get_system_prompt() -> str:
    """Get the system prompt for Data Agent."""
    return DATA_SYSTEM_PROMPT


def format_schema_design_prompt(requirements: str, context: str) -> str:
    """Format schema design prompt."""
    return SCHEMA_DESIGN_PROMPT.format(
        requirements=requirements,
        context=context,
    )


def format_migration_generation_prompt(
    changes: str,
    current_schema: str,
    target_schema: str,
) -> str:
    """Format migration generation prompt."""
    return MIGRATION_GENERATION_PROMPT.format(
        changes=changes,
        current_schema=current_schema,
        target_schema=target_schema,
    )


def format_data_validation_prompt(
    changes: str,
    existing_data: str,
    constraints: str,
) -> str:
    """Format data validation prompt."""
    return DATA_VALIDATION_PROMPT.format(
        changes=changes,
        existing_data=existing_data,
        constraints=constraints,
    )


def format_query_optimization_prompt(query: str, performance: str) -> str:
    """Format query optimization prompt."""
    return QUERY_OPTIMIZATION_PROMPT.format(
        query=query,
        performance=performance,
    )


def format_migration_review_prompt(migration: str, context: str) -> str:
    """Format migration review prompt."""
    return MIGRATION_REVIEW_PROMPT.format(
        migration=migration,
        context=context,
    )