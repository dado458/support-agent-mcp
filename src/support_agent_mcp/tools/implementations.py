"""
Domain tool implementations for SupportAgent internal loop.
These are called by EdgeAgent._execute_tools — not exposed via MCP.
"""


def triage_ticket(message: str, current_stage: str, history_summary: str = "") -> dict:
    msg = message.lower()
    critical_signals = ["down", "outage", "cannot login", "data loss", "urgent", "production", "broken"]
    high_signals     = ["error", "fail", "crash", "not working", "bug", "blocked"]
    billing_signals  = ["invoice", "charge", "refund", "billing", "payment", "subscription"]

    if any(w in msg for w in critical_signals):
        severity, priority = "critical", "critical"
        hint = "Potential outage or data loss — consider immediate escalation."
    elif any(w in msg for w in high_signals):
        severity, priority = "high", "high"
        hint = "Functional issue — prioritize resolution, search knowledge base first."
    elif any(w in msg for w in billing_signals):
        severity, priority = "medium", "medium"
        hint = "Billing issue — handle with care, may need finance team involvement."
    else:
        severity, priority = "low", "low"
        hint = "General inquiry — resolve with standard support flow."

    category = "billing" if any(w in msg for w in billing_signals) else "technical"

    return {
        "current_stage":   current_stage,
        "severity":        severity,
        "priority":        priority,
        "category":        category,
        "message_preview": message[:120],
        "hint":            hint,
    }


def search_knowledge_base(
    query: str,
    category: str = "general",
    kb_store=None,
    kb_text: str = "",
    tenant_id: str = "",
) -> dict:
    """
    Search the support knowledge base for articles relevant to the query.

    Priority:
    1. Vector search via ChromaCatalogStore (semantic, if configured and has data).
    2. Keyword search over KB text in tenant meta (fast fallback, no embeddings).
    3. No-data hint telling the agent to fall back to its own training and
       consider escalation — this is the genuine last resort, not the default.
    """
    # 1 — vector search
    if kb_store is not None and tenant_id:
        try:
            if kb_store.count(tenant_id) > 0:
                results = kb_store.search(tenant_id, query, n_results=3)
                if results:
                    return {"query": query, "category": category, "results": results, "source": "vector"}
        except Exception:
            pass  # fall through to keyword search

    # 2 — keyword search over meta KB text
    if kb_text and kb_text.strip():
        import re
        query_terms = set(query.lower().split())
        chunks = [c.strip() for c in re.split(r"\n{2,}|(?=#{1,3} )", kb_text, flags=re.MULTILINE) if c.strip()]
        scored = sorted(
            ((len(set(c.lower().split()) & query_terms), c) for c in chunks),
            reverse=True,
        )
        top = [c for _, c in scored[:3] if _ > 0]
        if top:
            return {"query": query, "category": category, "results": top, "source": "keyword"}

    # 3 — nothing available
    return {
        "query":    query,
        "category": category,
        "results":  [],
        "hint": (
            "No knowledge base configured or no match found — use your training to "
            "synthesize a solution. If the issue is complex or undocumented, consider escalation."
        ),
        "suggested_approach": (
            "1. Reproduce the issue if possible. "
            "2. Check recent changelog for known regressions. "
            "3. Ask the customer for logs or screenshots if needed."
        ),
    }


def update_ticket(ticket_id: str, new_stage: str, priority: str = "",
                  notes: str = "", resolution: str = "", memory=None) -> dict:
    if memory:
        state = memory.get_entity_state(ticket_id) or {}
        existing_notes = state.get("notes", [])
        if not isinstance(existing_notes, list):
            existing_notes = []
        if notes:
            existing_notes.append(notes)
        update = {"stage": new_stage, "notes": existing_notes}
        if priority:
            update["priority"] = priority
        if resolution:
            update["resolution"] = resolution
        memory.update_entity_state(ticket_id, **update)
    return {"ticket_id": ticket_id, "stage": new_stage, "updated": True}


def escalate_ticket(ticket_id: str, reason: str, urgency: str = "medium",
                    assign_to: str = "", memory=None, webhook=None) -> dict:
    if memory:
        state = memory.get_entity_state(ticket_id) or {}
        existing_notes = state.get("notes", [])
        if not isinstance(existing_notes, list):
            existing_notes = []
        existing_notes.append(f"ESCALATED: {reason}")
        memory.update_entity_state(
            ticket_id,
            stage="ESCALATED",
            escalation_reason=reason,
            escalation_urgency=urgency,
            assign_to=assign_to,
            notes=existing_notes,
        )

    if webhook:
        webhook.post({
            "text": (
                f":rotating_light: Ticket `{ticket_id}` escalated "
                f"(urgency: {urgency}) — {reason}"
                + (f" → assigned to {assign_to}" if assign_to else "")
            ),
            "event":     "ticket_escalated",
            "ticket_id": ticket_id,
            "reason":    reason,
            "urgency":   urgency,
            "assign_to": assign_to,
        })

    return {
        "ticket_id": ticket_id,
        "escalated": True,
        "urgency":   urgency,
        "assign_to": assign_to,
    }
