# Campus Customs Multi-Agent Operations (MGT 409, HW5)

A team of five PydanticAI agents runs the Campus Customs ticket desk:
- **Boss:** reads each ticket, decides who works on it, and makes the final call.
- **Inventory:** stock, shortfalls, and which vendor can restock.
- **Accounting:** cash, invoices, margins, and preparing payments for a human to approve.
- **Facilities:** the lease and rent.
- **Customer Service:** drafts replies to customers. Drafts are never sent.

Every agent uses **gpt-6-luna through Portkey**. Shop facts come only from an **MCP server** over the working copy of the shop database. A **FastAPI backend** runs the team, and a **React board** lets a person watch the agents work and approve payments. Only a person can approve a payment, and no payment can make the balance negative.

## What's here

| Path | What it is |
|---|---|
| `data/campus_customs.db` | The **original** shop database. Never written to; used to reset. |
| `data/campus_customs_new.db` | The **working copy** that the MCP server reads and updates. It's committed in the state left by the graded run (checking $160). |
| `mcp_server/server.py` | FastMCP server: 15 tools over the working copy (see `mcp_server/README.md`). |
| `.mcp.json` | Connects a vibe coder (e.g. Claude Code) to the MCP server. |
| `backend/` | `main.py` (FastAPI routes), `models.py` (data types), `agents/` (team loop, config), `prompts/` (one prompt per agent), `audit.py` (audit trail). |
| `frontend/` | The React + Vite + TypeScript board. |
| `output/` | `harness.md` (how everything works), `mcp_smoke.json`, `desk_tickets.html` (Expected / Actual / Cash / Reflection), `design.md`, `resolved_tickets.json`, `resolved_board.html`, `audit_trail.json`, `github_url.txt`. |
| `AI_prompts.md` | The log of what I typed to my vibe coder. |

## Setup (once)

You need Python 3.12+ and Node 20+. Run these from this folder (`hw5/`):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then put your own PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

## 1. Copy the original database to the working copy (for a clean run)

The MCP server and backend only use `data/campus_customs_new.db`, and the agents' approved payments change it. To start over from the original shop data, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The original `data/campus_customs.db` is never changed. "Today" for the shop is `desk.date_today` (2026-08-31), and checking starts at $3,400.

## 2. Start the MCP server

The server talks over stdio, so a client starts it as a subprocess:

- **The backend starts it automatically.** It opens one connection for its routes and one per ticket run for the agents, so you don't need a separate terminal for it.
- **To use the tools from a vibe coder** (Claude Code), open this folder; `.mcp.json` registers the server as `campus-customs`.
- **To run it by hand** (e.g. to check that it starts):

  ```bash
  .venv/bin/python mcp_server/server.py
  ```

## 3. Start the FastAPI backend

From `backend/`:

```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

The backend runs at http://localhost:8000, with interactive docs at http://localhost:8000/docs. Its routes:
- `GET /tickets`, `POST /tickets/{id}/run`, `GET /events`
- `GET /payments`, `POST /payments/{id}/approve`, `POST /payments/{id}/reject`
- `GET /cash`, `POST /reset`

## 4. Start the React board

In a second terminal, from `frontend/`:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. Then:
1. Pick a ticket and press **Activate Ops Team**.
2. Watch the agents in the **Live** tab, and read the **Summary** when the run finishes.
3. Type your name in **Approving as**, then **Approve & pay** or **Reject** each payment. Checking updates live.

## 5. Reset the database before a full three-ticket run

Before running all three tickets (101, 102, 103) from a clean start, reset the shop. Either:
- press **Reset shop** on the board,
- run `curl -X POST http://localhost:8000/reset`, or
- with the backend stopped, run the `cp` command from step 1.

Resetting copies the original database over the working copy. The audit trail (`output/audit_trail.json`) is kept: it only grows. Then run 101, 102 and 103 one at a time, approving payments as they appear.

## Notes

- **Secrets:** the real `.env` is not in the repository (`.gitignore`); `.env.example` has placeholders only.
- **Yale fonts and wordmark:** the Yale New font files and the wordmark images (`frontend/public/fonts/`, `frontend/public/brand/`) are licensed and not included. Without them the board uses Libre Caslon / Georgia and a text wordmark. The officer cartoons are drawn in code (`frontend/src/components/Portrait.tsx`).
- **How it all works:** the tables, MCP tools, agents, routes, dashboard, and safety rules are described in `output/harness.md`.
