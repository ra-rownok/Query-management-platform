import os
import json
import sqlite3
from models import init_app_database, UserModel, CategoryModel, DatabaseModel, AuditModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DB_DIR = os.path.join(BASE_DIR, 'instance', 'demo_dbs')

def create_sample_sqlite_db(filepath, schema_sql, seed_sql):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        conn = sqlite3.connect(filepath)
        cursor = conn.cursor()
        cursor.executescript(schema_sql)
        # Check if table already has rows, if so don't re-insert duplicates
        tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        has_data = False
        for t in tables:
            if t != 'sqlite_sequence':
                cnt = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                if cnt > 0:
                    has_data = True
                    break
        if not has_data:
            cursor.executescript(seed_sql)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating sample SQLite DB at {filepath}: {e}")

def setup_demo_environment():
    # 1. Initialize metadata tables
    init_app_database()
    
    # 2. Check if admin user exists
    admin = UserModel.get_by_username('admin')
    if not admin:
        admin_id = UserModel.create(
            username='admin',
            password='admin123',
            full_name='Lead DBA Administrator',
            role='lead_dba',
            is_active=1
        )
        AuditModel.log(
            username='system',
            action='USER_CREATE',
            target='admin',
            details='Initial Super Admin account provisioned',
            status='SUCCESS',
            user_id=admin_id
        )
        print("Created default admin user (admin / admin123 as lead_dba)")
    else:
        # Ensure admin is lead_dba
        UserModel.update(admin['id'], full_name=admin['full_name'], role='lead_dba', is_active=1)

    # 3. Create initial categories if not present
    categories = {c['name']: c['id'] for c in CategoryModel.list_all()}
    
    needed_categories = [
        {"name": "Quotera DB", "description": "High-throughput real-time market pricing and quotera databases", "color": "#6366f1"},
        {"name": "Trade DB", "description": "Low-latency order routing, execution, and fill recording databases", "color": "#0ea5e9"},
        {"name": "Backoffice DB", "description": "Post-trade settlement, accounting, clearing and regulatory reporting", "color": "#10b981"}
    ]

    for cat in needed_categories:
        if cat['name'] not in categories:
            cat_id = CategoryModel.create(cat['name'], cat['description'], cat['color'])
            categories[cat['name']] = cat_id
            AuditModel.log(
                username='admin',
                action='CATEGORY_CREATE',
                target=cat['name'],
                details=f"Created database category {cat['name']}",
                status='SUCCESS'
            )
            print(f"Created category: {cat['name']}")

    # 4. Create actual interactive SQLite databases to simulate multi-node environments
    quotera_schema = '''
        CREATE TABLE IF NOT EXISTS market_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            bid_price REAL NOT NULL,
            ask_price REAL NOT NULL,
            volume INTEGER NOT NULL,
            source TEXT NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS quote_engines (
            engine_id TEXT PRIMARY KEY,
            region TEXT NOT NULL,
            status TEXT NOT NULL,
            latency_ms REAL NOT NULL
        );
    '''

    quotera_ny_seed = '''
        INSERT OR IGNORE INTO quote_engines VALUES ('ENG-NY-01', 'US-EAST', 'ACTIVE', 1.2);
        INSERT OR IGNORE INTO quote_engines VALUES ('ENG-NY-02', 'US-EAST', 'ACTIVE', 1.4);
        INSERT OR IGNORE INTO market_quotes (symbol, bid_price, ask_price, volume, source) VALUES
            ('AAPL', 182.45, 182.50, 450000, 'NASDAQ'),
            ('MSFT', 415.10, 415.20, 230000, 'NASDAQ'),
            ('GOOGL', 175.80, 175.95, 180000, 'NASDAQ'),
            ('NVDA', 128.20, 128.30, 950000, 'NASDAQ'),
            ('AMZN', 186.50, 186.65, 340000, 'NASDAQ');
    '''

    quotera_ldn_seed = '''
        INSERT OR IGNORE INTO quote_engines VALUES ('ENG-LDN-01', 'EU-WEST', 'ACTIVE', 2.1);
        INSERT OR IGNORE INTO quote_engines VALUES ('ENG-LDN-02', 'EU-WEST', 'STANDBY', 2.5);
        INSERT OR IGNORE INTO market_quotes (symbol, bid_price, ask_price, volume, source) VALUES
            ('AAPL', 182.48, 182.52, 420000, 'LSE_CROSS'),
            ('MSFT', 415.05, 415.25, 210000, 'LSE_CROSS'),
            ('GOOGL', 175.85, 175.90, 175000, 'LSE_CROSS'),
            ('NVDA', 128.25, 128.35, 910000, 'LSE_CROSS'),
            ('BATS', 24.30, 24.40, 120000, 'LSE');
    '''

    quotera_tky_seed = '''
        INSERT OR IGNORE INTO quote_engines VALUES ('ENG-TKY-01', 'AP-NORTHEAST', 'ACTIVE', 3.4);
        INSERT OR IGNORE INTO market_quotes (symbol, bid_price, ask_price, volume, source) VALUES
            ('AAPL', 182.40, 182.55, 390000, 'TSE_CROSS'),
            ('MSFT', 415.00, 415.15, 195000, 'TSE_CROSS'),
            ('NVDA', 128.15, 128.40, 880000, 'TSE_CROSS'),
            ('SONY', 84.50, 84.70, 560000, 'TSE');
    '''

    trade_schema = '''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL, -- BUY / SELL
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            status TEXT NOT NULL, -- FILLED / PENDING / REJECTED
            execution_venue TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS risk_limits (
            account_id TEXT PRIMARY KEY,
            max_daily_notional REAL NOT NULL,
            current_utilization REAL NOT NULL
        );
    '''

    trade_pri_seed = '''
        INSERT OR IGNORE INTO risk_limits VALUES ('ACC-QUANT-01', 50000000.0, 18450000.0);
        INSERT OR IGNORE INTO risk_limits VALUES ('ACC-PROP-02', 25000000.0, 9200000.0);
        INSERT OR IGNORE INTO orders VALUES 
            ('ORD-8801', 'ACC-QUANT-01', 'NVDA', 'BUY', 5000, 128.20, 'FILLED', 'ARCA', '2026-10-15 08:30:12'),
            ('ORD-8802', 'ACC-QUANT-01', 'AAPL', 'SELL', 3000, 182.45, 'FILLED', 'BATS', '2026-10-15 08:35:45'),
            ('ORD-8803', 'ACC-PROP-02', 'MSFT', 'BUY', 1500, 415.10, 'FILLED', 'IEX', '2026-10-15 08:42:01'),
            ('ORD-8804', 'ACC-PROP-02', 'GOOGL', 'BUY', 2000, 175.80, 'PENDING', 'NASDAQ', '2026-10-15 08:50:00');
    '''

    trade_sec_seed = '''
        INSERT OR IGNORE INTO risk_limits VALUES ('ACC-QUANT-01', 50000000.0, 18450000.0);
        INSERT OR IGNORE INTO risk_limits VALUES ('ACC-PROP-02', 25000000.0, 9200000.0);
        INSERT OR IGNORE INTO orders VALUES 
            ('ORD-8801', 'ACC-QUANT-01', 'NVDA', 'BUY', 5000, 128.20, 'FILLED', 'ARCA', '2026-10-15 08:30:12'),
            ('ORD-8802', 'ACC-QUANT-01', 'AAPL', 'SELL', 3000, 182.45, 'FILLED', 'BATS', '2026-10-15 08:35:45'),
            ('ORD-8805', 'ACC-HFT-03', 'TSLA', 'BUY', 4000, 245.50, 'FILLED', 'EDGX', '2026-10-15 08:55:10');
    '''

    backoffice_schema = '''
        CREATE TABLE IF NOT EXISTS settlements (
            settlement_id TEXT PRIMARY KEY,
            trade_ref TEXT NOT NULL,
            counterparty TEXT NOT NULL,
            amount_usd REAL NOT NULL,
            status TEXT NOT NULL, -- SETTLED / PENDING / FAILED
            settle_date DATE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS regulatory_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_name TEXT NOT NULL,
            status TEXT NOT NULL,
            verified_by TEXT NOT NULL
        );
    '''

    backoffice_seed = '''
        INSERT OR IGNORE INTO regulatory_audit (report_name, status, verified_by) VALUES
            ('CAT_NMS_613', 'COMPLIANT', 'sec_bot'),
            ('MIFID_II_RTS28', 'COMPLIANT', 'reg_officer_uk'),
            ('TRACE_FIXED_INCOME', 'VERIFIED', 'audit_lead');
        INSERT OR IGNORE INTO settlements VALUES
            ('SET-2026-001', 'TRD-9901', 'GOLDMAN_SACHS', 1540000.0, 'SETTLED', '2026-10-15'),
            ('SET-2026-002', 'TRD-9902', 'MORGAN_STANLEY', 890000.0, 'SETTLED', '2026-10-15'),
            ('SET-2026-003', 'TRD-9903', 'JPMORGAN_CHASE', 3200000.0, 'PENDING', '2026-10-16');
    '''

    ny_db_path = os.path.join(DEMO_DB_DIR, 'quotera_prod_ny.db')
    ldn_db_path = os.path.join(DEMO_DB_DIR, 'quotera_replica_ldn.db')
    tky_db_path = os.path.join(DEMO_DB_DIR, 'quotera_dr_tokyo.db')
    trade_pri_path = os.path.join(DEMO_DB_DIR, 'trade_exec_primary.db')
    trade_sec_path = os.path.join(DEMO_DB_DIR, 'trade_exec_secondary.db')
    backoffice_path = os.path.join(DEMO_DB_DIR, 'backoffice_settlement.db')

    create_sample_sqlite_db(ny_db_path, quotera_schema, quotera_ny_seed)
    create_sample_sqlite_db(ldn_db_path, quotera_schema, quotera_ldn_seed)
    create_sample_sqlite_db(tky_db_path, quotera_schema, quotera_tky_seed)
    create_sample_sqlite_db(trade_pri_path, trade_schema, trade_pri_seed)
    create_sample_sqlite_db(trade_sec_path, trade_schema, trade_sec_seed)
    create_sample_sqlite_db(backoffice_path, backoffice_schema, backoffice_seed)

    # 5. Register Databases in registry
    existing_dbs = {d['name']: d['id'] for d in DatabaseModel.list_all()}

    demo_registrations = [
        # Quotera Group (Simulated local engines + simulated external PostgreSQL/MySQL)
        {
            "name": "Quotera NY (Primary)",
            "category_id": categories["Quotera DB"],
            "engine": "sqlite",
            "host": "localhost",
            "port": 0,
            "database_name": "quotera_prod_ny",
            "username": "quotera_admin",
            "password": "",
            "options": json.dumps({"filepath": ny_db_path}),
            "created_by": "admin"
        },
        {
            "name": "Quotera London (Replica)",
            "category_id": categories["Quotera DB"],
            "engine": "sqlite",
            "host": "localhost",
            "port": 0,
            "database_name": "quotera_replica_ldn",
            "username": "quotera_ro",
            "password": "",
            "options": json.dumps({"filepath": ldn_db_path}),
            "created_by": "admin"
        },
        {
            "name": "Quotera Tokyo (DR)",
            "category_id": categories["Quotera DB"],
            "engine": "sqlite",
            "host": "localhost",
            "port": 0,
            "database_name": "quotera_dr_tokyo",
            "username": "quotera_ro",
            "password": "",
            "options": json.dumps({"filepath": tky_db_path}),
            "created_by": "admin"
        },
        # Trade DB Group
        {
            "name": "Trade Execution (Primary)",
            "category_id": categories["Trade DB"],
            "engine": "sqlite",
            "host": "localhost",
            "port": 0,
            "database_name": "trade_exec_primary",
            "username": "trade_dba",
            "password": "",
            "options": json.dumps({"filepath": trade_pri_path}),
            "created_by": "admin"
        },
        {
            "name": "Trade Execution (Secondary)",
            "category_id": categories["Trade DB"],
            "engine": "sqlite",
            "host": "localhost",
            "port": 0,
            "database_name": "trade_exec_secondary",
            "username": "trade_dba",
            "password": "",
            "options": json.dumps({"filepath": trade_sec_path}),
            "created_by": "admin"
        },
        # Backoffice DB Group
        {
            "name": "Backoffice Settlement Main",
            "category_id": categories["Backoffice DB"],
            "engine": "sqlite",
            "host": "localhost",
            "port": 0,
            "database_name": "backoffice_settlement",
            "username": "bo_admin",
            "password": "",
            "options": json.dumps({"filepath": backoffice_path}),
            "created_by": "admin"
        },
        # PostgreSQL & MySQL & Oracle templates for real cluster connection
        {
            "name": "Quotera Postgres Cloud (Template)",
            "category_id": categories["Quotera DB"],
            "engine": "postgresql",
            "host": "pg-cluster.internal.trading.net",
            "port": 5432,
            "database_name": "quotera_prod",
            "username": "dba_pg_admin",
            "password": "sample_secret_password",
            "options": json.dumps({"sslmode": "require"}),
            "created_by": "admin"
        },
        {
            "name": "Trade MySQL Cluster (Template)",
            "category_id": categories["Trade DB"],
            "engine": "mysql",
            "host": "mysql-trade.internal.trading.net",
            "port": 3306,
            "database_name": "trading_db",
            "username": "trade_root",
            "password": "sample_mysql_password",
            "options": json.dumps({"charset": "utf8mb4"}),
            "created_by": "admin"
        },
        {
            "name": "Settlement Oracle Exadata (Template)",
            "category_id": categories["Backoffice DB"],
            "engine": "oracle",
            "host": "oracle-exa.internal.trading.net",
            "port": 1521,
            "database_name": "ORCLPDB1",
            "username": "c##dba_settle",
            "password": "sample_oracle_password",
            "options": json.dumps({"service_name": "ORCLPDB1.local"}),
            "created_by": "admin"
        }
    ]

    for db_cfg in demo_registrations:
        if db_cfg['name'] not in existing_dbs:
            DatabaseModel.create(
                name=db_cfg['name'],
                category_id=db_cfg['category_id'],
                engine=db_cfg['engine'],
                host=db_cfg['host'],
                port=db_cfg['port'],
                database_name=db_cfg['database_name'],
                username=db_cfg['username'],
                password=db_cfg['password'],
                options=db_cfg['options'],
                created_by=db_cfg['created_by']
            )
            AuditModel.log(
                username='admin',
                action='DB_CREATE',
                target=db_cfg['name'],
                details=f"Registered database {db_cfg['name']} ({db_cfg['engine'].upper()})",
                status='SUCCESS'
            )
            print(f"Registered DB: {db_cfg['name']}")

if __name__ == '__main__':
    setup_demo_environment()
    print("Database environment initialized successfully.")
