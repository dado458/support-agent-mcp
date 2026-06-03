# support-agent-mcp

> **⚠️ ALPHA SOFTWARE — FOR DEVELOPMENT USE ONLY — v0.1.0**
>
> This package is intended for **development, prototyping, and research purposes only**.
> It is not a finished commercial product and is not suitable for production use without significant additional hardening.
>
> - APIs may change without notice between minor versions in the 0.x series.
> - This package has not been audited for security. Do not use it to store or process real customer data
>   without your own thorough security and compliance review.
> - All LLM calls consume Anthropic API credits. Costs are your responsibility — monitor usage actively.
> - LLM outputs are non-deterministic. The agent may produce incorrect or incomplete responses.
>   Do not rely on agent output for consequential decisions without human review.
> - **The authors accept no responsibility for any costs, data loss, security breaches, compliance violations,
>   or damages of any kind arising from the use or misuse of this software.**
> - Use entirely at your own risk.

**Autonomous support ticket agent MCP server — stateful, multi-tenant, built on [edge-llm-core](https://pypi.org/project/edge-llm-core/).**

`support-agent-mcp` implements the *Edge LLM Pattern*: an MCP server with its own internal Claude loop, a support ticket state machine, persistent memory per ticket, and multi-tenant configuration.

## Install

```bash
pip install support-agent-mcp
```

## Quick start

### 1. Add to Claude config

**macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows** — `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "support": {
      "command": "uvx",
      "args": ["support-agent-mcp"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "SUPPORT_TENANT_ID": "my-company"
      }
    }
  }
}
```

### 2. Register a tenant

```python
from edge_llm.core.tenants.local import LocalTenantStore

store = LocalTenantStore("data/tenants.json")
store.register(
    "my-company",
    name="Acme Corp",
    plan="pro",
    meta={
        "agent_name":          "Sam",
        "company":             "Acme Corp",
        "product_description": "cloud storage platform for teams",
        "support_scope":       "technical issues, billing, onboarding",
        "language":            "en",
    },
)
```

### 3. Use from Claude

```
Send this message to the support agent for ticket "ticket-42":
"I can't log in — it says my account is locked"
```

Claude calls `handle_message` → the agent triages, classifies severity, and responds autonomously.

## Ticket pipeline

```
OPEN -> TRIAGING -> IN_PROGRESS -> WAITING_CUSTOMER -> RESOLVED -> CLOSED
                        |                                  |
                        +-----------> ESCALATED -----------+
```

| Stage | Objective |
|---|---|
| OPEN | Acknowledge and begin triage immediately. |
| TRIAGING | Classify severity, type, and priority. |
| IN_PROGRESS | Work toward resolution, ask clarifying questions. |
| WAITING_CUSTOMER | Waiting for customer response. |
| ESCALATED | Needs human/senior intervention — document and hand off. |
| RESOLVED | Solution provided — confirm with customer. |
| CLOSED | Final state — archive and log learnings. |

## MCP tools exposed

| Tool | Description |
|---|---|
| `handle_message` | Send a message → runs full internal agent loop → returns reply |
| `get_entity_state` | Current ticket stage + metadata |
| `get_conversation` | Message history (last N messages) |
| `set_entity_stage` | Manually advance or reset the ticket stage |
| `add_note` | Attach internal note without triggering the loop |
| `get_usage` | Monthly calls, tokens, cost for a tenant |
| `list_entities` | All active tickets in memory |

## Domain-specific tools (internal agent loop)

| Tool | Description |
|---|---|
| `triage_ticket` | Classify severity, priority, and category from the message |
| `search_knowledge_base` | Search for known solutions (returns strategy hints) |
| `update_ticket` | Update stage, priority, notes, and resolution |
| `escalate_ticket` | Mark ticket for escalation with reason and urgency |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Anthropic API key |
| `SUPPORT_MODEL` | `claude-opus-4-8` | Model for the internal agent loop |
| `REDIS_URL` | — | If set, uses Redis for memory (production) |
| `MEMORY_DIR` | `data/memory` | Local memory directory (dev) |
| `TENANTS_PATH` | `data/tenants.json` | Local tenant store path (dev) |
| `USAGE_DIR` | `data/usage` | Local usage tracking directory (dev) |

## Known limitations

| Limitation | Detail |
|---|---|
| **No API retry** | Anthropic API errors propagate uncaught. Wrap calls with retry logic at the integration layer. |
| **Reply length capped at 1 024 tokens** | Long agent replies will be silently truncated. Subclass `SupportAgent` to override. |
| **`search_knowledge_base` is a stub** | Returns strategy hints only — it does not connect to a real knowledge base. Implement your own by overriding the tool in a subclass. |
| **Local memory not thread-safe** | Use `REDIS_URL` for production or multi-instance deployments. |

## License

Apache 2.0 — free for commercial use, attribution required.
