from edge_llm.core.state_machine import StateMachine, StageContext


class SupportPipeline(StateMachine):
    stages = ["OPEN", "TRIAGING", "IN_PROGRESS", "WAITING_CUSTOMER", "ESCALATED", "RESOLVED", "CLOSED"]
    terminal_stages = ["RESOLVED", "CLOSED"]
    transitions = {
        "OPEN":             ["TRIAGING", "CLOSED"],
        "TRIAGING":         ["IN_PROGRESS", "ESCALATED", "CLOSED"],
        "IN_PROGRESS":      ["WAITING_CUSTOMER", "ESCALATED", "RESOLVED", "CLOSED"],
        "WAITING_CUSTOMER": ["IN_PROGRESS", "RESOLVED", "CLOSED"],
        "ESCALATED":        ["IN_PROGRESS", "RESOLVED", "CLOSED"],
        "RESOLVED":         ["CLOSED"],
        "CLOSED":           [],
    }
    _context_map = {
        "OPEN": StageContext(
            stage="OPEN",
            objective="Acknowledge the ticket and begin triage immediately.",
            recommended_tools=["triage_ticket"],
            possible_next_stages=["TRIAGING", "CLOSED"],
        ),
        "TRIAGING": StageContext(
            stage="TRIAGING",
            objective="Classify severity, type, and owner. Decide if escalation is needed.",
            recommended_tools=["triage_ticket", "search_knowledge_base"],
            possible_next_stages=["IN_PROGRESS", "ESCALATED", "CLOSED"],
        ),
        "IN_PROGRESS": StageContext(
            stage="IN_PROGRESS",
            objective="Work toward resolution. Ask clarifying questions if needed.",
            recommended_tools=["search_knowledge_base", "update_ticket"],
            possible_next_stages=["WAITING_CUSTOMER", "ESCALATED", "RESOLVED", "CLOSED"],
        ),
        "WAITING_CUSTOMER": StageContext(
            stage="WAITING_CUSTOMER",
            objective="Waiting for customer response. Re-engage if silent too long.",
            recommended_tools=["update_ticket"],
            possible_next_stages=["IN_PROGRESS", "RESOLVED", "CLOSED"],
        ),
        "ESCALATED": StageContext(
            stage="ESCALATED",
            objective="Issue requires senior/human intervention. Document clearly and hand off.",
            recommended_tools=["escalate_ticket", "update_ticket"],
            possible_next_stages=["IN_PROGRESS", "RESOLVED", "CLOSED"],
        ),
        "RESOLVED": StageContext(
            stage="RESOLVED",
            objective="Confirm resolution with the customer and close if accepted.",
            recommended_tools=["update_ticket"],
            possible_next_stages=["CLOSED"],
        ),
        "CLOSED": StageContext(
            stage="CLOSED",
            objective="Ticket is closed. Archive and log learnings.",
            recommended_tools=["update_ticket"],
            possible_next_stages=[],
        ),
    }
