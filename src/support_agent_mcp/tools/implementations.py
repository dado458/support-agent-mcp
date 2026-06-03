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


def search_knowledge_base(query: str, category: str = "general") -> dict:
    return {
        "query":    query,
        "category": category,
        "hint": (
            "No exact match found — use your training to synthesize a solution. "
            "If the issue is complex or undocumented, consider escalation."
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
        state = memory.get_entity_state(ticket_id)
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
                    assign_to: str = "", memory=None) -> dict:
    if memory:
        state = memory.get_entity_state(ticket_id)
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
    return {
        "ticket_id": ticket_id,
        "escalated": True,
        "urgency":   urgency,
        "assign_to": assign_to,
    }
