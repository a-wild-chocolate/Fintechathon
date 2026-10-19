TRADEX — FIVE-MINUTE PRODUCT DEMO
Case: A partial payment, a missing date, and a supplier deadline
Language: English presentation; Chinese operator guide
Scenario date: 17 October 2026
All companies, correspondence and financial records in this pack are synthetic.

THE STORY
StarSail Exports is a small Shenzhen trading business with eight employees and one finance generalist. Its UK buyer promises a partial payment without giving an amount or a date. The owner needs to decide how to meet a CNY 160,000 supplier payment. TradeX turns that incomplete email into questions, a confirmed receipt forecast, a company-wide cash analysis, and a concrete negotiation draft.

THE FIVE-MINUTE OUTCOME
The team confirms USD 6,000 expected on 29 October, leaves USD 6,000 unscheduled, and sees the CNY peak shortfall rise from 32,000 to 34,000. A ten-day supplier extension postpones the problem but does not eliminate it. A conditional extension to 17 November avoids a negative daily CNY balance in this scenario, after a scheduled receipt from another customer order. The final output is a negotiation draft; the supplier has not yet accepted it.

FILES AND WHEN TO USE THEM
preload/01_company_cash_schedule.txt
  Company-wide; upload before the presentation. Explains the modeled CNY cash schedule and USD reserve constraint.
preload/02_sales_order_TF-26104.txt
  Link to TF-26104; upload before the presentation. Establishes the outstanding balance and original forecast.
preload/03_supplier_payment_terms_TF-26104.txt
  Link to TF-26104; upload before the presentation. Establishes CNY 160,000 due on 22 October.
live-upload/04_buyer_partial_payment.eml
  Link to TF-26104; upload LIVE. Intentionally omits the partial-payment amount and availability date.
presenter-only/05_buyer_clarification.eml
  Keep OUT of the library until the AI has asked its questions. Supplies the later USD 6,000 / 29 October clarification.
presenter-only/06_finance_assumptions.txt
  Explains the CNY availability date, illustrative conversion assumption and USD reserve.
presenter-only/PROMPTS_EN.txt
  Copy-and-paste requests, clarification answers and the comparison question.
presenter-only/SCRIPT_EN.txt
  Timed English narration. Speak while the application processes requests.
presenter-only/OPERATOR_GUIDE_ZH.txt
  Preparation, exact operation sequence, timing and handling of slow responses.
presenter-only/EXPECTED_RESULTS.json
  Reference outputs calculated with the current backend cash engine; not an uploaded business source.
optional-after-demo/07_supplier_acceptance.eml
  Optional follow-on exercise after the five-minute presentation. Do not preload: acceptance is a later event.

PRIMARY ROUTE
Overview → TF-26104 → Documents / connected library → upload the email → Ask AI → answer questions → confirm expected payment → Overview → AI comparison and draft.

Use the connected library's Upload document and Ask AI controls. The order wizard also has local sample-extraction controls; those are a different demonstration path. The primary presentation uses the actual model/MCP assistant and its confirmation card.

PREPARATION
Use a fresh demo workspace and an unused browser origin or a private browser window. The current development workspace may contain earlier confirmations; a new chat alone does not reset the financial state. Required baseline: CNY 128,000 opening cash; supplier due 22 October; USD 12,000 expected on 29 October; peak CNY shortfall 32,000. See the operator guide for isolated startup commands.

INDEXING AND IMPORT
Uploading a schedule document makes it retrievable; it does not import a new accounting ledger. This case deliberately matches the application's built-in company schedule. Only the expected receipt confirmation changes the accepted forecast during the main demo.

REHEARSAL
Budget roughly 400 spoken words plus interaction time. Actual model and indexing latency varies. Rehearse the three AI phases on the presentation machine: interpretation, clarification continuation, and post-confirmation analysis. Keep a recording of the same real workflow ready if a strict five-minute slot cannot accommodate live latency; label a recording as a recorded run.

WHAT TO LEAVE FOR QUESTIONS
Web search, sandbox Python, financing-document checklists, time/event reminders and the second order's bank-fee reconciliation are separate capabilities. They do not advance this case enough to justify extra clicks in the five-minute story.
