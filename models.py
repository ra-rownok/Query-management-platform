import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'platform.db')

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_app_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                role TEXT NOT NULL DEFAULT 'dba',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')

        # Database Categories
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS db_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                color TEXT DEFAULT '#4f46e5',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Database Registry
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS db_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                category_id INTEGER NOT NULL,
                engine TEXT NOT NULL, -- 'postgresql', 'mysql', 'oracle', 'sqlite'
                host TEXT,
                port INTEGER,
                database_name TEXT NOT NULL,
                username TEXT,
                password TEXT,
                options TEXT, -- JSON/string for extra params (e.g. sslmode, service_name, filepath)
                is_enabled INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES db_categories(id) ON DELETE RESTRICT
            )
        ''')

        # Audit Logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                action TEXT NOT NULL, -- LOGIN, LOGOUT, USER_CREATE, DB_CREATE, DB_UPDATE, DB_DELETE, QUERY_EXECUTE
                target TEXT,
                details TEXT,
                ip_address TEXT,
                status TEXT DEFAULT 'SUCCESS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Query History
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                query_text TEXT NOT NULL,
                target_type TEXT NOT NULL, -- 'single', 'category', 'all'
                target_identifier TEXT, -- DB id, category id, or 'all'
                target_count INTEGER DEFAULT 1,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                total_duration_ms REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # User Database Permissions (Role-based & Granular per DB)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_db_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                db_id INTEGER NOT NULL,
                permission_level TEXT NOT NULL, -- 'read_write' or 'read_only'
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                granted_by TEXT,
                UNIQUE(user_id, db_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (db_id) REFERENCES db_connections(id) ON DELETE CASCADE
            )
        ''')

        # Saved Queries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                query_text TEXT NOT NULL,
                engine_hint TEXT DEFAULT 'any',
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()

class PermissionModel:
    @staticmethod
    def get_user_permissions(user_id):
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    "SELECT db_id, permission_level FROM user_db_permissions WHERE user_id = ?",
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
                cursor.execute("DELETE FROM user_db_permissions WHERE user_id = ?", (user_id,))
                for db_id, perm in permissions_dict.items():
                    if perm in ['read_write', 'read_only']:
                        cursor.execute(
                            "INSERT INTO user_db_permissions (user_id, db_id, permission_level, granted_by) VALUES (?, ?, ?, ?)",
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
                    # Auditors are always read-only, regardless of assigned level
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
                row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
                return dict(row) if row else None
        except Exception as e:
            print(f"Error fetching user by id {user_id}: {e}")
            return None

    @staticmethod
    def get_by_username(username):
        try:
            with get_db_connection() as conn:
                row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
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
                    "INSERT INTO users (username, password_hash, full_name, role, is_active) VALUES (?, ?, ?, ?, ?)",
                    (username, password_hash, full_name, role, is_active)
                )
                conn.commit()
                return cursor.lastrowid
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
                        "UPDATE users SET full_name = ?, role = ?, is_active = ?, password_hash = ? WHERE id = ?",
                        (full_name, role, is_active, password_hash, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET full_name = ?, role = ?, is_active = ? WHERE id = ?",
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
                conn.execute("DELETE FROM user_db_permissions WHERE user_id = ?", (user_id,))
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
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
                conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
                conn.commit()
        except Exception as e:
            print(f"Error updating last login for user {user_id}: {e}")

    @staticmethod
    def list_all():
        try:
            with get_db_connection() as conn:
                rows = conn.execute("SELECT id, username, full_name, role, is_active, created_at, last_login FROM users ORDER BY id ASC").fetchall()
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
                    GROUP BY c.id
                    ORDER BY c.name ASC
                ''').fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error listing categories: {e}")
            return []

    @staticmethod
    def get_by_id(cat_id):
        try:
            with get_db_connection() as conn:
                row = conn.execute("SELECT * FROM db_categories WHERE id = ?", (cat_id,)).fetchone()
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
                    "INSERT INTO db_categories (name, description, color) VALUES (?, ?, ?)",
                    (name, description, color)
                )
                conn.commit()
                return cursor.lastrowid
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
                JOIN db_categories c ON d.category_id = c.id
            '''
            if enabled_only:
                query += " WHERE d.is_enabled = 1"
            query += " ORDER BY c.name ASC, d.name ASC"
            
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
                    JOIN db_categories c ON d.category_id = c.id
                    WHERE d.id = ?
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
                    WHERE d.category_id = ? AND d.is_enabled = 1
                    ORDER BY d.name ASC
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, category_id, engine.lower(), host, port, database_name, username, password, options, created_by))
                conn.commit()
                return cursor.lastrowid
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
                        SET name = ?, category_id = ?, engine = ?, host = ?, port = ?, 
                            database_name = ?, username = ?, password = ?, options = ?, is_enabled = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (name, category_id, engine.lower(), host, port, database_name, username, password, options, is_enabled, db_id))
                else:
                    conn.execute('''
                        UPDATE db_connections 
                        SET name = ?, category_id = ?, engine = ?, host = ?, port = ?, 
                            database_name = ?, username = ?, options = ?, is_enabled = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
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
                conn.execute("DELETE FROM user_db_permissions WHERE db_id = ?", (db_id,))
                conn.execute("DELETE FROM db_connections WHERE id = ?", (db_id,))
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
                # Deduplicate rapid accidental login submissions (e.g. rapid double-clicks)
                if action == 'LOGIN':
                    recent = conn.execute('''
                        SELECT id FROM audit_logs 
                        WHERE username = ? AND action = 'LOGIN' AND status = ?
                        AND datetime(created_at) >= datetime('now', '-3 seconds')
                    ''', (username, status)).fetchone()
                    if recent:
                        return recent['id']

                cursor.execute('''
                    INSERT INTO audit_logs (user_id, username, action, target, details, ip_address, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, action, target, details, ip_address, status))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Warning: Failed to record audit log: {e}")
            return None

    @staticmethod
    def list_recent(limit=100, action=None, search=None, username=None):
        try:
            query = "SELECT * FROM audit_logs WHERE 1=1"
            params = []
            if username:
                query += " AND username = ?"
                params.append(username)
            if action:
                query += " AND action = ?"
                params.append(action)
            if search:
                query += " AND (username LIKE ? OR target LIKE ? OR details LIKE ?)"
                s = f"%{search}%"
                params.extend([s, s, s])
            query += " ORDER BY id DESC LIMIT ?"
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, query_text, target_type, str(target_identifier), target_count, success_count, failed_count, total_duration_ms))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Warning: Failed to record query history: {e}")
            return None

    @staticmethod
    def list_recent(limit=30, username=None):
        try:
            query = "SELECT * FROM query_history WHERE 1=1"
            params = []
            if username:
                query += " AND username = ?"
                params.append(username)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            with get_db_connection() as conn:
                rows = conn.execute(query, params).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error fetching query history: {e}")
            return []
