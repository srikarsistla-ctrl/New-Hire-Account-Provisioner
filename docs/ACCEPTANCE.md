# Acceptance evidence against the supplied problem statement

Source: the user's pasted **New Hire Account Provisioner** specification. No separate photo was available during this audit. This report covers the provided requirements, not unknown organizer tests or competitor comparisons.

## Official cases

| Case | Required result | Automated evidence |
| --- | --- | --- |
| TC.1 Approved tools | All eight selected accounts created with approved roles; lowest roles are defaults | `test_tc1_approved_tools.py`, plus all-eight non-default roles and explicit admin approval for each provider in `test_official_acceptance.py` |
| TC.2 Existing users | Reuse accounts; no duplication | `test_tc2_user_exists.py`, plus a second independent request for all eight tools that consumes no additional seats |
| TC.3 Default role override | Admin provider default must not override approved Viewer | `test_tc3_default_role.py`, plus admin-default override for all eight providers and downgrade of an existing GitHub Admin to Viewer |
| TC.4 Seat limit | Partial Access with explanation; other tools continue | `test_tc4_seat_limit.py`, plus saturation of each of the eight providers independently |

For Slack and Zoom, the lowest mock role is Guest and Basic respectively, rather than Viewer. Where Google Workspace is selected and cannot be created, new Slack provisioning is also marked partial because of the explicit dependency. Unrelated providers continue. Salesforce saturation is the standard TC.4 example, with all seven other apps succeeding.

## Requirement mapping

| Requirement | Implementation / evidence |
| --- | --- |
| Python FastAPI, plain HTML/CSS/JS, SQLAlchemy SQLite | `app/main.py`, `frontend/`, `app/database.py`, `requirements.txt` |
| Six employee fields, eight tools, role validation | `HireDetails`, `HireInput`, `Assignment`; browser form |
| Collect → plan → inspect → approved action | Input validators, dependency planner, mock preflight inspection, transactional executor |
| LangChain AI | Structured job-based recommendations and read-only model tool review; labeled offline fallback |
| Eight simulators with required five methods | Eight provider classes inherit `MockSaaS` methods |
| Human approval before mutation | Decision endpoint; confirmation, current revision, pending-state checks |
| Modify/reject individual assignments | Role edits and removal; removed assignments verified not to execute |
| Least privilege | Lowest default roles; exact approved role sent instead of provider default |
| No duplicate accounts | Normalized email, unique tool/email database constraint, existing-account reuse, concurrent-request tests |
| Groups | Department group assignment with explicit partial outcome if assignment fails |
| Access matrix, summary, timestamped audit | Results view, JSON export, persisted provisioning logs |
| Seed data | Existing synthetic users; GitHub admin default; configurable capacity and fault simulation |
| Graceful failures | Capacity changes, simulated outages, group errors, dependency failures, AI fallback |
| Setup, tests, architecture, UI documentation | README, Mermaid architecture, browser screenshots |

## Policy compatibility correction

The added strict department policy previously prohibited Admin requests outright, conflicting with the brief's ability to explicitly approve higher roles. The default `ACCESS_POLICY_MODE=approval` now matches the original requirements: supported higher roles can be planned, but no account changes occur until the user approves the saved plan. Omitted roles remain minimum access.

Set `ACCESS_POLICY_MODE=strict` to opt into the extra department restrictions. This extension is tested separately and intentionally rejects certain higher roles. Unrecognized mode values take the restrictive path. Neither mode lets AI approve accounts.

## Reproduce

From the project folder:

```powershell
python -m pytest -q
```

Audit result: **60 tests passed**, covering official scenarios and expanded regressions. Fixtures use temporary databases and disable external AI keys. The browser workflow previously passed guide, form, editing/undo, approval, rejection, search/filter, recommendation, and mobile checks.

## Distinguishing features already implemented

- Job-based AI app/role recommendations with per-app explanations.
- Human review with revision protection, undo, and explicit rejection.
- Repeat-safe approvals and concurrent seat/duplicate protection.
- Policy validation independent of model output.
- Persistent audit records and downloadable results.

## Verification boundaries

Live Groq recommendation quality has not been verified in this audit; AI tests use controlled model responses. This is an unauthenticated local sandbox with simulated integrations, as requested. Approval records are not proof of a verified manager identity. No guarantee is made about hidden tests, production readiness, or competition placement.
