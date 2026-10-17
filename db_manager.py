import time
import re
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine, text
import psycopg2
import pymysql

try:
    import oracledb
except ImportError:
    oracledb = None

class EngineDialectHelper:
    """Provides engine awareness, query validation, and syntax compatibility warnings."""
    
    @staticmethod
    def inspect_query(query: str, target_engines: set):
        try:
            if not query or not target_engines:
                return []
            warnings = []
            q_upper = query.upper()
            
            # Check for LIMIT vs ROWNUM
            has_limit = re.search(r'\bLIMIT\b', q_upper) is not None
            has_rownum = 'ROWNUM' in q_upper
            has_dual = 'FROM DUAL' in q_upper
            has_backticks = '`' in query
            has_ilike = re.search(r'\bILIKE\b', q_upper) is not None
            
            if 'oracle' in target_engines:
                if has_limit and not ('FETCH FIRST' in q_upper or 'OFFSET' in q_upper):
                    warnings.append("Oracle warning: Oracle 11g and below does not support 'LIMIT'. Use 'ROWNUM' or (Oracle 12c+) 'FETCH FIRST N ROWS ONLY'.")
                if has_backticks:
                    warnings.append("Oracle warning: Backtick identifiers (`) are not standard SQL and will fail on Oracle.")
                if has_ilike:
                    warnings.append("Oracle warning: 'ILIKE' is specific to PostgreSQL and will fail on Oracle.")

            if 'postgresql' in target_engines:
                if has_backticks:
                    warnings.append("PostgreSQL warning: PostgreSQL does not support backticks (`) for identifiers. Use double quotes (\") instead.")
                if has_rownum:
                    warnings.append("PostgreSQL warning: 'ROWNUM' is an Oracle pseudocolumn. Use 'LIMIT' in PostgreSQL.")
                if has_dual:
                    warnings.append("PostgreSQL notice: 'FROM DUAL' is an Oracle construct (PostgreSQL supports SELECT expressions without FROM).")

            if 'mysql' in target_engines:
                if has_rownum:
                    warnings.append("MySQL warning: 'ROWNUM' is an Oracle pseudocolumn. Use 'LIMIT' in MySQL.")
                if has_ilike:
                    warnings.append("MySQL warning: 'ILIKE' is specific to PostgreSQL. Use 'LIKE' in MySQL.")

            return warnings
        except Exception as e:
            return [f"Notice: Engine dialect inspection encountered an issue: {str(e)}"]

    WRITE_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE',
        'REPLACE', 'GRANT', 'REVOKE', 'MERGE', 'UPSERT'
    }

    @classmethod
    def is_write_query(cls, query: str) -> bool:
        try:
            if not query:
                return False
            # Strip comments
            cleaned = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
            cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
            tokens = re.findall(r'\b[A-Za-z_]+\b', cleaned)
            for token in tokens[:5]:
                if token.upper() in cls.WRITE_KEYWORDS:
                    return True
            return False
        except Exception:
            return False

    @staticmethod
    def get_ping_query(engine: str):
        try:
            engine = (engine or '').lower()
            if engine == 'oracle':
                return "SELECT 1 FROM DUAL"
            return "SELECT 1"
        except Exception:
            return "SELECT 1"

