# 🎬 ContextKeeper — 5-Minute Evaluation & Demo Script

This script walks an evaluator or reviewer through the complete end-to-end functionality of ContextKeeper in ~5 minutes, demonstrating all key scenarios specified in the master prompt.

---

## ⚡ Quick Start
```bash
# 1. Navigate to the project
cd contextkeeper

# 2. Reset and seed realistic data
python -m app.seed

# 3. Launch the application
uvicorn app.main:app --reload --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🧭 Scenario 1: The "Missed Meeting" Context Gap (1 min)
**Problem**: Alex missed a meeting while on medical leave. What did the team decide? What is expected of Alex?

1. Click **⚡ Catch-Up Brief** in the top navigation bar (`/catchup`).
2. Under **Select Teammate**, choose **Alex Rodriguez (Senior DevOps & Infrastructure Engineer) [On Leave]**.
3. Under **Select Meeting**, choose **#4 - Sprint 23 Retrospective & Risk Review**.
4. Click **⚡ Generate Personalised Brief**.
5. **Observe**:
   - The **✨ AI-GENERATED** badge.
   - **What You Need to Know**: Tailored summary of sprint decisions and team blockers.
   - **Expected of You**: Specific action items relevant to DevOps and Alex's owned items.
   - **Overdue Items**: Highlighting his overdue staging migration task.
   - Click **📋 Copy Brief** to verify clipboard copy.

---

## 🧭 Scenario 2: Handover Risk Radar & Smart Actions (1.5 min)
**Problem**: Open action items quietly slip through the cracks when owners go on leave or meetings lack follow-through.

1. Click **🎯 Risk Radar** in the top navigation (`/`).
2. Review the top metrics:
   - **Critical Risk Items** (Score ≥ 60)
   - **Team On Leave** (Alex Rodriguez: Oct 28 - Nov 7)
3. Inspect the top at-risk item:
   - *Title*: `Execute Postgres staging migration script and verify foreign keys`
   - *Risk Score*: **80/100** (Color-coded Red)
   - *Fired Signals*:
     - `⚡ Overdue by 3 days`
     - `⚡ Owner Alex Rodriguez is currently on leave`
     - `⚡ Stale context: carried forward 3 times across meetings`
     - `⚡ Owner Alex Rodriguez did not attend source meeting`
4. **Trigger Smart Nudge**:
   - Click **✉️ Nudge** next to the item.
   - Toggle between **Friendly & Supportive 😊** and **Firm & Direct 🎯**.
   - Notice how the tone and language adapt dynamically while preserving collegiality.
   - Click **Copy to Clipboard**.
5. **Trigger AI Reassignment Suggestion**:
   - Click **🔄 Reassign** next to the item.
   - AI analyzes teammates who are active and not on leave.
   - Recommends **Sarah Chen** because of her Staff Backend background and current availability.
   - Click **Confirm Reassignment**.
   - Watch the item update instantly with a new owner and lower risk score!

---

## 🧭 Scenario 3: Carry-Forward Continuity & Full Audit Trail (1 min)
**Problem**: Items get copied between meetings and lose their historical context.

1. Click **✅ Action Items** (`/items`).
2. Find any open item and click **📜 History**.
3. **Observe the Append-Only Event Drawer**:
   - `CREATED` event with creator and timestamp.
   - `CARRIED FORWARD` events documenting the exact transition from Meeting A to Meeting B.
   - `REASSIGNED` events showing old owner → new owner with handover notes.
4. **Enforce Mandatory Outcome on Closure**:
   - Click **✓ Close** on an open item.
   - Try submitting with an empty outcome — notice the validation rejects it.
   - Select Resolution Type: `Completed` or `Superseded`.
   - Enter Outcome Summary: `"Completed verification against staging RDS cluster; 0 errors."`
   - Click **Save Outcome & Close**.
   - Re-open **📜 History** and see the `OUTCOME RECORDED` event logged immutably.

---

## 🧭 Scenario 4: Human-in-the-Loop AI Meeting Recap (1 min)
**Problem**: Unstructured meeting notes, transcripts, or chat dumps need to be structured without hallucinations.

1. Click **📅 Meetings & Handovers** (`/meetings`).
2. Select **#5 - Urgent: Staging Database Migration Sync**.
3. Click the **✨ AI Recap & Review** tab.
4. Review the raw transcript in the input box.
5. Click **✨ Extract AI Recap Draft**.
6. **Observe the Grounded Human-in-the-Loop Review**:
   - Draft Summary and Decisions ready for editing.
   - Action Items table displaying **Confidence Score** and exact **Verbatim Source Quotes** (e.g., `“We need the staging Postgres up before end of sprint”`).
   - Click **Exclude** to discard an unwanted action item.
   - Edit an owner or due date inline.
7. Click **✅ Accept & Commit Recap**.
8. Notice that double-clicking or resubmitting is **100% idempotent** (items are not duplicated).

---

## 🧭 Scenario 5: Graceful AI Degradation & Request-ID Traceability (0.5 min)
**Problem**: When upstream AI APIs experience rate limits (429) or timeouts, the app must remain fully usable.

1. **Verify Deterministic Heuristic Fallback**:
   - Set `MOCK_AI_FAIL=timeout` in `.env` (or run offline with no keys).
   - Generate a recap or brief: the app catches the error, engages heuristic extraction (`TODO:`, `@mention`, `by <date>`), tags the result with `fallback_used: true`, and never loses user input.
2. **Trace a Request End-to-End via Logs**:
   - Click **⚙️ Admin & Logs** (`/admin-ui`).
   - Enter the token: `change-admin-token` and click **Unlock Data**.
   - Review the **AI Runs Table**:
     - Inspect `latency_ms`, `provider`, `model`, `prompt_version`, and unique `request_id`.
   - Switch to the **Application JSON Log Tail**:
     - Locate the exact `http_request` log line matching the `request_id`.
     - Confirm all sensitive API keys and tokens are replaced with `[REDACTED]`.

---

✅ **Demo Complete! All core functional, AI, architectural, and reliability requirements verified.**

