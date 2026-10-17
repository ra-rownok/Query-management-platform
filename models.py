import os
from contextlib import contextmanager
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

# ----------------- Environment Configuration -----------------

def load_dotenv_file(filepath=None):
    """Loads environment variables from .env file."""
    if not filepath:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
        except Exception as e:
            print(f"Warning: Failed to load .env file: {e}")

load_dotenv_file()

def get_database_uri():
    """Resolves PostgreSQL connection URI."""
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url
    
    user = os.environ.get('POSTGRES_USER')
    password = os.environ.get('POSTGRES_PASSWORD')
    host = os.environ.get('POSTGRES_HOST')
    port = os.environ.get('POSTGRES_PORT')
    dbname = os.environ.get('POSTGRES_DB')
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

def get_database_schema():
    return os.environ.get('POSTGRES_SCHEMA')

# ----------------- Connection & Pool Management -----------------

_POOL = None

def get_pool():
    global _POOL
    if _POOL is None:
        dsn = get_database_uri()
        _POOL = ThreadedConnectionPool(minconn=1, maxconn=20, dsn=dsn, connect_timeout=5)
    return _POOL

class PooledConnection:
    """Helper providing RealDictCursor and direct execute() on pooled connections."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

@contextmanager
def get_db_connection():
    """Provides a managed PostgreSQL connection with auto-commit, rollback, and pool return."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        # Re-establish if connection was closed remotely
        if conn.closed != 0:
            conn = psycopg2.connect(get_database_uri())
        yield PooledConnection(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            pool.putconn(conn)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

# ----------------- Database Schema Initialization -----------------

def init_app_database():
    """Initializes metadata tables in PostgreSQL."""
    schema = get_database_schema()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if schema and schema != 'public':
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
            cursor.execute(f"SET search_path TO {schema}, public;")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name VARCHAR(255),
                role VARCHAR(50) NOT NULL DEFAULT 'dba',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP WITH TIME ZONE
            );
            CREATE TABLE IF NOT EXISTS db_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                color VARCHAR(50) DEFAULT '#4f46e5',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS db_connections (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                category_id INTEGER REFERENCES db_categories(id) ON DELETE SET NULL,
                engine VARCHAR(50) NOT NULL,
                host VARCHAR(255),
                port INTEGER,
                database_name VARCHAR(255) NOT NULL,
                username VARCHAR(255),
                password TEXT,
                options TEXT,
                is_enabled INTEGER DEFAULT 1,
                created_by VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                username VARCHAR(255) NOT NULL,
                action VARCHAR(100) NOT NULL,
                target VARCHAR(255),
                details TEXT,
                ip_address VARCHAR(100),
                status VARCHAR(50) DEFAULT 'SUCCESS',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS query_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                username VARCHAR(255) NOT NULL,
                query_text TEXT NOT NULL,
                target_type VARCHAR(50) NOT NULL,
                target_identifier VARCHAR(255),
                target_count INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                total_duration_ms DOUBLE PRECISION DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS user_db_permissions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                db_id INTEGER NOT NULL REFERENCES db_connections(id) ON DELETE CASCADE,
                permission_level VARCHAR(50) NOT NULL,
                granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                granted_by VARCHAR(255),
                UNIQUE(user_id, db_id)
            );
            CREATE TABLE IF NOT EXISTS saved_queries (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                query_text TEXT NOT NULL,
                engine_hint VARCHAR(50) DEFAULT 'any',
                created_by VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
    print(f"[POSTGRESQL] Database tables initialized successfully (schema: {schema}).")

# ----------------- Model Classes -----------------

class PermissionModel:
    @staticmethod
    def get_user_permissions(user_id):
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    "SELECT db_id, permission_level FROM user_db_permissions WHERE user_id = %s;",
                    (user_id,)
                ).fetchall()
                return {r['db_id']: r['permission_level'] for r in rows}
        except Exception as e:
            print(f"Error fetching permissions for user {user_id}: {e}")
            return {}

    @staticmethod
    def set_user_permissions(user_id, permissions_dict, granted_by='super_admin'):
        """permissions_dict: {db_id: 'read_write' | 'read_only'}"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_db_permissions WHERE user_id = %s;", (user_id,))
                for db_id, perm in permissions_dict.items():
                    if perm in ['read_write', 'read_only']:
                        cursor.execute(
                            "INSERT INTO user_db_permissions (user_id, db_id, permission_level, granted_by) VALUES (%s, %s, %s, %s);",
                            (user_id, int(db_id), perm, granted_by)
                        )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error setting permissions for user {user_id}: {e}")
            raise e

    @staticmethod
    def get_accessible_databases(user_id, user_role, enabled_only=True):
        """Returns databases accessible to the user with permission_level annotated."""
        try:
            all_dbs = DatabaseModel.list_all(enabled_only=enabled_only)
            
            # Super admin (lead_dba) sees and can write to all databases
            if user_role == 'lead_dba':
                for db in all_dbs:
                    db['permission_level'] = 'read_write'
                return all_dbs

            # Standard DBA or Auditor: only return explicitly granted databases
            perms = PermissionModel.get_user_permissions(user_id)
            accessible = []
            for db in all_dbs:
                if db['id'] in perms:
                    db_copy = dict(db)
                    if user_role == 'auditor':
                        db_copy['permission_level'] = 'read_only'
                    else:
                        db_copy['permission_level'] = perms[db['id']]
                    accessible.append(db_copy)
            return accessible
        except Exception as e:
            print(f"Error resolving accessible databases for user {user_id}: {e}")
            return []

class UserModel:
    @staticmethod
    def get_by_id(user_id):
        try:
            with get_db_connection() as conn:
                row = conn.execute("SELECT * FROM users WHERE id = %s;", (user_id,)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error fetching user by id {user_id}: {e}")
            return None

    @staticmethod
    def get_by_username(username):
        try:
            with get_db_connection() as conn:
                row = conn.execute("SELECT * FROM users WHERE username = %s;", (username,)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error fetching user by username {username}: {e}")
            return None

    @staticmethod
    def create(username, password, full_name="", role="dba", is_active=1):
        try:
            password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        except Exception:
            import hashlib
            password_hash = "sha256$" + hashlib.sha256(password.encode('utf-8')).hexdigest()
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, full_name, role, is_active) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                    (username, password_hash, full_name, role, is_active)
                )
                res = cursor.fetchone()
                conn.commit()
                return res['id']
        except Exception as e:
            print(f"Error creating user {username}: {e}")
            raise e

    @staticmethod
    def update(user_id, full_name, role, is_active, password=None):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                if password:
                    try:
                        password_hash = generate_password_hash(password, method='pbkdf2:sha256')
                    except Exception:
                        import hashlib
                        password_hash = "sha256$" + hashlib.sha256(password.encode('utf-8')).hexdigest()
                    cursor.execute(
                        "UPDATE users SET full_name = %s, role = %s, is_active = %s, password_hash = %s WHERE id = %s;",
                        (full_name, role, is_active, password_hash, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET full_name = %s, role = %s, is_active = %s WHERE id = %s;",
                        (full_name, role, is_active, user_id)
                    )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating user {user_id}: {e}")
            raise e

    @staticmethod
    def delete(user_id):
        try:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM user_db_permissions WHERE user_id = %s;", (user_id,))
                conn.execute("DELETE FROM users WHERE id = %s;", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error deleting user {user_id}: {e}")
            raise e

    @staticmethod
    def verify_password(stored_hash, password):
        try:
            if not stored_hash or not password:
                return False
            if stored_hash.startswith("sha256$"):
                import hashlib
                return stored_hash == "sha256$" + hashlib.sha256(password.encode('utf-8')).hexdigest()
            return check_password_hash(stored_hash, password)
        except Exception as e:
            print(f"Error verifying password: {e}")
            return False

    @staticmethod
    def update_last_login(user_id):
        try:
            with get_db_connection() as conn:
                conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s;", (user_id,))
                conn.commit()
        except Exception as e:
            print(f"Error updating last login for user {user_id}: {e}")

    @staticmethod
    def list_all():
        try:
            with get_db_connection() as conn:
                rows = conn.execute("SELECT id, username, full_name, role, is_active, created_at, last_login FROM users ORDER BY id ASC;").fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error listing users: {e}")
            return []

class CategoryModel:
    @staticmethod
    def list_all():
        try:
            with get_db_connection() as conn:
                rows = conn.execute('''
                    SELECT c.*, COUNT(d.id) as db_count 
                    FROM db_categories c 
                    LEFT JOIN db_connections d ON c.id = d.category_id AND d.is_enabled = 1
                    GROUP BY c.id, c.name, c.description, c.color, c.created_at
                    ORDER BY c.name ASC;
                ''').fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error listing categories: {e}")
            return []

    @staticmethod
    def get_by_id(cat_id):
        try:
            with get_db_connection() as conn:
                row = conn.execute("SELECT * FROM db_categories WHERE id = %s;", (cat_id,)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error fetching category {cat_id}: {e}")
            return None

    @staticmethod
    def create(name, description="", color="#4f46e5"):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO db_categories (name, description, color) VALUES (%s, %s, %s) RETURNING id;",
                    (name, description, color)
                )
                res = cursor.fetchone()
                conn.commit()
                return res['id']
        except Exception as e:
            print(f"Error creating category {name}: {e}")
            raise e

class DatabaseModel:
    @staticmethod
    def list_all(enabled_only=False):
        try:
            query = '''
                SELECT d.*, c.name as category_name, c.color as category_color 
                FROM db_connections d
                LEFT JOIN db_categories c ON d.category_id = c.id
            '''
            if enabled_only:
                query += " WHERE d.is_enabled = 1"
            query += " ORDER BY COALESCE(c.name, 'Uncategorized') ASC, d.name ASC;"
            
            with get_db_connection() as conn:
                rows = conn.execute(query).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error listing databases: {e}")
            return []

    @staticmethod
    def get_by_id(db_id):
        try:
            with get_db_connection() as conn:
                row = conn.execute('''
                    SELECT d.*, c.name as category_name, c.color as category_color 
                    FROM db_connections d
                    LEFT JOIN db_categories c ON d.category_id = c.id
                    WHERE d.id = %s;
                ''', (db_id,)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error fetching database {db_id}: {e}")
            return None

    @staticmethod
    def get_by_category(category_id):
        try:
            with get_db_connection() as conn:
                rows = conn.execute('''
                    SELECT d.*, c.name as category_name, c.color as category_color 
                    FROM db_connections d
                    JOIN db_categories c ON d.category_id = c.id
                    WHERE d.category_id = %s AND d.is_enabled = 1
                    ORDER BY d.name ASC;
                ''', (category_id,)).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error fetching databases for category {category_id}: {e}")
            return []

    @staticmethod
    def create(name, category_id, engine, host, port, database_name, username, password, options="", created_by=""):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO db_connections (name, category_id, engine, host, port, database_name, username, password, options, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                ''', (name, category_id, engine.lower(), host, port, database_name, username, password, options, created_by))
                res = cursor.fetchone()
                conn.commit()
                return res['id']
        except Exception as e:
            print(f"Error creating database {name}: {e}")
            raise e

    @staticmethod
    def update(db_id, name, category_id, engine, host, port, database_name, username, password, options="", is_enabled=1):
        try:
            with get_db_connection() as conn:
                if password:
                    conn.execute('''
                        UPDATE db_connections 
                        SET name = %s, category_id = %s, engine = %s, host = %s, port = %s, 
                            database_name = %s, username = %s, password = %s, options = %s, is_enabled = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    ''', (name, category_id, engine.lower(), host, port, database_name, username, password, options, is_enabled, db_id))
                else:
                    conn.execute('''
                        UPDATE db_connections 
                        SET name = %s, category_id = %s, engine = %s, host = %s, port = %s, 
                            database_name = %s, username = %s, options = %s, is_enabled = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s;
                    ''', (name, category_id, engine.lower(), host, port, database_name, username, options, is_enabled, db_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating database {db_id}: {e}")
            raise e

    @staticmethod
    def delete(db_id):
        try:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM user_db_permissions WHERE db_id = %s;", (db_id,))
                conn.execute("DELETE FROM db_connections WHERE id = %s;", (db_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error deleting database {db_id}: {e}")
            raise e

class AuditModel:
    @staticmethod
    def log(username, action, target="", details="", ip_address="127.0.0.1", status="SUCCESS", user_id=None):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                if action == 'LOGIN':
                    cursor.execute('''
                        SELECT id FROM audit_logs 
                        WHERE username = %s AND action = 'LOGIN' AND status = %s
                        AND created_at >= NOW() - INTERVAL '3 seconds';
                    ''', (username, status))
                    recent = cursor.fetchone()
                    if recent:
                        return recent['id']

                cursor.execute('''
                    INSERT INTO audit_logs (user_id, username, action, target, details, ip_address, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
                ''', (user_id, username, action, target, details, ip_address, status))
                res = cursor.fetchone()
                conn.commit()
                return res['id']
        except Exception as e:
            print(f"Warning: Failed to record audit log: {e}")
            return None

    @staticmethod
    def list_recent(limit=100, action=None, search=None, username=None):
        try:
            query = "SELECT * FROM audit_logs WHERE 1=1"
            params = []
            if username:
                query += " AND username = %s"
                params.append(username)
            if action:
                query += " AND action = %s"
                params.append(action)
            if search:
                query += " AND (username LIKE %s OR target LIKE %s OR details LIKE %s)"
                s = f"%{search}%"
                params.extend([s, s, s])
            query += " ORDER BY id DESC LIMIT %s;"
            params.append(limit)

            with get_db_connection() as conn:
                rows = conn.execute(query, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error fetching audit logs: {e}")
            return []

class QueryHistoryModel:
    @staticmethod
    def record(username, query_text, target_type, target_identifier, target_count, success_count, failed_count, total_duration_ms, user_id=None):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO query_history (user_id, username, query_text, target_type, target_identifier, target_count, success_count, failed_count, total_duration_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
                ''', (user_id, username, query_text, target_type, str(target_identifier), target_count, success_count, failed_count, total_duration_ms))
                res = cursor.fetchone()
                conn.commit()
                return res['id']
        except Exception as e:
            print(f"Warning: Failed to record query history: {e}")
            return None

    @staticmethod
    def list_recent(limit=30, username=None):
        try:
            query = "SELECT * FROM query_history WHERE 1=1"
            params = []
            if username:
                query += " AND username = %s"
                params.append(username)
            query += " ORDER BY id DESC LIMIT %s;"
            params.append(limit)

            with get_db_connection() as conn:
                rows = conn.execute(query, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error fetching query history: {e}")
            return []

class SavedQueryModel:
    @staticmethod
    def list_all():
        try:
            with get_db_connection() as conn:
                rows = conn.execute("SELECT * FROM saved_queries ORDER BY title ASC;").fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error listing saved queries: {e}")
            return []

    @staticmethod
    def create(title, query_text, description="", engine_hint="any", created_by=""):
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO saved_queries (title, description, query_text, engine_hint, created_by)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id;
                ''', (title, description, query_text, engine_hint, created_by))
                res = cursor.fetchone()
                conn.commit()
                return res['id']
        except Exception as e:
            print(f"Error creating saved query {title}: {e}")
            raise e
