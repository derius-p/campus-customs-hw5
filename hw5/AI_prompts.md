# AI Prompts: HW5 (Campus Customs Multi-Agent Operations)

## Problem 1: Vibe coder prompts

**Prompt:**

> Problem 1: create AI_prompts.md and log my prompts

**Setup prompts:**

> ok we are going to work on HW5 now. Please create a HW5 folder inside the MGT409_PTM folder and put all the work in there. https://zlisto.github.io/mgt_409_fa26/hw5/p1.html is the website describing the homework that we will follow. I'll give instructions about each sub-part

> it's there

## Problem 2: Study the Campus Customs database

**Prompt:**

> ok - you already did the second part of problem 1, which like the first part matches previous assignments we have done. Problem 2: Study the Campus Customs Database. Open the database and look at each table and its fields. Tell me about the three open tickets so I can understand how they link to the other tables. Go ahead and make the working (_new) version we will work in

**Second prompt:**

> start output/harness.md for problem 2 listing the fields or each table and one short line on why the table matters for the agents

**Follow-up:**

> how do you know the tickets are "open"

*What was lacking:* I did not see 'status' listed and wasn't sure where it was noted that the tickets were open so I asked the AI to tell me how it knew

## Problem 3: Build the MCP server

**Prompt:**

> Problem 3: build the MCP server. Write an MCP serve in mcp_server/ using FastMCP. The server will communicate with the _new version of the database. Start with three tools that you know you will need for the tools in the database and we will add more later. No need to connect or run it yet

**Second prompt:**

> add the three tools to harness.md and write the mcp_server README that explains what the MCP server is for, what database file it connects with, and the three tools it has. in harness.md make sure you include which table each tool reads, which ticket the tool helps unlock, and one specific sentence on why that tool is the right one for that ticket

## Problem 4: Add the MCP server to vibe coder and test each tool

**Prompt:**

> Problem 4: Add the MCP server to vibe coder and test each tool. Liike it says, add the mcp server so all the tools can be called from here. Save the connection json text in .mcp.json in the project root (or let me know how otherwise you would want to save local MCP server lists)

**Second prompt:**

> ok i restarted. Proceed with testing each of the three tools. Save the evidence of testing in output/mcp_smoke.json. Include for each tool the prompt sent to the vibe coder, the tool name, and the tool output (check it matches the values in the new database)

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**

> Problem 5: Build the agent team and grow the MCP tools. ok time to build the team of agents using pydanticAI. Build a boss, inventory, accounting, facilities, and customer service agent. include the appropriate prompts, models, and agent loops to fully connect them and allow they to delegate work to each other. Make sepearate files for prompts for each agent in backend/prompts/ . Put the data types in backend/model.py and the agent files under backend/ . Show me an example of each prompt with the shop rules that agent needs

**Second prompt:**

> Ok - now we are going to add tools that the agents need to the MCP server. We are not supposed to do anything to bypass MCP - the facts should come from the MCP server over the new database. Agents should be appended to output_audit_trail.json as they run - for each agent-loop step, record enough to be auditable later. in output/harness.md list each agen and each MCP tool (including newly added) along with which table used by that tool. Also add a safety section with the guardrails a real business would want, particularly considering when agents interact with real customers and real money, and limits to keep token use in check. I know you did part of this already.

**Third prompt:**

> also please update mcp_server/README.md so the tool list matches the updated tools

## Problem 6: Plan the three tickets

**Prompt:**

