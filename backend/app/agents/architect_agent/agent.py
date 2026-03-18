"""Architect Agent implementation for technical review and architecture analysis."""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from app.agents.base import AgentResponse, AgentType, BaseAgent, TaskCard
from app.agents.llm import BaseLLM, ChatMessage, get_llm
from app.agents.architect_agent.prompts import (
    ARCHITECT_SYSTEM_PROMPT,
    get_system_prompt,
    format_feasibility_prompt,
    format_zone_violation_prompt,
    format_architecture_impact_prompt,
    format_security_review_prompt,
    format_performance_review_prompt,
    format_review_summary_prompt,
)
from app.governance.zone import ZoneType, get_zone_registry
from app.business import get_module_registry

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    """Status of a review."""
    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    REJECTED = "rejected"
    PENDING = "pending"


class ImpactLevel(str, Enum):
    """Impact level for changes."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ZoneViolation:
    """Represents a zone boundary violation."""
    path: str
    zone_type: ZoneType
    zone_name: str
    reason: str
    suggested_alternative: Optional[str] = None


@dataclass
class FeasibilityResult:
    """Result of feasibility analysis."""
    score: int  # 1-10
    complexity: str  # Simple, Medium, Complex
    required_technologies: List[str]
    potential_blockers: List[str]
    recommended_approach: str


@dataclass
class ArchitectureImpact:
    """Architecture impact analysis result."""
    level: ImpactLevel
    affected_components: List[str]
    breaking_changes: List[str]
    migration_required: bool
    rollback_strategy: Optional[str] = None


@dataclass
class SecurityFinding:
    """Security review finding."""
    category: str
    severity: str  # low, medium, high, critical
    description: str
    recommendation: str


@dataclass
class PerformanceImpact:
    """Performance impact analysis."""
    latency_change: str  # "none", "low", "medium", "high"
    memory_impact: str
    database_impact: str
    caching_recommendations: List[str]
    optimization_suggestions: List[str]


@dataclass
class ReviewResult:
    """Complete review result."""
    status: ReviewStatus
    summary: str
    key_findings: List[str]
    recommendations: List[str]
    risk_mitigations: Dict[str, str]
    conditions: List[str]
    violations: List[ZoneViolation] = field(default_factory=list)
    feasibility: Optional[FeasibilityResult] = None
    architecture_impact: Optional[ArchitectureImpact] = None
    security_findings: List[SecurityFinding] = field(default_factory=list)
    performance_impact: Optional[PerformanceImpact] = None


@dataclass
class ArchitectSession:
    """Session for architecture review."""

    session_id: str
    proposal: str = ""
    files_to_modify: List[str] = field(default_factory=list)
    review_result: Optional[ReviewResult] = None
    context: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class ArchitectAgent(BaseAgent):
    """Architect Agent for technical review and architecture analysis.

    The Architect Agent is responsible for:
    1. Technical feasibility evaluation
    2. Zone violation detection
    3. Architecture impact analysis
    4. Security review
    5. Performance review

    It reviews proposed changes from other agents and provides
    structured feedback with recommendations.

    Attributes:
        agent_type: Always AgentType value for architect
        name: Agent name for identification
        llm: LLM instance for analysis
    """

    agent_type = AgentType.ARCHITECT
    name = "Architect Agent"

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize Architect Agent.

        Args:
            llm: LLM instance (will use default if not provided)
            config: Agent configuration
        """
        self._llm = llm
        self._config = config or {}
        self._sessions: Dict[str, ArchitectSession] = {}

    @property
    def llm(self) -> BaseLLM:
        """Get LLM instance."""
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def _get_or_create_session(self, session_id: str) -> ArchitectSession:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ArchitectSession(session_id=session_id)
        return self._sessions[session_id]

    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process a message for architecture review.

        Args:
            session_id: Session identifier
            message: Message describing proposed changes
            context: Additional context (files, components, etc.)

        Returns:
            AgentResponse with review results
        """
        session = self._get_or_create_session(session_id)

        # Update context
        if context:
            session.context.update(context)

        # Store proposal
        session.proposal = message
        if context and "files" in context:
            session.files_to_modify = context["files"]

        # Add to message history
        session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        try:
            # Run comprehensive review
            review_result = await self.review_proposal(
                proposal=message,
                files=session.files_to_modify,
                context=session.context,
            )

            session.review_result = review_result

            # Format response
            response_content = self._format_review_response(review_result)

            # Add assistant message
            session.messages.append({
                "role": "assistant",
                "content": response_content,
                "timestamp": datetime.utcnow().isoformat(),
            })
            session.updated_at = datetime.utcnow()

            return AgentResponse(
                success=True,
                content=response_content,
                metadata={
                    "session_id": session_id,
                    "review_status": review_result.status.value,
                    "violations_count": len(review_result.violations),
                    "findings_count": len(review_result.key_findings),
                },
            )

        except Exception as e:
            logger.error(f"Architect Agent error: {e}")
            return AgentResponse(
                success=False,
                content=f"架构审查时出错：{str(e)}",
                metadata={"error": str(e), "session_id": session_id},
            )

    async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
        """Generate a task card from the review session.

        Args:
            session_id: Session identifier

        Returns:
            TaskCard if review was completed, None otherwise
        """
        session = self._sessions.get(session_id)

        if not session or not session.review_result:
            return None

        result = session.review_result

        # Create task card for the review
        task_card = TaskCard(
            id=str(uuid.uuid4()),
            type="config",  # Review is a configuration/validation task
            priority="high" if result.status == ReviewStatus.REJECTED else "medium",
            description=f"架构审查: {session.proposal[:100]}...",
            structured_requirements=[
                {
                    "id": "review-status",
                    "description": f"审查状态: {result.status.value}",
                    "acceptance_criteria": "所有条件已满足",
                },
                {
                    "id": "violations",
                    "description": f"Zone 违规: {len(result.violations)} 项",
                    "acceptance_criteria": "无违规或已获得例外批准",
                },
                {
                    "id": "conditions",
                    "description": f"审批条件: {len(result.conditions)} 项",
                    "acceptance_criteria": "所有条件已满足",
                },
            ],
            constraints={
                "review_status": result.status.value,
                "must_address": result.conditions,
            },
        )

        return task_card

    async def execute(self, task_card: TaskCard) -> AgentResponse:
        """Execute architecture review for a task.

        Args:
            task_card: Task card with proposal details

        Returns:
            AgentResponse with review results
        """
        try:
            # Extract proposal from task card
            proposal = task_card.description
            files = task_card.constraints.get("files", [])
            context = {
                "priority": task_card.priority,
                "requirements": task_card.structured_requirements,
                **task_card.constraints,
            }

            # Run review
            review_result = await self.review_proposal(
                proposal=proposal,
                files=files,
                context=context,
            )

            response_content = self._format_review_response(review_result)

            return AgentResponse(
                success=review_result.status != ReviewStatus.REJECTED,
                content=response_content,
                metadata={
                    "review_status": review_result.status.value,
                    "violations": [
                        {
                            "path": v.path,
                            "zone": v.zone_name,
                            "reason": v.reason,
                        }
                        for v in review_result.violations
                    ],
                    "recommendations": review_result.recommendations,
                    "conditions": review_result.conditions,
                },
                task_card=task_card,
            )

        except Exception as e:
            logger.error(f"Architect Agent execution error: {e}")
            return AgentResponse(
                success=False,
                content=f"执行审查失败：{str(e)}",
                metadata={"error": str(e)},
            )

    async def review_proposal(
        self,
        proposal: str,
        files: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReviewResult:
        """Perform comprehensive review of a proposed change.

        This is the main entry point for architecture review.

        Args:
            proposal: Description of the proposed change
            files: List of files that will be modified
            context: Additional context for the review

        Returns:
            ReviewResult with comprehensive analysis
        """
        files = files or []
        context = context or {}

        # Step 1: Check zone violations
        violations = self._check_zone_violations(files)

        # If there are violations in immutable zones, reject immediately
        immutable_violations = [
            v for v in violations
            if v.zone_type == ZoneType.IMMUTABLE
        ]

        if immutable_violations:
            return ReviewResult(
                status=ReviewStatus.REJECTED,
                summary="提议的变更违反了不可变区域的边界限制",
                key_findings=[
                    f"发现 {len(immutable_violations)} 处不可变区域违规"
                ],
                recommendations=[
                    "请将变更移至可变区域",
                    "如确需修改不可变区域，请联系管理员申请例外",
                ],
                risk_mitigations={
                    "zone_violation": "申请例外批准或重新设计变更方案",
                },
                conditions=[],
                violations=violations,
            )

        # Step 2: Analyze feasibility
        feasibility = await self._analyze_feasibility(proposal, context)

        # Step 3: Analyze architecture impact
        architecture_impact = await self._analyze_architecture_impact(
            proposal, context
        )

        # Step 4: Security review
        security_findings = await self._security_review(proposal, context)

        # Step 5: Performance review
        performance_impact = await self._analyze_performance_impact(
            proposal, context
        )

        # Step 6: Determine overall status
        status = self._determine_review_status(
            feasibility=feasibility,
            architecture_impact=architecture_impact,
            security_findings=security_findings,
            performance_impact=performance_impact,
            violations=violations,
        )

        # Step 7: Generate recommendations and conditions
        recommendations = self._generate_recommendations(
            feasibility=feasibility,
            architecture_impact=architecture_impact,
            security_findings=security_findings,
            performance_impact=performance_impact,
        )

        conditions = self._generate_conditions(
            status=status,
            security_findings=security_findings,
            architecture_impact=architecture_impact,
        )

        # Step 8: Generate summary
        summary = await self._generate_summary(
            proposal=proposal,
            status=status,
            feasibility=feasibility,
            architecture_impact=architecture_impact,
            security_findings=security_findings,
        )

        return ReviewResult(
            status=status,
            summary=summary,
            key_findings=self._extract_key_findings(
                feasibility, architecture_impact, security_findings
            ),
            recommendations=recommendations,
            risk_mitigations=self._generate_risk_mitigations(
                security_findings, architecture_impact
            ),
            conditions=conditions,
            violations=violations,
            feasibility=feasibility,
            architecture_impact=architecture_impact,
            security_findings=security_findings,
            performance_impact=performance_impact,
        )

    def _check_zone_violations(self, files: List[str]) -> List[ZoneViolation]:
        """Check if any files violate zone boundaries.

        Args:
            files: List of file paths to check

        Returns:
            List of violations found
        """
        violations = []
        zone_registry = get_zone_registry()

        for file_path in files:
            result = zone_registry.get_zone_for_path(file_path)

            if result.matched and result.zone_type == ZoneType.IMMUTABLE:
                violations.append(ZoneViolation(
                    path=file_path,
                    zone_type=result.zone_type,
                    zone_name=result.zone_name or "unknown",
                    reason=f"文件位于不可变区域 '{result.zone_name}'",
                    suggested_alternative=self._suggest_alternative_path(file_path),
                ))
            elif result.matched and result.zone_type == ZoneType.MUTABLE:
                # Check write permissions
                # For now, mutable zones are writable by developers
                pass

        return violations

    def _suggest_alternative_path(self, path: str) -> Optional[str]:
        """Suggest an alternative path in a mutable zone.

        Args:
            path: Original path

        Returns:
            Suggested alternative path
        """
        # Simple suggestion: replace 'immutable' with 'mutable' in path
        if "immutable" in path:
            return path.replace("immutable", "mutable")
        return None

    async def _analyze_feasibility(
        self,
        proposal: str,
        context: Dict[str, Any],
    ) -> FeasibilityResult:
        """Analyze technical feasibility of the proposal.

        Args:
            proposal: Proposal description
            context: Review context

        Returns:
            FeasibilityResult with analysis
        """
        # Build prompt
        prompt = format_feasibility_prompt(
            proposal=proposal,
            context=json.dumps(context, ensure_ascii=False, indent=2),
        )

        # Get LLM analysis
        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)
        content = response.content

        # Parse response
        return self._parse_feasibility_result(content)

    def _parse_feasibility_result(self, content: str) -> FeasibilityResult:
        """Parse LLM response into FeasibilityResult."""
        import re

        # Default values
        score = 5
        complexity = "Medium"
        technologies = []
        blockers = []
        approach = ""

        # Try to extract structured info
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line.lower().startswith("score") or "feasibility" in line.lower():
                # Extract score
                score_match = re.search(r"(\d+)", line)
                if score_match:
                    score = min(10, max(1, int(score_match.group(1))))

            elif "complexity" in line.lower():
                line_lower = line.lower()
                # Use word boundaries to avoid matching "complexity" as "complex"
                if re.search(r'\bsimple\b', line_lower):
                    complexity = "Simple"
                elif re.search(r'\bcomplex\b', line_lower):
                    complexity = "Complex"
                elif re.search(r'\bmedium\b', line_lower):
                    complexity = "Medium"

            elif "technology" in line.lower() or "dependencies" in line.lower():
                # Extract technologies
                if ":" in line:
                    tech_part = line.split(":", 1)[1]
                    technologies = [t.strip() for t in tech_part.split(",") if t.strip()]

            elif "blocker" in line.lower() or "risk" in line.lower():
                if ":" in line:
                    blockers.append(line.split(":", 1)[1].strip())

        # Generate recommended approach from content
        approach = content[:500] if len(content) > 500 else content

        return FeasibilityResult(
            score=score,
            complexity=complexity,
            required_technologies=technologies,
            potential_blockers=blockers,
            recommended_approach=approach,
        )

    async def _analyze_architecture_impact(
        self,
        proposal: str,
        context: Dict[str, Any],
    ) -> ArchitectureImpact:
        """Analyze architecture impact of the proposal.

        Args:
            proposal: Proposal description
            context: Review context

        Returns:
            ArchitectureImpact analysis
        """
        # Get affected components from module registry
        module_registry = get_module_registry()
        modules = module_registry.list_all()

        architecture_context = {
            "modules": [m.id for m in modules],
            "enabled_modules": [m.id for m in module_registry.list_enabled()],
        }

        prompt = format_architecture_impact_prompt(
            proposal=proposal,
            architecture_context=json.dumps(architecture_context, ensure_ascii=False),
            affected_components=json.dumps(context.get("components", []), ensure_ascii=False),
        )

        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)
        content = response.content

        return self._parse_architecture_impact(content)

    def _parse_architecture_impact(self, content: str) -> ArchitectureImpact:
        """Parse LLM response into ArchitectureImpact."""
        # Determine impact level from content
        level = ImpactLevel.LOW
        if "high" in content.lower() or "critical" in content.lower():
            level = ImpactLevel.HIGH
        elif "medium" in content.lower() or "moderate" in content.lower():
            level = ImpactLevel.MEDIUM

        # Extract breaking changes
        breaking_changes = []
        if "breaking" in content.lower():
            lines = content.split("\n")
            for line in lines:
                if "-" in line and any(
                    keyword in line.lower()
                    for keyword in ["break", "change", "remove", "deprecat"]
                ):
                    breaking_changes.append(line.strip("- ").strip())

        # Check for migration requirement
        migration_required = (
            "migration" in content.lower() or
            "schema change" in content.lower() or
            "database" in content.lower()
        )

        return ArchitectureImpact(
            level=level,
            affected_components=[],  # Would be extracted from detailed analysis
            breaking_changes=breaking_changes,
            migration_required=migration_required,
        )

    async def _security_review(
        self,
        proposal: str,
        context: Dict[str, Any],
    ) -> List[SecurityFinding]:
        """Perform security review of the proposal.

        Args:
            proposal: Proposal description
            context: Review context

        Returns:
            List of security findings
        """
        roles = context.get("roles", ["user"])
        data_sensitivity = context.get("data_sensitivity", "normal")

        prompt = format_security_review_prompt(
            proposal=proposal,
            roles=json.dumps(roles),
            data_sensitivity=data_sensitivity,
        )

        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)
        content = response.content

        return self._parse_security_findings(content)

    def _parse_security_findings(self, content: str) -> List[SecurityFinding]:
        """Parse LLM response into SecurityFindings."""
        findings = []

        # Look for common security patterns
        security_keywords = {
            "injection": ("Injection", "high"),
            "xss": ("XSS", "medium"),
            "csrf": ("CSRF", "medium"),
            "auth": ("Authentication", "high"),
            "authorization": ("Authorization", "high"),
            "data exposure": ("Data Exposure", "high"),
            "credential": ("Credentials", "high"),
            "secret": ("Secrets", "high"),
        }

        content_lower = content.lower()
        for keyword, (category, severity) in security_keywords.items():
            if keyword in content_lower:
                findings.append(SecurityFinding(
                    category=category,
                    severity=severity,
                    description=f"潜在的安全风险：{category}",
                    recommendation=f"请确保正确处理 {category} 问题",
                ))

        return findings

    async def _analyze_performance_impact(
        self,
        proposal: str,
        context: Dict[str, Any],
    ) -> PerformanceImpact:
        """Analyze performance impact of the proposal.

        Args:
            proposal: Proposal description
            context: Review context

        Returns:
            PerformanceImpact analysis
        """
        metrics = context.get("metrics", {})

        prompt = format_performance_review_prompt(
            proposal=proposal,
            metrics=json.dumps(metrics, ensure_ascii=False),
        )

        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)
        content = response.content

        return self._parse_performance_impact(content)

    def _parse_performance_impact(self, content: str) -> PerformanceImpact:
        """Parse LLM response into PerformanceImpact."""
        latency = "none"
        if "latency" in content.lower():
            if "high" in content.lower():
                latency = "high"
            elif "medium" in content.lower():
                latency = "medium"
            elif "low" in content.lower():
                latency = "low"

        memory = "none"
        if "memory" in content.lower():
            if "high" in content.lower():
                memory = "high"
            elif "medium" in content.lower():
                memory = "medium"
            else:
                memory = "low"

        db_impact = "none"
        if "database" in content.lower() or "query" in content.lower():
            if "heavy" in content.lower() or "high" in content.lower():
                db_impact = "high"
            elif "medium" in content.lower():
                db_impact = "medium"
            else:
                db_impact = "low"

        caching = []
        if "cache" in content.lower():
            caching.append("考虑添加缓存层")

        optimizations = []
        if "optimization" in content.lower() or "index" in content.lower():
            optimizations.append("检查数据库索引")

        return PerformanceImpact(
            latency_change=latency,
            memory_impact=memory,
            database_impact=db_impact,
            caching_recommendations=caching,
            optimization_suggestions=optimizations,
        )

    def _determine_review_status(
        self,
        feasibility: FeasibilityResult,
        architecture_impact: ArchitectureImpact,
        security_findings: List[SecurityFinding],
        performance_impact: PerformanceImpact,
        violations: List[ZoneViolation],
    ) -> ReviewStatus:
        """Determine overall review status.

        Args:
            feasibility: Feasibility analysis result
            architecture_impact: Architecture impact analysis
            security_findings: Security findings
            performance_impact: Performance impact analysis
            violations: Zone violations

        Returns:
            ReviewStatus for the proposal
        """
        # Check for critical issues
        critical_security = any(
            f.severity == "critical" for f in security_findings
        )
        high_security = any(
            f.severity == "high" for f in security_findings
        )

        if critical_security:
            return ReviewStatus.REJECTED

        if feasibility.score < 3:
            return ReviewStatus.REJECTED

        # Check for conditions
        needs_conditions = (
            high_security or
            architecture_impact.level == ImpactLevel.HIGH or
            feasibility.score < 5 or
            len(violations) > 0
        )

        if needs_conditions:
            return ReviewStatus.APPROVED_WITH_CONDITIONS

        return ReviewStatus.APPROVED

    def _generate_recommendations(
        self,
        feasibility: FeasibilityResult,
        architecture_impact: ArchitectureImpact,
        security_findings: List[SecurityFinding],
        performance_impact: PerformanceImpact,
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # Feasibility recommendations
        if feasibility.score < 7:
            recommendations.append(
                f"可行性评分较低 ({feasibility.score}/10)，建议重新评估方案"
            )

        if feasibility.potential_blockers:
            recommendations.append(
                f"潜在阻碍: {', '.join(feasibility.potential_blockers[:3])}"
            )

        # Architecture recommendations
        if architecture_impact.level == ImpactLevel.HIGH:
            recommendations.append(
                "高架构影响，建议分阶段实施"
            )

        if architecture_impact.migration_required:
            recommendations.append(
                "需要数据库迁移，请准备回滚脚本"
            )

        # Security recommendations
        for finding in security_findings:
            if finding.severity in ("high", "critical"):
                recommendations.append(f"[安全] {finding.recommendation}")

        # Performance recommendations
        if performance_impact.caching_recommendations:
            recommendations.extend(performance_impact.caching_recommendations)

        return recommendations[:10]  # Limit to 10 recommendations

    def _generate_conditions(
        self,
        status: ReviewStatus,
        security_findings: List[SecurityFinding],
        architecture_impact: ArchitectureImpact,
    ) -> List[str]:
        """Generate approval conditions if needed."""
        conditions = []

        if status != ReviewStatus.APPROVED_WITH_CONDITIONS:
            return conditions

        # Security conditions
        for finding in security_findings:
            if finding.severity == "high":
                conditions.append(
                    f"必须解决安全问题: {finding.category}"
                )

        # Architecture conditions
        if architecture_impact.breaking_changes:
            conditions.append(
                "必须提供变更通知和迁移指南"
            )

        if architecture_impact.migration_required:
            conditions.append(
                "必须提供数据库迁移脚本和回滚方案"
            )

        return conditions

    def _extract_key_findings(
        self,
        feasibility: FeasibilityResult,
        architecture_impact: ArchitectureImpact,
        security_findings: List[SecurityFinding],
    ) -> List[str]:
        """Extract key findings from analysis."""
        findings = []

        findings.append(f"可行性评分: {feasibility.score}/10 ({feasibility.complexity})")

        if architecture_impact.breaking_changes:
            findings.append(
                f"发现 {len(architecture_impact.breaking_changes)} 处潜在破坏性变更"
            )

        if security_findings:
            high_count = sum(1 for f in security_findings if f.severity == "high")
            if high_count > 0:
                findings.append(f"发现 {high_count} 个高严重性安全问题")

        if not findings:
            findings.append("未发现重大问题")

        return findings

    def _generate_risk_mitigations(
        self,
        security_findings: List[SecurityFinding],
        architecture_impact: ArchitectureImpact,
    ) -> Dict[str, str]:
        """Generate risk mitigation strategies."""
        mitigations = {}

        for finding in security_findings:
            mitigations[finding.category] = finding.recommendation

        if architecture_impact.rollback_strategy:
            mitigations["架构变更"] = architecture_impact.rollback_strategy

        return mitigations

    async def _generate_summary(
        self,
        proposal: str,
        status: ReviewStatus,
        feasibility: FeasibilityResult,
        architecture_impact: ArchitectureImpact,
        security_findings: List[SecurityFinding],
    ) -> str:
        """Generate a summary of the review."""
        status_text = {
            ReviewStatus.APPROVED: "已批准",
            ReviewStatus.APPROVED_WITH_CONDITIONS: "有条件批准",
            ReviewStatus.REJECTED: "已拒绝",
            ReviewStatus.PENDING: "待定",
        }

        summary = f"审查结果: {status_text[status]}\n"
        summary += f"可行性评分: {feasibility.score}/10\n"
        summary += f"架构影响级别: {architecture_impact.level.value}\n"
        summary += f"安全问题: {len(security_findings)} 项\n"

        return summary

    def _format_review_response(self, result: ReviewResult) -> str:
        """Format the review result for display."""
        lines = []
        lines.append(f"## 审查结果: {result.status.value}")
        lines.append("")
        lines.append("### 摘要")
        lines.append(result.summary)
        lines.append("")

        if result.violations:
            lines.append("### Zone 违规")
            for v in result.violations:
                lines.append(f"- **{v.path}**: {v.reason}")
                if v.suggested_alternative:
                    lines.append(f"  - 建议: {v.suggested_alternative}")
            lines.append("")

        if result.key_findings:
            lines.append("### 主要发现")
            for f in result.key_findings:
                lines.append(f"- {f}")
            lines.append("")

        if result.recommendations:
            lines.append("### 建议")
            for i, r in enumerate(result.recommendations, 1):
                lines.append(f"{i}. {r}")
            lines.append("")

        if result.conditions:
            lines.append("### 批准条件")
            for i, c in enumerate(result.conditions, 1):
                lines.append(f"{i}. {c}")
            lines.append("")

        return "\n".join(lines)

    def clear_session(self, session_id: str) -> bool:
        """Clear a session from memory.

        Args:
            session_id: Session identifier

        Returns:
            True if session was cleared
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False