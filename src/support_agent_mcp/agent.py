from pathlib import Path
from typing import Optional

from edge_llm.core.agent import EdgeAgent
from edge_llm.core.catalog import AbstractCatalogStore
from edge_llm.core.state_machine import StateMachine, StageContext
from edge_llm.core.tenants.base import TenantConfig

from .pipeline import SupportPipeline
from .tools.definitions import SUPPORT_TOOLS
from .tools.implementations import triage_ticket, search_knowledge_base, update_ticket, escalate_ticket

_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")

_DEFAULT_META = {
    "agent_name":          "Sam",
    "company":             "Acme Corp",
    "product_description": "a SaaS platform used by teams to manage their work",
    "support_scope":       "technical issues, billing questions, onboarding, and general inquiries",
    "language":            "en",
}


class SupportAgent(EdgeAgent):

    def __init__(self, *args, kb_store: Optional[AbstractCatalogStore] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._kb_store = kb_store

    def get_state_machine(self) -> StateMachine:
        return SupportPipeline()

    def build_system_prompt(self, tenant_cfg: TenantConfig, stage_ctx: StageContext) -> str:
        m = {**_DEFAULT_META, **tenant_cfg.meta}
        base = _PROMPT_TEMPLATE.format(**m)
        return (
            f"{base}\n\n"
            f"# Current ticket state\n"
            f"- Stage: {stage_ctx.stage}\n"
            f"- Objective now: {stage_ctx.objective}\n"
            f"- Recommended tools: {', '.join(stage_ctx.recommended_tools)}\n"
            f"- Possible next stages: {', '.join(stage_ctx.possible_next_stages)}\n"
        )

    def get_tools(self) -> list[dict]:
        return SUPPORT_TOOLS

    def get_tool_map(self, tenant_id: str = "") -> dict[str, callable]:
        mem      = self._memory
        kb_store = self._kb_store
        # Resolve per-tenant config from meta (keyword KB text fallback, escalation webhook).
        kb_text            = ""
        escalation_webhook = None
        if tenant_id:
            try:
                meta = self._tenants.get(tenant_id).meta
                kb_text = meta.get("knowledge_base", "")
                webhook_url = meta.get("escalation_webhook_url", "")
                if webhook_url:
                    from edge_llm.core.integrations import WebhookClient
                    escalation_webhook = WebhookClient(webhook_url)
            except KeyError:
                pass
        return {
            "triage_ticket": lambda **kw: triage_ticket(**kw),
            "search_knowledge_base": lambda **kw: search_knowledge_base(
                **kw,
                kb_store=kb_store,
                kb_text=kb_text,
                tenant_id=tenant_id,
            ),
            "update_ticket":   lambda **kw: update_ticket(**kw, memory=mem),
            "escalate_ticket": lambda **kw: escalate_ticket(**kw, memory=mem, webhook=escalation_webhook),
        }

    def initial_entity_state(self) -> dict:
        return {
            "stage":       "OPEN",
            "interactions": 0,
            "notes":       [],
            "priority":    "medium",
            "escalated":   False,
        }