> Problem 6: Plan the three tickets. I will start with writing what I expect the team to do on each open ticket. You will build output/desk_tickets.html , a double-clickable page with a separate tab for each ticket and tabs for Cash and Reflection (for a later problem). On each ticket tab, fill an Expected section with what I write and leave room for an Actual section to be filled after we actually run the agents. For the Expected, for Ticket 101, The boss will read the ticket and check the date. It will call inventory for stock on the item and will get the response that stock is 0 in size S and return stock for the other sizes. The boss will call accounting to check the linked invoice 501 and accounting will check current balance, find an outstanding invoice of $840 that needs to be paid before the reprint order will be handle, and identify any other outstanding invoices and due dates. Accounting will  call facilities to check rent obligations. Facilities finds the outstanding rent due Sept 2 and returns that information to accounting. Accounting determines that paying the $840 and the $2400 rent due will leave $160 so prepares payment of the $840 for human approval and returns that to the boss with the information it has gathered including a priority of paying the overdue $840 while noting the upcoming rent due.  The boss asks customer service to draft a response to the customer to let them know about the delay  due to out of stock and ask about suitability of a different size that is currently in stock. Customer service calls inventory to confirm the information from the boss, writes the draft and sends it back to the boss while informing the boss if there is any unconfirmed information. The boss will update the ticket status with needs human and will draft the request to the human (i.e., approval to pay the $840 invoice and showing the draft e-mail for the human to send if desired).  Ticket 102 The boss reads the ticket and asks facilities to confirm the lease and due date of payment. Facilities does that and calls accounting to check cash balance and prepare the payment for human approval, giving the lease id, landlord, amount, and due date for accounting to work with. Accounting does that and returns it to Facilities with the recommendation to pay given the account balance will still be positive. Facilities returns this to the boss. The boss updates the ticket status with needs human and drafts the request to the human for consideration. Ticket 103. The boss calls inventory to consider the request for 20 hoodies size M. Inventory returns the inventory information including the shortfall of 12 tees relative to the order and the availability of different sizes. The boss calls accounting with the ticket and inventory information to determine the cost of reprinting the shortfall and the margin on the hoodies to return to the boss with the break even point for a discount. Accounting notes that there is not enough cash to pay for filling the order because of the shortfall. The boss receives the information and calls customer service to prepare a draft e-mail to the customer indicating the current shortfall and ask about whether filling the shortfall with other sizes is okay (and which sizes) or whether the customer would like a partial fill now and more complete fill later or would like another option. Customer service prepares the draft and sends it back to boss. The boss prepares the information for human consideration including the most immediate need of contacting the customer to consider how to proceed, what discount to offer in the correspondence to customer, and the problem that the full order cannot be supplied with the current cash on hand, unless there is prepayment.

**Second prompt:**

> issue #1. Incorporate into 101. The boss calls inventory first because it needs to know whether the order can be filled as is.
>
> Incorporate into 102. The boss calls facilities first because it needs to confirm that the lease is due and the amount.
>
> incorporate into 103. The boss calls inventory first because it needs to know whether the order can be filled as is.
>
> The boss uses get_ticket and get_desk and ask_agent and update_ticket. inventory uses check_stock, list_vendors, check_vendor_invoices. Accounting uses check_stock, check_vendor_invoices, get_invoice, get_cash_balance, prepare_payment, and ask_agent. Facilities will use get_lease and and get_desk. Customer service uses ask_agent.
> issue #2. yes change to hoodies. issue #3 please change to 'waiting_on_approval'. #4 leave it

**Third prompt:**

> 1. yeah let's let facilities do ask_agent. 2. understood, let's keep it in the lists and change the heading. 3. please remove the check_stock and get_invoice from 102 and add check_margin under accounting for 103

## Problem 7: Backend routes

**Prompt:**

> Problem 7: Backend routes. We are going to prepare a backend to be called by a frontend we will make in the next priblem. For now, in backend/main.py use FastAPI and add routes that a) return the three tickes and whether each is open or resolved b) take a ticket id and run your agent team on that ticket c) return recent agent events so the board can refresh (include what each agent says and the tools used) d) approve a payment/purchase after a human clicks approve (which should change cash) e) return the current checking balanc from cash_accounts f) reset the databse to the original values when a fresh run is desirder.
> From the backend/ folder, start the server with uvicorn main:app --reload --port 8000
> in output/harness.md list each tour in one line (what URL and what it does)

## Problem 8: Agent dashboard

**Prompt:**

