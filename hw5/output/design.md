# Campus Customs Desk: dashboard design

Decisions about how the board (`frontend/`, React + Vite + TypeScript) looks and why. It talks to the FastAPI backend at `http://localhost:8000`. The backend allows the Vite origin `http://localhost:5173`. Start it with `npm run dev` from `frontend/`.

## The idea: a desk, not a log viewer
The board should feel like a shop's back office: a place where someone sits, hands work to the team, watches it happen, and signs off on money. Everything on screen answers one of three questions: **what needs doing** (tickets), **what is the team doing about it** (the agent floor), and **what needs me** (approvals and cash).

## Layout
- **Header bar (navy with a gold rule):**
  - The shop name and a "CC" mark.
  - The **shop date** (Aug 31, 2026), shown because every due date is measured from it.
  - The **checking balance**, the most important number in the shop.
  - **Reset shop**, set apart on the right because it undoes everything.
- **Three columns, read left to right in the order of the work:**
  1. **Tickets** (left): one card per ticket, with type, requester, item or linked lease/invoice, a state badge, and the **Activate Ops Team** button (**Reactivate Ops Team** after a run). A progress bar at the top counts resolved tickets.
  2. **The agent floor** (center): the selected ticket's request in the requester's own words. Below it, **five agent tiles**, then a **Live / Summary** switch.
  3. **Approvals and cash** (right): the "Approving as" name, the pending payments, decided ones, and a cash ledger.
- On narrower screens the right column drops below the other two; on a phone everything stacks.

## Agents are played by Yale's officers
Each agent is shown as the Yale officer whose job best matches it, according to Yale's 2026–27 list of university officers. Each one has a cartoon portrait, their name, and the agent's role as a subtitle.

| Agent | Played by | Why this person |
|---|---|---|
| Boss | **Maurie McInnis**, President | The president leads the university and makes the final calls, like the Boss. |
| Inventory | **Geoffrey Chatas**, Senior Vice President for Operations | Operations runs the university's supply side (procurement, purchasing, campus services), the closest match to stock and restocking. |
| Accounting | **Katrina Spencer**, Vice President for Finance, CFO & Treasurer | Cash, bills, and payments are the CFO's job. |
| Facilities | **Mike Bellamy**, Vice President for Facilities, Campus Development & Sustainability | He runs Yale's buildings and space, like the shop's lease and rent. |
| Customer Service | **Renee Kopkowski**, Vice President for Communications | Communications speaks for the university, like the agent that drafts replies. |

- **Portraits:**
  - Friendly cartoons drawn in SVG code (`frontend/src/components/Portrait.tsx`). Each one follows the person's official Yale headshot: hair, coloring, glasses, earrings, and what they wear.
  - No photos are stored in the project or shipped with the board.
  - Each portrait sits in a ring of that agent's color and bobs gently while the agent is working.
- **Tiles:** the person's name in Yale New, the role (BOSS, INVENTORY, …) as an Oswald subtitle in the agent's color, their real title underneath, then the live state, tool count, and current action.
- **Elsewhere:** in the timeline and summary, each line shows the small portrait, the person's name, and the role in small caps. Waiting messages use names, e.g. "Waiting on Katrina Spencer".
- **The agent colors stay** (Boss Yale Blue, Inventory green, Accounting gold, Facilities purple, Customer Service rose), so you can still tell at a glance who is talking.

### The team resizes with the window
The five tiles size themselves to the width of the center column, not the whole window:
- **Wide (most laptop and desktop windows):** five across.
- **Medium:** 3 + 2.
- **Narrow (phone):** 2 + 2 + 1.

The tiles stack the portrait above the name, so five fit side by side without cutting off names. Long titles are trimmed to two lines, with the full text on hover. On narrow windows the header also rearranges, so the date, balance, and Reset button stay on screen.

