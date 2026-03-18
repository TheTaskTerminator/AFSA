"""Tests for Architect Agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.agents.architect_agent import (
    ArchitectAgent,
    ArchitectSession,
    ArchitectureImpact,
    FeasibilityResult,
    ImpactLevel,
    PerformanceImpact,
    ReviewResult,
    ReviewStatus,
    SecurityFinding,
    ZoneViolation,
)
from app.agents.base import AgentResponse, AgentType, TaskCard
from app.governance.zone import ZoneType, ZoneConfig, get_zone_registry


class TestZoneViolation:
    """Tests for ZoneViolation."""

    def test_create_violation(self):
        """Test creating a zone violation."""
        violation = ZoneViolation(
            path="/app/business/immutable/auth/user.py",
            zone_type=ZoneType.IMMUTABLE,
            zone_name="auth",
            reason="File is in immutable zone",
        )

        assert violation.path == "/app/business/immutable/auth/user.py"
        assert violation.zone_type == ZoneType.IMMUTABLE
        assert violation.zone_name == "auth"
        assert violation.suggested_alternative is None

    def test_violation_with_alternative(self):
        """Test violation with suggested alternative."""
        violation = ZoneViolation(
            path="/app/business/immutable/auth/user.py",
            zone_type=ZoneType.IMMUTABLE,
            zone_name="auth",
            reason="File is in immutable zone",
            suggested_alternative="/app/business/mutable/auth/user.py",
        )

        assert violation.suggested_alternative == "/app/business/mutable/auth/user.py"


class TestFeasibilityResult:
    """Tests for FeasibilityResult."""

    def test_create_result(self):
        """Test creating feasibility result."""
        result = FeasibilityResult(
            score=7,
            complexity="Medium",
            required_technologies=["FastAPI", "PostgreSQL"],
            potential_blockers=["Migration needed"],
            recommended_approach="Incremental implementation",
        )

        assert result.score == 7
        assert result.complexity == "Medium"
        assert len(result.required_technologies) == 2
        assert len(result.potential_blockers) == 1


class TestArchitectureImpact:
    """Tests for ArchitectureImpact."""

    def test_low_impact(self):
        """Test low architecture impact."""
        impact = ArchitectureImpact(
            level=ImpactLevel.LOW,
            affected_components=["UserService"],
            breaking_changes=[],
            migration_required=False,
        )

        assert impact.level == ImpactLevel.LOW
        assert not impact.migration_required

    def test_high_impact(self):
        """Test high architecture impact."""
        impact = ArchitectureImpact(
            level=ImpactLevel.HIGH,
            affected_components=["UserService", "AuthService"],
            breaking_changes=["API endpoint changed"],
            migration_required=True,
            rollback_strategy="Restore from backup",
        )

        assert impact.level == ImpactLevel.HIGH
        assert len(impact.breaking_changes) == 1
        assert impact.migration_required
        assert impact.rollback_strategy == "Restore from backup"


class TestSecurityFinding:
    """Tests for SecurityFinding."""

    def test_low_severity(self):
        """Test low severity finding."""
        finding = SecurityFinding(
            category="XSS",
            severity="low",
            description="Minor XSS risk",
            recommendation="Sanitize input",
        )

        assert finding.category == "XSS"
        assert finding.severity == "low"

    def test_critical_severity(self):
        """Test critical severity finding."""
        finding = SecurityFinding(
            category="Injection",
            severity="critical",
            description="SQL injection vulnerability",
            recommendation="Use parameterized queries",
        )

        assert finding.severity == "critical"


class TestPerformanceImpact:
    """Tests for PerformanceImpact."""

    def test_no_impact(self):
        """Test no performance impact."""
        impact = PerformanceImpact(
            latency_change="none",
            memory_impact="none",
            database_impact="none",
            caching_recommendations=[],
            optimization_suggestions=[],
        )

        assert impact.latency_change == "none"
        assert len(impact.caching_recommendations) == 0

    def test_with_recommendations(self):
        """Test performance impact with recommendations."""
        impact = PerformanceImpact(
            latency_change="medium",
            memory_impact="low",
            database_impact="high",
            caching_recommendations=["Add Redis cache"],
            optimization_suggestions=["Add database index"],
        )

        assert impact.database_impact == "high"
        assert len(impact.caching_recommendations) == 1


class TestReviewResult:
    """Tests for ReviewResult."""

    def test_approved_result(self):
        """Test approved review result."""
        result = ReviewResult(
            status=ReviewStatus.APPROVED,
            summary="Proposal approved",
            key_findings=["No issues found"],
            recommendations=[],
            risk_mitigations={},
            conditions=[],
        )

        assert result.status == ReviewStatus.APPROVED
        assert len(result.violations) == 0

    def test_rejected_result(self):
        """Test rejected review result."""
        violations = [
            ZoneViolation(
                path="/immutable/auth",
                zone_type=ZoneType.IMMUTABLE,
                zone_name="auth",
                reason="Immutable zone",
            )
        ]

        result = ReviewResult(
            status=ReviewStatus.REJECTED,
            summary="Zone violation detected",
            key_findings=["Immutable zone violation"],
            recommendations=["Move to mutable zone"],
            risk_mitigations={},
            conditions=[],
            violations=violations,
        )

        assert result.status == ReviewStatus.REJECTED
        assert len(result.violations) == 1


class TestArchitectAgent:
    """Tests for ArchitectAgent."""

    @pytest.fixture
    def agent(self):
        """Create architect agent instance."""
        return ArchitectAgent()

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = MagicMock()
        llm.chat = AsyncMock()
        return llm

    def test_agent_type(self, agent):
        """Test agent type is ARCHITECT."""
        assert agent.agent_type == AgentType.ARCHITECT
        assert agent.name == "Architect Agent"

    def test_get_or_create_session(self, agent):
        """Test session creation."""
        session = agent._get_or_create_session("test-session")

        assert session.session_id == "test-session"
        assert isinstance(session.created_at, datetime)

    def test_suggest_alternative_path(self, agent):
        """Test path alternative suggestion."""
        alternative = agent._suggest_alternative_path(
            "/app/business/immutable/auth/user.py"
        )

        assert alternative == "/app/business/mutable/auth/user.py"

    def test_suggest_alternative_no_change(self, agent):
        """Test path suggestion when no change needed."""
        alternative = agent._suggest_alternative_path("/app/business/other/file.py")

        assert alternative is None

    @pytest.mark.asyncio
    async def test_check_zone_violations(self, agent):
        """Test zone violation detection."""
        # Initialize zones
        from app.governance.zone import initialize_zones
        initialize_zones()

        violations = agent._check_zone_violations([
            "/app/business/immutable/auth/user.py",
            "/app/business/mutable/rules/config.py",
        ])

        # Should have one violation for immutable path
        assert len(violations) >= 1
        assert any(v.zone_type == ZoneType.IMMUTABLE for v in violations)

    @pytest.mark.asyncio
    async def test_parse_feasibility_result(self, agent):
        """Test parsing feasibility result."""
        content = """
        Technical Feasibility: 7/10
        Complexity: Medium
        Technologies: FastAPI, PostgreSQL
        Blockers: None identified
        """

        result = agent._parse_feasibility_result(content)

        assert result.score == 7
        assert result.complexity == "Medium"

    @pytest.mark.asyncio
    async def test_parse_architecture_impact(self, agent):
        """Test parsing architecture impact."""
        content = """
        Impact Assessment: High
        Breaking Changes: API endpoint signature changed
        Migration Required: Yes
        """

        result = agent._parse_architecture_impact(content)

        assert result.level == ImpactLevel.HIGH
        assert result.migration_required

    @pytest.mark.asyncio
    async def test_parse_security_findings(self, agent):
        """Test parsing security findings."""
        content = """
        Security Review:
        - SQL Injection risk detected
        - XSS vulnerability in user input
        """

        findings = agent._parse_security_findings(content)

        assert len(findings) >= 1
        assert any(f.category == "Injection" for f in findings)

    @pytest.mark.asyncio
    async def test_determine_review_status_approved(self, agent):
        """Test review status determination - approved."""
        feasibility = FeasibilityResult(
            score=8, complexity="Simple",
            required_technologies=[], potential_blockers=[],
            recommended_approach=""
        )
        impact = ArchitectureImpact(
            level=ImpactLevel.LOW,
            affected_components=[], breaking_changes=[],
            migration_required=False
        )

        status = agent._determine_review_status(
            feasibility=feasibility,
            architecture_impact=impact,
            security_findings=[],
            performance_impact=PerformanceImpact(
                latency_change="none", memory_impact="none",
                database_impact="none", caching_recommendations=[],
                optimization_suggestions=[]
            ),
            violations=[],
        )

        assert status == ReviewStatus.APPROVED

    @pytest.mark.asyncio
    async def test_determine_review_status_with_conditions(self, agent):
        """Test review status determination - with conditions."""
        feasibility = FeasibilityResult(
            score=5, complexity="Medium",
            required_technologies=[], potential_blockers=[],
            recommended_approach=""
        )
        impact = ArchitectureImpact(
            level=ImpactLevel.HIGH,
            affected_components=[], breaking_changes=["API change"],
            migration_required=True
        )

        status = agent._determine_review_status(
            feasibility=feasibility,
            architecture_impact=impact,
            security_findings=[],
            performance_impact=PerformanceImpact(
                latency_change="medium", memory_impact="low",
                database_impact="high", caching_recommendations=[],
                optimization_suggestions=[]
            ),
            violations=[],
        )

        assert status == ReviewStatus.APPROVED_WITH_CONDITIONS

    @pytest.mark.asyncio
    async def test_determine_review_status_rejected_critical(self, agent):
        """Test review status determination - rejected for critical."""
        feasibility = FeasibilityResult(
            score=8, complexity="Simple",
            required_technologies=[], potential_blockers=[],
            recommended_approach=""
        )
        impact = ArchitectureImpact(
            level=ImpactLevel.LOW,
            affected_components=[], breaking_changes=[],
            migration_required=False
        )
        security = [SecurityFinding(
            category="Injection",
            severity="critical",
            description="SQL injection",
            recommendation="Fix it"
        )]

        status = agent._determine_review_status(
            feasibility=feasibility,
            architecture_impact=impact,
            security_findings=security,
            performance_impact=PerformanceImpact(
                latency_change="none", memory_impact="none",
                database_impact="none", caching_recommendations=[],
                optimization_suggestions=[]
            ),
            violations=[],
        )

        assert status == ReviewStatus.REJECTED

    @pytest.mark.asyncio
    async def test_determine_review_status_rejected_low_score(self, agent):
        """Test review status determination - rejected for low score."""
        feasibility = FeasibilityResult(
            score=2, complexity="Complex",
            required_technologies=[], potential_blockers=[],
            recommended_approach=""
        )
        impact = ArchitectureImpact(
            level=ImpactLevel.LOW,
            affected_components=[], breaking_changes=[],
            migration_required=False
        )

        status = agent._determine_review_status(
            feasibility=feasibility,
            architecture_impact=impact,
            security_findings=[],
            performance_impact=PerformanceImpact(
                latency_change="none", memory_impact="none",
                database_impact="none", caching_recommendations=[],
                optimization_suggestions=[]
            ),
            violations=[],
        )

        assert status == ReviewStatus.REJECTED

    def test_generate_recommendations(self, agent):
        """Test recommendation generation."""
        feasibility = FeasibilityResult(
            score=5, complexity="Medium",
            required_technologies=["FastAPI"],
            potential_blockers=["Migration"],
            recommended_approach=""
        )
        impact = ArchitectureImpact(
            level=ImpactLevel.HIGH,
            affected_components=["UserService"],
            breaking_changes=["API change"],
            migration_required=True
        )
        security = [SecurityFinding(
            category="XSS",
            severity="high",
            description="XSS risk",
            recommendation="Sanitize input"
        )]
        performance = PerformanceImpact(
            latency_change="medium",
            memory_impact="low",
            database_impact="none",
            caching_recommendations=["Add cache"],
            optimization_suggestions=[]
        )

        recommendations = agent._generate_recommendations(
            feasibility, impact, security, performance
        )

        assert len(recommendations) > 0
        assert any("Migration" in r for r in recommendations)

    def test_generate_conditions(self, agent):
        """Test condition generation."""
        impact = ArchitectureImpact(
            level=ImpactLevel.HIGH,
            affected_components=[],
            breaking_changes=["API change"],
            migration_required=True
        )
        security = [SecurityFinding(
            category="Injection",
            severity="high",
            description="SQL injection",
            recommendation="Use parameterized queries"
        )]

        conditions = agent._generate_conditions(
            status=ReviewStatus.APPROVED_WITH_CONDITIONS,
            security_findings=security,
            architecture_impact=impact,
        )

        assert len(conditions) >= 2  # Security + migration conditions

    def test_format_review_response(self, agent):
        """Test formatting review response."""
        result = ReviewResult(
            status=ReviewStatus.APPROVED,
            summary="Test summary",
            key_findings=["Finding 1"],
            recommendations=["Recommendation 1"],
            risk_mitigations={},
            conditions=[],
        )

        response = agent._format_review_response(result)

        assert "approved" in response.lower()
        assert "Test summary" in response
        assert "Finding 1" in response

    def test_clear_session(self, agent):
        """Test clearing session."""
        agent._get_or_create_session("test-session")

        assert "test-session" in agent._sessions

        cleared = agent.clear_session("test-session")

        assert cleared is True
        assert "test-session" not in agent._sessions

    def test_clear_nonexistent_session(self, agent):
        """Test clearing nonexistent session."""
        cleared = agent.clear_session("nonexistent")
        assert cleared is False


class TestArchitectAgentIntegration:
    """Integration tests for ArchitectAgent."""

    @pytest.fixture
    def agent_with_llm(self):
        """Create agent with mock LLM."""
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock()

        # Create mock response
        mock_response = MagicMock()
        mock_response.content = """
        Technical Feasibility: 8/10
        Complexity: Simple
        Technologies: FastAPI, SQLAlchemy
        Impact: Low
        """
        mock_llm.chat.return_value = mock_response

        return ArchitectAgent(llm=mock_llm), mock_llm

    @pytest.mark.asyncio
    async def test_process_message(self, agent_with_llm):
        """Test processing a review message."""
        agent, mock_llm = agent_with_llm

        response = await agent.process_message(
            session_id="test-session",
            message="Add new user registration endpoint",
            context={"files": ["/app/business/mutable/users/registration.py"]},
        )

        assert isinstance(response, AgentResponse)
        assert response.success
        assert response.metadata["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_generate_task_card(self, agent_with_llm):
        """Test generating task card."""
        agent, mock_llm = agent_with_llm

        # First process a message to create a session
        await agent.process_message(
            session_id="test-session",
            message="Add new feature",
            context={},
        )

        task_card = await agent.generate_task_card("test-session")

        assert task_card is not None
        assert isinstance(task_card, TaskCard)

    @pytest.mark.asyncio
    async def test_execute_task(self, agent_with_llm):
        """Test executing a review task."""
        agent, mock_llm = agent_with_llm

        task_card = TaskCard(
            id="test-task",
            type="feature",
            priority="medium",
            description="Add new API endpoint",
            structured_requirements=[],
            constraints={"files": ["/app/business/mutable/api/users.py"]},
        )

        response = await agent.execute(task_card)

        assert isinstance(response, AgentResponse)
        assert response.task_card == task_card


class TestArchitectAgentZoneViolation:
    """Tests for zone violation detection."""

    @pytest.fixture
    def agent(self):
        """Create architect agent."""
        return ArchitectAgent()

    @pytest.mark.asyncio
    async def test_review_proposal_with_immutable_violation(self, agent):
        """Test reviewing proposal with immutable zone violation."""
        # Initialize zones
        from app.governance.zone import initialize_zones
        initialize_zones()

        result = await agent.review_proposal(
            proposal="Modify authentication logic",
            files=["/app/business/immutable/auth/login.py"],
            context={},
        )

        assert result.status == ReviewStatus.REJECTED
        assert len(result.violations) >= 1
        assert any(v.zone_type == ZoneType.IMMUTABLE for v in result.violations)

    @pytest.mark.asyncio
    async def test_review_proposal_mutable_zone(self, agent):
        """Test reviewing proposal in mutable zone."""
        # Initialize zones
        from app.governance.zone import initialize_zones
        from app.agents.llm import ChatMessage

        # Mock LLM
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Feasibility: 8/10\nImpact: Low"
        mock_llm.chat = AsyncMock(return_value=mock_response)

        agent._llm = mock_llm

        initialize_zones()

        result = await agent.review_proposal(
            proposal="Add new business rule",
            files=["/app/business/mutable/rules/custom.py"],
            context={},
        )

        # Should not be rejected for zone violation
        immutable_violations = [
            v for v in result.violations
            if v.zone_type == ZoneType.IMMUTABLE
        ]
        assert len(immutable_violations) == 0