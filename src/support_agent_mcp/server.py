"""
Entry point — run as MCP server via stdio.

Install:  pip install support-agent-mcp
Run:      support-agent-mcp
Config:
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
"""
import os

from edge_llm.core.mcp_server import BaseEdgeMCPServer
from edge_llm.core.memory.local import LocalMemoryStore
from edge_llm.core.memory.redis_store import RedisMemoryStore
from edge_llm.core.tenants.local import LocalTenantStore
from edge_llm.core.usage.local import LocalUsageTracker
from edge_llm.core.agent import EdgeAgent

from .agent import SupportAgent


class SupportMCPServer(BaseEdgeMCPServer):

    SERVER_NAME    = "support-agent"
    SERVER_VERSION = "0.1.0"

    def create_memory(self):
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            return RedisMemoryStore(redis_url)
        return LocalMemoryStore(os.getenv("MEMORY_DIR", "data/memory"))

    def create_tenants(self):
        return LocalTenantStore(os.getenv("TENANTS_PATH", "data/tenants.json"))

    def create_tracker(self):
        return LocalUsageTracker(os.getenv("USAGE_DIR", "data/usage"))

    def create_agent(self) -> EdgeAgent:
        self._kb_store = self._create_kb_store()
        return SupportAgent(
            memory=self._memory,
            tenants=self._tenants,
            tracker=self._tracker,
            kb_store=self._kb_store,
            model=os.getenv("SUPPORT_MODEL", "claude-opus-4-8"),
        )

    def _create_kb_store(self):
        """Optional ChromaDB-backed knowledge base. Requires: pip install chromadb."""
        kb_dir = os.getenv("KB_DIR")
        if not kb_dir:
            return None
        from edge_llm.core.catalog import ChromaCatalogStore
        return ChromaCatalogStore(persist_dir=kb_dir)

    def extra_tools(self) -> list:
        if self._kb_store is None:
            return []
        from mcp.types import Tool
        return [
            (
                Tool(
                    name="upsert_kb_article",
                    description=(
                        "Add or update a knowledge base article for semantic search by "
                        "search_knowledge_base. Content is chunked on markdown headers."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tenant_id": {"type": "string"},
                            "content":   {"type": "string", "description": "Markdown content of the article"},
                        },
                        "required": ["tenant_id", "content"],
                    },
                ),
                self._upsert_kb_article,
            ),
        ]

    def _upsert_kb_article(self, args: dict) -> dict:
        from edge_llm.core.catalog import chunk_markdown
        tenant_id = args["tenant_id"]
        pairs     = chunk_markdown(args["content"])
        ids       = [p[0] for p in pairs]
        documents = [p[1] for p in pairs]
        if not documents:
            return {"tenant_id": tenant_id, "chunks_stored": 0, "error": "content produced zero chunks"}
        stored = self._kb_store.upsert(tenant_id, documents=documents, ids=ids)
        return {"tenant_id": tenant_id, "chunks_stored": stored}


def main():
    SupportMCPServer().run()


if __name__ == "__main__":
    main()
