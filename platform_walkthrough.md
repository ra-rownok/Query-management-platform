# Multi-Database Query Management Platform (QuantumDBA)

## Overview
**QuantumDBA** is a centralized, high-performance Flask platform that enables Database Administrators (DBAs) to execute and broadcast SQL queries simultaneously across multiple databases of the same or different types, grouped by categories (e.g., Quotera DB, Trade DB, Backoffice DB) or targeting individual nodes.

---

## Video Tour & Visual Highlights

### End-to-End Workflow Recording
![Multi-Database Studio Video Tour](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/multi_db_query_tour_1792046709690.webp)

````carousel
![DBA Login Screen](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/login_page_1792046728094.png)
<!-- slide -->
![Query Studio with Multi-Targeting & Permission Badges](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/query_studio_dashboard_1792046775787.png)
<!-- slide -->
![User Provisioning with Database Permissions Matrix](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/provision_user_modal_1792055679233.png)
<!-- slide -->
![Edit User & Per-DB Permissions Pre-population](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/edit_user_modal_1792055713335.png)
<!-- slide -->
![Query Results with Tables & Failure Traces](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/query_results_1792046856934.png)
<!-- slide -->
![Broadcast Across All 9 Engines](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/engine_ping_results_1792046962969.png)
<!-- slide -->
![Database Registry (Restricted to Super Admin)](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/db_registry_1792047002223.png)
<!-- slide -->
![Immutable Audit Logging](/Users/rownok/.gemini/antigravity-ide/brain/996a7e5f-6e52-46b6-a4d6-f55b8fef8eb6/audit_logs_1792047032737.png)
````

---

## Core Capabilities Implemented

### 1. Granular Role & Per-Database Permission Control
- **Super Admin (`lead_dba`) Only Authority**:
  - Only the Super Admin can register, update, or delete databases in the registry.
  - Only the Super Admin can provision new users, edit existing accounts, toggle active/inactive status, and manage DB permissions.
- **Per-User Database Permission Scoping**:
  - Standard DBAs and Auditors **only see and query databases that the Super Admin explicitly assigned to them**.
  - On user creation and editing, Super Admin can:
    - Click **"All Read/Write"** to grant full access across all registered databases.
    - Click **"All Read-Only"** to grant read-only query access across all registered databases.
    - Customize individual databases (assigning *Read & Write*, *Read-Only*, or *No Access* per node).
- **Auditor Role Enforcement**:
  - Auditors can run `SELECT` queries only on permitted nodes. Any write operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc.) are blocked with an explicit `Permission Denied` notice.
- **Active / Inactive Status Enforcement**:
  - Inactive users are immediately blocked from logging in with a clear alert.
- **Target Studio Integration**:
  - In [dashboard.html](file:///Users/rownok/quant/Query%20management%20platform/templates/dashboard.html), target selectors and pills display real-time permission badges (`R/W` or `READ ONLY`) next to each node. Queries against unpermitted databases or write operations on read-only databases return an immediate, clear failure report.

### 2. Database Registry & Categorization
- **Database Categorization**: Group databases by business domain (e.g., `Quotera DB`, `Trade DB`, `Backoffice DB`) with custom colors and descriptions ([databases.html](file:///Users/rownok/quant/Query%20management%20platform/templates/databases.html)).
- **Engine Specification**: Supports PostgreSQL, MySQL, Oracle, and SQLite with port defaults and connection options.
- **Live Connection Testing**: Test button performs instant ping against configured endpoints and displays duration or failure diagnosis.

### 3. Query Execution & Flexible Targeting
- **Target Selection Modes**:
  1. **Individual Database**: Run on a single selected node.
  2. **Category Group**: Broadcast across all active nodes in a category (e.g., all Quotera DBs).
  3. **All Registered Databases**: Execute simultaneously across every database in the registry.
- **Engine Awareness & Dialect Validation**:
  - Live pre-flight dialect validator warns if query contains non-standard keywords (e.g. `LIMIT` vs `ROWNUM` / `FETCH FIRST` on Oracle, PostgreSQL `ILIKE` vs MySQL `LIKE`, or backtick quoting).
  - Target engine filter allows narrowing broadcast to a specific engine dialect (e.g. PostgreSQL only).
- **Concurrent Execution**: Multi-threaded execution (`ThreadPoolExecutor`) ensures queries across 10+ databases complete in parallel without head-of-line blocking.

### 4. Results Reporting & Error Diagnostics
- **Comprehensive Status Summary**: Total targets, Succeeded count (green badge), Failed count (red badge), and execution duration in milliseconds.
- **Interactive Result Tables**: Formatted, sticky-header tables with per-node CSV and JSON export options.
- **Failure Root Cause Analysis**: When a query fails (e.g., table does not exist, connection timeout, network unreachable, syntax error), the platform highlights the exact failure reason and exception stack trace.

### 5. Audit & Activity Logging with Role Scoping
- **Super Admin (`lead_dba`) Global Visibility**:
  - The Super Admin has full organizational visibility to inspect all user logins, query executions, database registrations, configuration edits, connection tests, and user provisioning events across the entire company.
- **Personal Activity Scoping for Standard DBAs & Auditors**:
  - Non-super admin users (standard DBAs and auditors) **only see their own personal activity stream and query history** (logins, connection tests, and broadcast queries executed by their account). They cannot view other administrators' queries, credentials tests, or management actions.
- **Query History Scoping**:
  - The Query Execution Studio's recent history panel is also scoped: standard DBAs only see their own recent queries for fast rerun, while the Super Admin can view global recent broadcast activity.
- Includes real-time search, action filters (`LOGIN`, `QUERY_EXECUTE`, `DB_CREATE`, `DB_UPDATE`, `DB_DELETE`, `USER_CREATE`, `TEST_CONNECTION`), and scope indicator chips.

---

## Running the Application

### Default Credentials
- **URL**: `http://127.0.0.1:5001`
- **Username**: `admin`
- **Password**: `admin123`

### Command to Start Server
```bash
./venv/bin/python3 app.py
```

### Running Test Suite
```bash
./venv/bin/python3 -m unittest tests/test_platform.py
```
