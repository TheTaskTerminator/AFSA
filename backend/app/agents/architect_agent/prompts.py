"""Prompts for Architect Agent."""

ARCHITECT_SYSTEM_PROMPT = """You are the Architect Agent, a technical reviewer and architecture analyst in the AFSA system.

Your responsibilities include:
1. Technical feasibility evaluation - Assess if proposed changes are technically viable
2. Zone violation detection - Ensure changes respect mutable/immutable boundaries
3. Architecture impact analysis - Analyze the broader impact of proposed changes
4. Security review - Identify potential security implications
5. Performance review - Assess performance implications

You work with other agents to ensure changes are safe, feasible, and aligned with system architecture.

When reviewing proposals, consider:
- Is the change technically feasible with current infrastructure?
- Does it violate any immutable zone boundaries?
- What are the security implications?
- What is the performance impact?
- What other components might be affected?
- Are there any breaking changes?
- Is the proposed timeline realistic?

Provide clear, structured feedback with:
- Overall assessment (APPROVED, APPROVED_WITH_CONDITIONS, REJECTED)
- Detailed analysis for each area
- Specific recommendations
- Risk mitigation strategies
"""

FEASIBILITY_ANALYSIS_PROMPT = """Analyze the technical feasibility of the following proposed change:

Proposed Change:
{proposal}

Context:
{context}

Provide a detailed analysis including:
1. Technical Feasibility (1-10 score)
2. Required Technologies/Dependencies
3. Estimated Complexity (Simple/Medium/Complex)
4. Potential Blockers
5. Recommended Approach
"""

ZONE_VIOLATION_PROMPT = """Analyze if the following proposed changes would violate zone boundaries:

Proposed Changes:
{changes}

Zone Configuration:
- Immutable Zones: {immutable_zones}
- Mutable Zones: {mutable_zones}

Files to Modify:
{files}

Identify:
1. Any zone boundary violations
2. Files that are in protected (immutable) zones
3. Recommended alternatives if violations exist
"""

ARCHITECTURE_IMPACT_PROMPT = """Analyze the architecture impact of the following changes:

Proposed Changes:
{proposal}

Current Architecture Context:
{architecture_context}

Affected Components:
{affected_components}

Provide:
1. Impact Assessment (Low/Medium/High)
2. Affected Services/Components
3. Database Schema Changes Required
4. API Contract Changes
5. Breaking Changes
6. Migration Strategy Recommendations
7. Rollback Strategy
"""

SECURITY_REVIEW_PROMPT = """Perform a security review of the proposed changes:

Proposed Changes:
{proposal}

User Roles Involved:
{roles}

Data Sensitivity:
{data_sensitivity}

Identify:
1. Authentication/Authorization Concerns
2. Data Exposure Risks
3. Injection Vulnerabilities
4. CSRF/XSS Risks (if applicable)
5. Secrets/Credentials Handling
6. Compliance Implications
7. Recommended Security Controls
"""

PERFORMANCE_REVIEW_PROMPT = """Analyze performance implications of the proposed changes:

Proposed Changes:
{proposal}

Current System Metrics:
{metrics}

Provide:
1. Performance Impact Assessment
2. Estimated Latency Changes
3. Database Query Impact
4. Memory Usage Impact
5. Caching Recommendations
6. Scaling Implications
7. Optimization Recommendations
"""

REVIEW_SUMMARY_PROMPT = """Provide a comprehensive review summary for the following analysis:

{analysis}

Format the response as:
## Overall Assessment
[APPROVED/APPROVED_WITH_CONDITIONS/REJECTED]

## Summary
[Brief summary of the review]

## Key Findings
- Finding 1
- Finding 2
...

## Recommendations
1. [Recommendation 1]
2. [Recommendation 2]
...

## Risk Mitigation
- Risk 1: Mitigation strategy
- Risk 2: Mitigation strategy
...

## Conditions for Approval (if applicable)
1. [Condition 1]
2. [Condition 2]
...
"""


def get_system_prompt() -> str:
    """Get the system prompt for Architect Agent."""
    return ARCHITECT_SYSTEM_PROMPT


def format_feasibility_prompt(proposal: str, context: str) -> str:
    """Format feasibility analysis prompt."""
    return FEASIBILITY_ANALYSIS_PROMPT.format(
        proposal=proposal,
        context=context,
    )


def format_zone_violation_prompt(
    changes: str,
    immutable_zones: str,
    mutable_zones: str,
    files: str,
) -> str:
    """Format zone violation prompt."""
    return ZONE_VIOLATION_PROMPT.format(
        changes=changes,
        immutable_zones=immutable_zones,
        mutable_zones=mutable_zones,
        files=files,
    )


def format_architecture_impact_prompt(
    proposal: str,
    architecture_context: str,
    affected_components: str,
) -> str:
    """Format architecture impact prompt."""
    return ARCHITECTURE_IMPACT_PROMPT.format(
        proposal=proposal,
        architecture_context=architecture_context,
        affected_components=affected_components,
    )


def format_security_review_prompt(
    proposal: str,
    roles: str,
    data_sensitivity: str,
) -> str:
    """Format security review prompt."""
    return SECURITY_REVIEW_PROMPT.format(
        proposal=proposal,
        roles=roles,
        data_sensitivity=data_sensitivity,
    )


def format_performance_review_prompt(
    proposal: str,
    metrics: str,
) -> str:
    """Format performance review prompt."""
    return PERFORMANCE_REVIEW_PROMPT.format(
        proposal=proposal,
        metrics=metrics,
    )


def format_review_summary_prompt(analysis: str) -> str:
    """Format review summary prompt."""
    return REVIEW_SUMMARY_PROMPT.format(analysis=analysis)