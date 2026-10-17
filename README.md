# Multi-Database Query Management Platform (QuantumDBA)

A centralized, high-performance web platform that empowers Database Administrators (DBAs) to execute, broadcast, and monitor SQL queries simultaneously across multiple database instances of the same or different types, grouped by operational categories (e.g., Quotera DB, Trade DB, Backoffice DB) or targeting specific nodes.

---

## Key Features

- **Multi-Target Concurrent Query Execution**:
  - Broadcast SQL queries in parallel across multiple database instances grouped by operational categories (e.g., Quotera DBs, Trade DBs) or targeted to specific individual nodes using multi-threaded execution (`ThreadPoolExecutor`).
- **Heterogeneous Engine Support & Dialect Analysis**:
  - Connects natively to **PostgreSQL, MySQL, Oracle**, and **SQLite**. Real-time pre-flight inspection alerts you to engine-specific SQL friction (e.g., `LIMIT` vs `ROWNUM`, `ILIKE` vs `LIKE`, quoting syntax).
- **Role-Based Access Control (RBAC)**:
  - Strict hierarchical permissions for **Super Admin (`lead_dba`)**, **Standard DBA (`dba`)**, and **Auditor (`auditor`)** ensuring least-privilege operations.
- **Granular Database Permission Scoping**:
  - Control access (*Read-Only*, *Read & Write*, or *Hidden*) per user and per database. Write statements (`INSERT`, `UPDATE`, `DELETE`, DDL) are strictly blocked on read-only databases.
- **Immutable Audit & Compliance Logging**:
  - Comprehensive, tamper-evident audit trail tracking every query execution, login, schema update, and credential change with role-scoped visibility.
- **Diagnostics, Reporting & Data Export**:
  - Real-time execution summaries with per-node latency metrics, status badges, interactive data tables, and one-click CSV/JSON data export.

---

## Visual Tour & Interface

### End-to-End Workflow Recording
![Multi-Database Studio Video Tour](docs/screenshots/video_tour.webp)

---

### 1. Query Execution Studio
Execute and broadcast queries across individual databases or category clusters with real-time target resolution and dialect feedback.

![Query Studio](docs/screenshots/query_studio.png)

---

### 2. Execution Results & Export
Per-node results card with status badges, execution duration, interactive data tables, CSV/JSON export, and detailed failure diagnostics.

![Query Results](docs/screenshots/query_results.png)

---

### 3. Database Registry & Categorization (Super Admin)
Manage database clusters, connection parameters, engine specifications, and run live connection heartbeat tests.

![Database Registry](docs/screenshots/db_registry.png)

---

### 4. DBA User Provisioning & Granular Permissions
Provision administrators and assign database access levels using quick presets (All Read/Write, All Read-Only) or individual node toggles.

<p align="center">
  <img src="docs/screenshots/provision_modal.png" width="48%" />
  <img src="docs/screenshots/edit_user_modal.png" width="48%" />
</p>

---

### 5. Scoped Audit & Compliance Logging
Track system activity with action filters (`LOGIN`, `QUERY_EXECUTE`, `DB_CREATE`, `DB_UPDATE`, `DB_DELETE`, `USER_CREATE`, `TEST_CONNECTION`).

![Audit Logs](docs/screenshots/audit_logs.png)

---

## Permissions Matrix

| Feature / Capability | Super Admin (`lead_dba`) | Standard DBA (`dba`) | Auditor (`auditor`) |
| :--- | :---: | :---: | :---: |
| **Execute `SELECT` Queries** | All Databases | Permitted Databases | Permitted Databases (Read-Only) |
| **Execute Write Queries (`INSERT`, `UPDATE`, DDL)** | All Databases | Permitted R/W Databases Only | **Blocked** (`Permission Denied`) |
| **Database Registry (Add / Edit / Delete)** | **Yes** | **No** (Hidden & Restricted) | **No** (Hidden & Restricted) |
| **User Administration (`/users`)** | **Yes** | **No** (Access Denied) | **No** (Access Denied) |
| **Audit Logs Visibility** | **Global** (All Users) | **Personal Stream Only** | **Personal Stream Only** |
| **Target Scope in Query Studio** | All Categories & Databases | Permitted Categories & DBs | Permitted Categories & DBs |

---

## Quick Start Guide

### Prerequisites
- Python 3.9+
- PostgreSQL 12+

### 1. Clone & Set Up Virtual Environment
```bash
git clone <repository-url>
cd "Query management platform"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Application Database Engine (PostgreSQL)
The platform uses **PostgreSQL** exclusively for its internal metadata (users, categories, database connections, permissions, audit logs, and query history).

Set your PostgreSQL connection details in `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your PostgreSQL connection URI (default port: `5432`):
```env
DATABASE_URL=postgresql://username:password@localhost:5432/platform_db
```
*(Alternatively, configure individual parameters: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_SCHEMA`).

### 3. Initialize Database & Seed Administrator
To provision all tables and seed the default administrator account:
```bash
python3 init_db.py
```

### 4. Run Application Server
```bash
python3 app.py
```
The application will start on **`http://127.0.0.1:5001`**.

---

## Default Administrator Credentials

| Role | Username | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `admin` | `admin123` | Full Organization Authority (All DBs & Users) |

*(Additional accounts can be provisioned via the DBA Users console)*.

---

## Running the Automated Test Suite

The platform includes an extensive test suite covering authentication, multi-target execution, dialect analysis, error diagnostics, active/inactive status enforcement, per-database permissions, and audit log scoping:

```bash
python3 -m unittest tests/test_platform.py
```

---

## Project Structure

```
├── app.py                     # Flask application routes, decorators & auth
├── models.py                  # Database schemas, UserModel, PermissionModel, AuditModel
├── db_manager.py              # Engine dialect helper, connection factory, concurrent executor
├── init_db.py                 # PostgreSQL table provisioning & default admin seeder
├── requirements.txt           # Python dependencies
├── docs/
│   └── screenshots/           # Application screenshots and visual assets
├── static/
│   ├── css/style.css          # Design system, glassmorphism, dark theme styling
│   └── js/app.js              # Client-side targeting controls, AJAX executor, export
├── templates/
│   ├── base.html              # Core navigation layout & alerts
│   ├── login.html             # Secure DBA sign-in interface
│   ├── dashboard.html         # Query Execution Studio
│   ├── databases.html         # Database Registry & Configuration
│   ├── audit.html             # Immutable audit log stream
│   └── users.html             # User administration & permission matrix
└── tests/
    └── test_platform.py       # 11 unit & integration tests
```