class DatabaseManager:
    @staticmethod
    def build_connection_uri(db_info: dict) -> str:
        try:
            engine = db_info.get('engine', '').lower()
            host = db_info.get('host', 'localhost')
            port = db_info.get('port')
            dbname = db_info.get('database_name', '')
            user = db_info.get('username', '')
            password = db_info.get('password', '') or ''
            options = db_info.get('options', '')

            # Check options for custom connection string or sqlite path
            opt_dict = {}
            if options:
                try:
                    opt_dict = json.loads(options) if isinstance(options, str) else dict(options)
                except Exception:
                    opt_dict = {}

            if engine == 'sqlite':
                # Local or demo SQLite DB
                path = opt_dict.get('filepath') or dbname
                return f"sqlite:///{path}"

            elif engine == 'postgresql':
                port_str = f":{port}" if port else ":5432"
                auth_str = f"{user}:{password}@" if user else ""
                ssl = f"?sslmode={opt_dict.get('sslmode', 'prefer')}"
                return f"postgresql+psycopg2://{auth_str}{host}{port_str}/{dbname}{ssl}"

            elif engine == 'mysql':
                port_str = f":{port}" if port else ":3306"
                auth_str = f"{user}:{password}@" if user else ""
                charset = f"?charset={opt_dict.get('charset', 'utf8mb4')}"
                return f"mysql+pymysql://{auth_str}{host}{port_str}/{dbname}{charset}"

            elif engine == 'oracle':
                port_str = f":{port}" if port else ":1521"
                service_name = opt_dict.get('service_name', dbname)
                auth_str = f"{user}:{password}@" if user else ""
                return f"oracle+oracledb://{auth_str}{host}{port_str}/?service_name={service_name}"

            else:
                raise ValueError(f"Unsupported database engine: '{engine}'")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Failed to build connection URI for database {db_info.get('name', 'unknown')}: {str(e)}")

    @classmethod
    def test_connection(cls, db_info: dict, timeout=5) -> dict:
        start_time = time.time()
        engine_type = db_info.get('engine', '').lower()
        try:
            uri = cls.build_connection_uri(db_info)
            # Create engine with quick connection timeout
            engine_args = {"connect_args": {}}
            if engine_type == 'postgresql':
                engine_args["connect_args"]["connect_timeout"] = timeout
            elif engine_type == 'mysql':
                engine_args["connect_args"]["connect_timeout"] = timeout

            db_engine = create_engine(uri, pool_pre_ping=True, **engine_args)
            ping_sql = EngineDialectHelper.get_ping_query(engine_type)
            with db_engine.connect() as conn:
                conn.execute(text(ping_sql))
            
            duration_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "success": True,
                "message": f"Successfully connected to {db_info.get('name')} ({engine_type.upper()})",
                "duration_ms": duration_ms
            }
        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            error_reason = str(e).strip()
            # Clean up long password/credentials exposure in errors if any
            if db_info.get('password'):
                error_reason = error_reason.replace(db_info['password'], '******')
            return {
                "success": False,
                "message": error_reason,
                "duration_ms": duration_ms
            }

    @classmethod
    def execute_single_query(cls, db_info: dict, query_text: str, max_rows=500, timeout=15) -> dict:
        start_time = time.time()
        db_id = db_info.get('id')
        db_name = db_info.get('name')
        category_name = db_info.get('category_name', 'General')
        engine_type = db_info.get('engine', '').lower()

        result = {
            "db_id": db_id,
            "db_name": db_name,
            "category_name": category_name,
            "engine": engine_type,
            "status": "FAILED",
            "duration_ms": 0,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "affected_rows": 0,
            "is_select": False,
            "error_message": None,
            "error_type": None
        }

        try:
            perm_level = db_info.get('permission_level', 'read_write')
            if perm_level == 'read_only' and EngineDialectHelper.is_write_query(query_text):
                result["error_type"] = "PermissionDenied"
                result["error_message"] = f"Permission Denied: User has READ-ONLY access to database '{db_name}'. Write operations (INSERT, UPDATE, DELETE, DDL) are restricted."
                return result

            uri = cls.build_connection_uri(db_info)
            engine_args = {"connect_args": {}}
            if engine_type == 'postgresql':
                engine_args["connect_args"]["connect_timeout"] = timeout
            elif engine_type == 'mysql':
                engine_args["connect_args"]["connect_timeout"] = timeout

            db_engine = create_engine(uri, **engine_args)

            # Check if query contains multiple statements or is select
            clean_query = query_text.strip().rstrip(';')
            
            with db_engine.connect() as connection:
                trans = connection.begin()
                try:
                    exec_result = connection.execute(text(clean_query))
                    
                    if exec_result.returns_rows:
                        result["is_select"] = True
                        columns = list(exec_result.keys())
                        result["columns"] = columns
                        
                        raw_rows = exec_result.fetchmany(max_rows)
                        result["row_count"] = len(raw_rows)
                        
                        # Serialize rows safely into JSON-friendly format
                        formatted_rows = []
                        for row in raw_rows:
                            formatted_row = {}
                            for col_idx, col_name in enumerate(columns):
                                val = row[col_idx]
                                if val is None:
                                    formatted_row[col_name] = None
                                elif isinstance(val, (int, float, bool, str)):
                                    formatted_row[col_name] = val
                                else:
                                    formatted_row[col_name] = str(val)
                            formatted_rows.append(formatted_row)
                        result["rows"] = formatted_rows
                    else:
                        result["is_select"] = False
                        result["affected_rows"] = exec_result.rowcount if exec_result.rowcount != -1 else 0

                    trans.commit()
                    result["status"] = "SUCCESS"
                except Exception as query_err:
                    try:
                        trans.rollback()
                    except Exception:
                        pass
                    raise query_err

            result["duration_ms"] = round((time.time() - start_time) * 1000, 2)
            return result

        except Exception as e:
            result["duration_ms"] = round((time.time() - start_time) * 1000, 2)
            result["status"] = "FAILED"
            result["error_type"] = type(e).__name__
            err_msg = str(e).strip()
            if db_info.get('password'):
                err_msg = err_msg.replace(db_info['password'], '******')
            result["error_message"] = err_msg
            return result

    @classmethod
    def execute_across_databases(cls, databases: list, query_text: str, max_workers=10, max_rows=500) -> dict:
        """Executes a query across a list of target databases concurrently."""
        overall_start = time.time()
        results = []
        try:
            target_engines = {db['engine'].lower() for db in databases if 'engine' in db}
            
            # Engine awareness warnings
            try:
                warnings = EngineDialectHelper.inspect_query(query_text, target_engines)
            except Exception as w_err:
                warnings = [f"Warning analysis skipped: {str(w_err)}"]

            # Run concurrent queries
            try:
                with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(databases)))) as executor:
                    future_to_db = {
                        executor.submit(cls.execute_single_query, db, query_text, max_rows): db 
                        for db in databases
                    }
                    for future in as_completed(future_to_db):
                        db = future_to_db[future]
                        try:
                            db_res = future.result()
                            results.append(db_res)
                        except Exception as fut_err:
                            results.append({
                                "db_id": db.get('id'),
                                "db_name": db.get('name'),
                                "category_name": db.get('category_name', 'General'),
                                "engine": db.get('engine', '').lower(),
                                "status": "FAILED",
                                "duration_ms": 0,
                                "columns": [],
                                "rows": [],
                                "row_count": 0,
                                "affected_rows": 0,
                                "is_select": False,
                                "error_message": f"Thread execution error: {str(fut_err)}",
                                "error_type": type(fut_err).__name__
                            })
            except Exception as pool_err:
                for db in databases:
                    results.append({
                        "db_id": db.get('id'),
                        "db_name": db.get('name'),
                        "category_name": db.get('category_name', 'General'),
                        "engine": db.get('engine', '').lower(),
                        "status": "FAILED",
                        "duration_ms": 0,
                        "columns": [],
                        "rows": [],
                        "row_count": 0,
                        "affected_rows": 0,
                        "is_select": False,
                        "error_message": f"Pool execution failure: {str(pool_err)}",
                        "error_type": type(pool_err).__name__
                    })

            # Sort results by category and database name for clean display
            try:
                results.sort(key=lambda x: (x.get('category_name', ''), x.get('db_name', '')))
            except Exception:
                pass

            total_duration = round((time.time() - overall_start) * 1000, 2)
            success_count = sum(1 for r in results if r.get('status') == 'SUCCESS')
            failed_count = sum(1 for r in results if r.get('status') == 'FAILED')

            return {
                "total_targets": len(databases),
                "success_count": success_count,
                "failed_count": failed_count,
                "total_duration_ms": total_duration,
                "target_engines": list(target_engines),
                "warnings": warnings,
                "results": results
            }
        except Exception as e:
            total_duration = round((time.time() - overall_start) * 1000, 2)
            return {
                "total_targets": len(databases),
                "success_count": 0,
                "failed_count": len(databases),
                "total_duration_ms": total_duration,
                "target_engines": [],
                "warnings": [f"Execution error: {str(e)}"],
                "results": results
            }