## Live view: watch the work happen
A timeline built from the audit-trail events, refreshed about once a second while a run is going:
- Delegations read as sentences, "Boss **asks** Facilities", with the exact task underneath.
- Tool calls show a friendly label chip ("Check stock") next to the real call (`check_stock(sku=…, size=…)`). The raw result opens on click, so the screen stays calm but every number can be checked.
- Anything an agent says is shown in a speech bubble (markdown rendered).
- Items are indented by delegation depth, so a specialist asking another specialist is visibly nested.
- The end of a run shows its cost: model calls, tokens, tool calls, handoffs.
- Refused handoffs, blocked tools and errors are shown in red.

## Summary view: what each agent did
When a run finishes, the board switches to Summary on its own and shows a toast.
- **The Boss's decision**, with a gold edge: the decision, the reasoning, the ticket status (e.g. "Awaiting approval"), anything left for a human, and any **customer drafts**. Drafts are labeled **"Draft, not sent"**, since the shop never emails anyone.
- **One card per agent that worked:** who asked it, who it asked, which tools it used (×count), and its answer.

## Money: the human is the only one who pays
- Pending payments appear as cards in the right column (amber edge, sliding in). Each card shows:
  - the amount in large type and the payee
  - the agent's reason and which agent prepared it
  - **"Checking after"**, so the approver sees the effect before clicking. It turns red with "will be refused" if there isn't enough cash.
- **Approve & pay** (green) and **Reject** (outline). Rejecting is deliberately quieter than approving, but just as easy to reach.
- Approvals are signed: the board won't approve until a name is typed in "Approving as". The name is remembered between visits and goes to the backend, the `payments` table, and the audit trail.
- **Live cash:** the header balance counts down to its new value, the box flashes red (or green after a reset), and a "−$2,400.00" marker appears. A small sparkline traces the balance over the session. The ledger lists each change with what caused it and who approved it.

## States, and when a ticket counts as "resolved"
- Tickets are **Open**, then **Agents working** (pulsing amber), then **Resolved** (green).
- A ticket is marked resolved **when the team's run on it finishes**, as the assignment asks. The finer status from the database (e.g. "Awaiting approval", "Needs a human") and "1 to approve" stay visible next to the badge, so "resolved" never hides that money is still waiting.
- After a reset, earlier runs no longer count, so all tickets show Open again.
- **One ticket runs at a time.** Start buttons are disabled while the team is busy, which keeps token use predictable and avoids two runs competing for the same cash. Reset is disabled during a run.

## Look and feel: the Campus Customs brand from HW4
The board uses the same identity as the HW4 Campus Customs storefront, so the shop's back office and its storefront look like one business.
- **Marks:** the header carries the same crest (a white athletic "Y" on Yale Blue inside a white ring) and the stacked **YALE / BULLDOG BLUE / By Campus Customs** wordmark as the storefront. The board's own title, "Operations Desk", sits beside it after a thin divider. The browser tab icon is the crest.
- **Type:**
  - **Yale New** for the wordmark, headings, ticket titles, agent names, the Boss's decision, and every money figure (balance, payment amounts), because money and decisions are what matter most on this desk.
  - **Oswald** caps for labels: column headings, badges, agent states, tabs, the shop date label.
  - **Inter** for everything you read at length.
- **Palette:**
  - Yale Blue `#00356b` (header, buttons, the Boss), deep navy `#00224a` (headings), and a lighter blue `#286dc0` (eyebrows, accents), on warm ivory `#faf8f3` with white cards. These are the same values as HW4.
  - Money and status colors stay separate from the brand: green for paid or resolved, amber for pending or running, red for refused or problems.
  - Buttons are pill-shaped as on the storefront: solid Yale Blue, with white for Reset in the header.
- **The agents keep their own colors** (Boss in Yale Blue; Inventory green, Accounting gold, Facilities purple, Customer Service rose), so you can still tell at a glance who is talking.
- **Licensed artwork stays out of the public repo:** the Yale New font files (`frontend/public/fonts/`) and the wordmark images (`frontend/public/brand/`) are in `.gitignore`, as in HW4. Without them the board still works: headings fall back to Libre Caslon / Georgia, and the wordmark is set in regular fonts.
- **Motion** is only used where something changed: the cash count-down and flash, pulsing "working" dots, cards sliding in, and a typing indicator while agents think.
- **If the backend isn't running**, a banner says so and shows the command to start it.
