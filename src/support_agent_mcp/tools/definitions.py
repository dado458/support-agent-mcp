SUPPORT_TOOLS = [
    {
        "name": "triage_ticket",
        "description": "Analyze the ticket message to classify severity, type, and suggested priority.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message":       {"type": "string", "description": "The customer's message"},
                "current_stage": {"type": "string", "description": "Current ticket stage"},
                "history_summary": {"type": "string", "description": "Brief summary of prior context"},
            },
            "required": ["message", "current_stage"],
        },
    },
    {
        "name": "search_knowledge_base",
        "description": "Search for known solutions or documentation relevant to the issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query":    {"type": "string", "description": "Search terms describing the problem"},
                "category": {"type": "string", "description": "Issue category (bug, billing, setup, feature)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "update_ticket",
        "description": "Update the ticket stage, priority, and internal notes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id":  {"type": "string"},
                "new_stage":  {"type": "string", "description": "New pipeline stage"},
                "priority":   {"type": "string", "description": "low | medium | high | critical"},
                "notes":      {"type": "string", "description": "Internal notes to append"},
                "resolution": {"type": "string", "description": "Resolution summary (when closing)"},
            },
            "required": ["ticket_id", "new_stage"],
        },
    },
    {
        "name": "escalate_ticket",
        "description": "Mark the ticket for human escalation with a reason and urgency level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "reason":    {"type": "string", "description": "Why escalation is needed"},
                "urgency":   {"type": "string", "description": "low | medium | high | critical", "default": "medium"},
                "assign_to": {"type": "string", "description": "Team or person to escalate to"},
            },
            "required": ["ticket_id", "reason"],
        },
    },
]
