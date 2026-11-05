"""Model, MCP connection, and limits for the Campus Customs agent team.

- MODEL_NAME is always gpt-6-luna (shop rule: every agent uses it, through Portkey)
- build_model(): one shared OpenAIResponsesModel (Azure's gpt-6-luna needs the Responses API for tools)
- build_mcp_toolset(): the agents' only way to shop facts: the FastMCP server in mcp_server/, over stdio
- Limits: how deep delegation can go, how many delegations a ticket may use, per-agent request caps
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai.mcp import MCPToolset, ProcessToolCallback
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

ROOT = Path(__file__).resolve().parents[2]  # HW5/
PROMPTS_DIR = ROOT / "backend" / "prompts"
MCP_SERVER = ROOT / "mcp_server" / "server.py"
for folder in (ROOT, ROOT.parent):  # HW5/.env, else the course folder's .env
    load_dotenv(folder / ".env")

MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").strip()

# Limits that keep token use (and runaway loops) in check
MAX_DEPTH = 2  # Boss (0) -> specialist (1) -> specialist (2); no deeper
MAX_DELEGATIONS = 8  # per ticket, across the whole team
MAX_TICKET_TOKENS = 250_000  # input + output tokens per ticket, across the whole team
MAX_TICKET_TOOL_CALLS = 40  # MCP calls per ticket, across the whole team
TOOL_RESULT_CHARS = 4_000  # longest tool result kept in the audit trail
BOSS_LIMITS = UsageLimits(request_limit=16, tool_calls_limit=20, total_tokens_limit=120_000)
SPECIALIST_LIMITS = UsageLimits(request_limit=8, tool_calls_limit=10, total_tokens_limit=60_000)


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Put it in HW5/.env (see .env.example).")
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    key = require_api_key()
    client = AsyncOpenAI(api_key=key, base_url=PORTKEY_BASE_URL, default_headers={"x-portkey-api-key": key})
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def build_mcp_toolset(process_tool_call: ProcessToolCallback | None = None) -> MCPToolset:
    """Starts mcp_server/server.py as a subprocess (stdio) when first entered; shared by all five agents."""
    transport = StdioTransport(command=sys.executable, args=[str(MCP_SERVER)], cwd=str(ROOT))
    return MCPToolset(Client(transport), id="campus-customs", process_tool_call=process_tool_call)
