"""
Tests for support-agent-mcp.
Run: pytest tests/
"""
import pytest

from edge_llm.core.memory.local import LocalMemoryStore
from edge_llm.core.tenants.local import LocalTenantStore
from edge_llm.core.tenants.base import TenantConfig
from edge_llm.core.usage.local import LocalUsageTracker

from support_agent_mcp.pipeline import SupportPipeline
from support_agent_mcp.agent import SupportAgent
from support_agent_mcp.tools.implementations import (
    triage_ticket, search_knowledge_base, update_ticket, escalate_ticket,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def agent(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    return SupportAgent(
        memory=LocalMemoryStore(tmp_path / "memory"),
        tenants=LocalTenantStore(tmp_path / "tenants.json"),
        tracker=LocalUsageTracker(tmp_path / "usage"),
    )


# ── SupportPipeline ───────────────────────────────────────────────────────────

def test_pipeline_validate():
    SupportPipeline().validate()


def test_pipeline_stages():
    sm = SupportPipeline()
    assert "OPEN" in sm.stages
    assert "TRIAGING" in sm.stages
    assert "IN_PROGRESS" in sm.stages
    assert "WAITING_CUSTOMER" in sm.stages
    assert "ESCALATED" in sm.stages
    assert "RESOLVED" in sm.stages
    assert "CLOSED" in sm.stages


def test_pipeline_terminal_stages():
    sm = SupportPipeline()
    assert sm.is_terminal("RESOLVED")
    assert sm.is_terminal("CLOSED")
    assert not sm.is_terminal("OPEN")
    assert not sm.is_terminal("IN_PROGRESS")
    assert not sm.is_terminal("ESCALATED")


def test_pipeline_initial_stage():
    assert SupportPipeline().initial_stage() == "OPEN"


def test_pipeline_transitions_valid():
    sm = SupportPipeline()
    assert sm.can_transition("OPEN", "TRIAGING")
    assert sm.can_transition("TRIAGING", "IN_PROGRESS")
    assert sm.can_transition("TRIAGING", "ESCALATED")
    assert sm.can_transition("IN_PROGRESS", "WAITING_CUSTOMER")
    assert sm.can_transition("IN_PROGRESS", "RESOLVED")
    assert sm.can_transition("ESCALATED", "RESOLVED")
    assert sm.can_transition("RESOLVED", "CLOSED")


def test_pipeline_transitions_invalid():
    sm = SupportPipeline()
    assert not sm.can_transition("OPEN", "RESOLVED")
    assert not sm.can_transition("CLOSED", "OPEN")
    assert not sm.can_transition("RESOLVED", "OPEN")


def test_pipeline_all_stages_have_context():
    sm = SupportPipeline()
    for stage in sm.stages:
        ctx = sm.get_context(stage)
        assert ctx.stage == stage
        assert ctx.objective, f"Stage {stage} has no objective"


# ── Tool: triage_ticket ───────────────────────────────────────────────────────

def test_triage_ticket_critical():
    result = triage_ticket(message="Production is down, complete outage!", current_stage="OPEN")
    assert result["severity"] == "critical"
    assert result["priority"] == "critical"
    assert "escalat" in result["hint"].lower()


def test_triage_ticket_high():
    result = triage_ticket(message="The app keeps crashing on login", current_stage="OPEN")
    assert result["severity"] == "high"
    assert result["priority"] == "high"


def test_triage_ticket_billing():
    result = triage_ticket(message="I was charged twice for my subscription", current_stage="OPEN")
    assert result["category"] == "billing"
    assert result["severity"] == "medium"


def test_triage_ticket_low():
    result = triage_ticket(message="How do I change my profile picture?", current_stage="OPEN")
    assert result["severity"] == "low"
    assert result["priority"] == "low"


def test_triage_ticket_preview_truncated():
    result = triage_ticket(message="x" * 200, current_stage="OPEN")
    assert len(result["message_preview"]) == 120


def test_triage_ticket_has_required_fields():
    result = triage_ticket(message="Something is broken", current_stage="TRIAGING")
    assert "severity" in result
    assert "priority" in result
    assert "category" in result
    assert "hint" in result
    assert "current_stage" in result


# ── Tool: search_knowledge_base ───────────────────────────────────────────────

def test_search_knowledge_base_returns_hint():
    result = search_knowledge_base(query="login error 403")
    assert "hint" in result
    assert "suggested_approach" in result
    assert result["query"] == "login error 403"


def test_search_knowledge_base_with_category():
    result = search_knowledge_base(query="payment failed", category="billing")
    assert result["category"] == "billing"


# ── Tool: update_ticket ───────────────────────────────────────────────────────

def test_update_ticket_without_memory():
    result = update_ticket(ticket_id="ticket-1", new_stage="IN_PROGRESS")
    assert result["updated"] is True
    assert result["stage"] == "IN_PROGRESS"
    assert result["ticket_id"] == "ticket-1"


def test_update_ticket_appends_notes(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("t1", {"stage": "OPEN", "notes": ["first note"]})
    update_ticket(ticket_id="t1", new_stage="IN_PROGRESS", notes="second note", memory=mem)
    state = mem.get_entity_state("t1")
    assert isinstance(state["notes"], list)
    assert "first note" in state["notes"]
    assert "second note" in state["notes"]


def test_update_ticket_sets_priority(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("t1", {"notes": []})
    update_ticket(ticket_id="t1", new_stage="IN_PROGRESS", priority="high", memory=mem)
    assert mem.get_entity_state("t1")["priority"] == "high"


def test_update_ticket_sets_resolution(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("t1", {"notes": []})
    update_ticket(ticket_id="t1", new_stage="RESOLVED", resolution="Reset password worked", memory=mem)
    assert mem.get_entity_state("t1")["resolution"] == "Reset password worked"


def test_update_ticket_recovers_corrupted_notes(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("t1", {"notes": "corrupted"})
    update_ticket(ticket_id="t1", new_stage="IN_PROGRESS", notes="clean", memory=mem)
    assert isinstance(mem.get_entity_state("t1")["notes"], list)


# ── Tool: escalate_ticket ─────────────────────────────────────────────────────

def test_escalate_ticket_without_memory():
    result = escalate_ticket(ticket_id="t1", reason="requires DB access")
    assert result["escalated"] is True
    assert result["ticket_id"] == "t1"


def test_escalate_ticket_persists_to_memory(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("t1", {"notes": [], "stage": "IN_PROGRESS"})
    escalate_ticket(ticket_id="t1", reason="data corruption suspected",
                    urgency="critical", assign_to="senior-eng", memory=mem)
    state = mem.get_entity_state("t1")
    assert state["stage"] == "ESCALATED"
    assert state["escalation_urgency"] == "critical"
    assert state["assign_to"] == "senior-eng"
    assert any("ESCALATED" in n for n in state["notes"])


def test_escalate_ticket_default_urgency():
    result = escalate_ticket(ticket_id="t1", reason="complex issue")
    assert result["urgency"] == "medium"


# ── SupportAgent ──────────────────────────────────────────────────────────────

def test_agent_initial_state(agent):
    state = agent.initial_entity_state()
    assert state["stage"] == "OPEN"
    assert state["interactions"] == 0
    assert state["notes"] == []
    assert state["priority"] == "medium"
    assert state["escalated"] is False


def test_agent_system_prompt_defaults(agent):
    ctx = SupportPipeline().get_context("OPEN")
    cfg = TenantConfig(tenant_id="test")
    prompt = agent.build_system_prompt(cfg, ctx)
    assert "Sam" in prompt
    assert "Acme Corp" in prompt
    assert "OPEN" in prompt
    assert "Objective" in prompt


def test_agent_system_prompt_tenant_override(agent):
    ctx = SupportPipeline().get_context("IN_PROGRESS")
    cfg = TenantConfig(
        tenant_id="t1",
        meta={
            "agent_name": "Jordan", "company": "TechCo",
            "product_description": "cloud storage platform",
            "support_scope": "technical and billing",
            "language": "en",
        },
    )
    prompt = agent.build_system_prompt(cfg, ctx)
    assert "Jordan" in prompt
    assert "TechCo" in prompt
    assert "Sam" not in prompt


def test_agent_system_prompt_contains_stage_context(agent):
    sm = SupportPipeline()
    for stage in ["OPEN", "TRIAGING", "IN_PROGRESS", "ESCALATED"]:
        ctx = sm.get_context(stage)
        cfg = TenantConfig(tenant_id="test")
        prompt = agent.build_system_prompt(cfg, ctx)
        assert stage in prompt
        assert ctx.objective in prompt


def test_agent_tools_have_required_fields(agent):
    for tool in agent.get_tools():
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_agent_tool_map_complete(agent):
    expected = {"triage_ticket", "search_knowledge_base", "update_ticket", "escalate_ticket"}
    assert set(agent.get_tool_map().keys()) == expected


def test_agent_tool_map_all_callable(agent):
    for name, fn in agent.get_tool_map().items():
        assert callable(fn), f"Tool '{name}' is not callable"
