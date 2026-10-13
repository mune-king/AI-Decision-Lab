# AI Decision Lab v1.0

Lecture experiment: M0 (17 decisions), then M1 (17 decisions). Initial shares 100, cash JPY100,000 per run. No outside funding, borrowing or short selling.

## Student workflow

Open index.html through HTTPS. No name, student number, email or account is requested. A random UUID and 256-bit write capability are generated with Web Crypto. The capability stays in browser storage and is sent over HTTPS only to the save endpoint; only its SHA-256 hash is stored on the server. It never appears in CSV exports or the researcher dataset.

Each confirmed answer is retained in localStorage and automatically submitted. The UI shows the server-acknowledged count; it never labels an unacknowledged answer as saved. Offline failures retry after 10 seconds, on reconnection and when the page becomes visible. Continue in the same browser. Browser storage clearing, private browsing closure or permanent device loss can destroy unsubmitted answers. If local storage is unavailable, the page displays a warning. CSV downloads are optional anonymous backups, not required submissions.

The database validates sequence, condition, price and portfolio balance. Confirmed answers cannot be changed. Repeating a request does not duplicate answers. A stale request cannot delete later answers. Existing v0.9 local data is not silently imported because it contains student numbers.

## Researcher access

researcher.html uses Supabase password login. Authentication alone does not grant data access. The research RPC checks decision_private.researchers against auth.uid(). No researcher accounts existed at implementation time; account creation and a verified administrator grant remain necessary before this page can be used. Register an appropriate researcher using Supabase Auth administration, verify their identity, then add their verified auth.users UUID to decision_private.researchers through the SQL editor. Do not grant students or anonymous users researcher access.

Data is collected in decision_private.runs. It is available to the project owner through Supabase SQL administration while the researcher account is being provisioned. Neither private table is exposed through the Data API. Public save RPC is deliberately callable without student authentication; it returns only a run ID and saved count and enforces the per-run capability. This intentionally triggers the Supabase public SECURITY DEFINER advisory. The authenticated research RPC also deliberately uses SECURITY DEFINER with an explicit researcher allowlist. Both functions have an empty search_path and explicit grants. Public submissions can be fabricated or spammed; this is a lecture pilot, not an attendance or identity verification system. Condition allocation is hash-based random UUID allocation, not guaranteed balanced blocks.

## Validation

`node test-save.cjs` exercises all 34 decisions with a lightweight DOM fixture, offline retention and server acknowledgement. This does not emulate iOS/Android browsers. Real REST API validation saved 17 then 34 answers, repeated and stale requests kept exactly 34, incorrect capabilities and invalid balances were rejected, and unauthenticated research reads were denied. Physical iPhone/Android and simultaneous class-load tests remain unperformed.

## Recovery

Previous main commit before v1.0: 11af0a346765bbc90f50687412595e3b706cf59e. Restore that index.html to revert the student UI; retain private collection tables to preserve submitted data. Do not roll back by dropping data tables.