> Problem 8: Agent dashboard. Ok now build the frontend dashboard in frontend/ with React, Vite and Typescript. Make sure it calls all the routes we just did. the board should list all three tickets, allow selecting a ticket and starting the agent team on it, show what each agent is doing while the ticekt runs, mark a ticket as resolved when the run finishes, show a short summary of what each agent did, let a human approve a pay or purchase when asked, show the checking balance with live changes. This is supposed to look good so try your best but I can help afterwards. The front end should talk to the back end on ocalhost:8000. On the backend allow the vite page origin (e.g. localhost:5173) so the browser can call the routes. Start the board with npm run dev . Start an output/design.md file to keep decisions about how the dashboard looks and why it is designed that way

**Second prompt:**

> ok do you remember the work we did before for campus customs using the right fonts and marks?

**Third prompt:**

> yes, go ahead and make it match HW4

**Fourth prompt:**

> change start the team to Activate Ops Team. Figure out who in the Yale University executive heirarchy best matches each role (like the boss is the president of the university) and make cartoon representations of the actual people with their names with a subtitle of boss, accounting, etc. Make sure the agent team resizes appropriately if I resize the window

## Problem 9: Resolve the tickets

**Prompt:**

> ok we can keep them. Problem 9: Resolve the tickets. I will reset the board and run all three tickets. Your job is to fill the actual section from this run. Also, itemize the money in the Cash tab. That is, after I reset, start checking balance and for each ticket note how cash changed when that ticekt resolved and why. Check the ending balance and make sure it matches cash_accounts in the working database. also save output/resolved_tickets.json for each ticket with id, final status, short outcome, what each agent contributed, and any human approvals AND output/resolved_board.html, a double-clickable page with a screenshot of the react board for each resolved ticket. Append real runs to output/audit_trial.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

## Problem 10: Reflection

**Prompt:**

> Problem 10: Reflection.  Fill the reflection tab with the following. The agents overall did well but there were some issues. They handled the first two tickets without any problems, presenting an approval request to a human with the appropriate information. However, in the second ticket I was allowed to approve it before the agents had fully finished, resulting in the ticket showing as resolved at the time the agents finished. For the third ticket there was an issue that didn't mess with the final result - a vendor look up created a false vendor that was then rejected. Actual compared overall well to expected but with notable differences. In task 101 I thought accounting would ask facilities about rent because I neglected to notice that accounting could do it itself. Also customer service did not ask inventory to confirm what the boss told it about inventory. In task 102, there was the issue with final status being resolved because I was able to approve the request before the agents fully finished their run and that approval was acknowledged in media res by the agents. I also also did not anticipate accounting using get_lease and erroneosly listed check_vendor_list. In task 103, accounting never checked the cash so the expected message about the $264 restock expense being more than the $160 balance didn't happen. I also expected the e-mail draft to offer the other sizes but it didn't, and it asked the customer what discount it wanted while I had anticipated that that would have been presented to the human with a suggestion based on the margin. Also, accounting accessed inventory once when it should have been unnecessary. It would have been simpler to have a single agent for the sequential tasks without parallel processing or going back and forth. For high priority sequential actions with a linear process, like paying rent, a single agent would likely be more efficient. However, for tasks with multiple threads, like checking inventory, checking balance and other debts, checking with the customer for alternatives, the multi-agent system is better. This team could solve problems including a vendor requesting payment on an overdue bill, a customer asking to purchase an in-stock item, and a request to list the sales value of current inventory. This team could not manage requests about adding new items to inventory and would need a tool to categorize new items according to the existing template and add them including adding their values and margin and vendors. This team does not have the capability to access inventory over time information so cannot answer questions from customers about inventory that used to be in stock and who the vendor was. We'd need baseline historical information and a decision making capability (likely with human involvement) as to whether we are or are no longer working with a vendor and/or whether that vendor still can make a product. This team cannot interact with outside agents (like a vendor's agent) to check information about availability of items and delivery time. It would need a tool for the MCP to interact with outside ones and rules for those interactions.

**Second prompt:**

> yes do all 3

## Problem 11: Submit to GitHub

**Prompt:**

> Problem 11: Submit to GitHub. Time to submit to a public github repository so graders of the assignment can clone it. include both database files under data/ and of course don't push my real .env. Put the repository url in output/github_url.txt and I will post it to canvas. The README should explain the copying of the original db to the working copy for a clean run, starting the mcp server, starting the backed, starting the react board, and reseting the db before a full three-ticket run
