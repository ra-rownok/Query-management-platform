import os
import json
import functools
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
from models import (
    init_app_database, UserModel, CategoryModel, DatabaseModel, 
    AuditModel, QueryHistoryModel, PermissionModel
)
from db_manager import DatabaseManager, EngineDialectHelper

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'multi-db-quant-dba-secret-key-2026-xyz')

# Helper: Decorator for login requirement
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not getattr(g, 'user', None) or 'user_id' not in session:
            was_deactivated = getattr(g, 'was_deactivated', False)
            session.clear()
            
            # API / AJAX JSON request
            if request.path.startswith('/api/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                msg = 'Your account has been deactivated by an administrator.' if was_deactivated else 'Authentication required. Please log in.'
                return jsonify({
                    'success': False,
                    'error': msg,
                    'redirect': url_for('login')
                }), 401
            
            # Standard browser navigation
            if was_deactivated:
                flash('Your account has been deactivated by an administrator. Please contact your system DBA.', 'error')
                return redirect(url_for('login'))
            
            # Clean redirect without '?next=' if accessing root dashboard
            if request.path in ('/', url_for('dashboard')):
                return redirect(url_for('login'))
            return redirect(url_for('login', next=request.path))
        return view(**kwargs)
    return wrapped_view

# Helper: Decorator for Super Admin (lead_dba) requirement
def lead_dba_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not getattr(g, 'user', None) or 'user_id' not in session:
            was_deactivated = getattr(g, 'was_deactivated', False)
            session.clear()
            
            if request.path.startswith('/api/') or request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                msg = 'Your account has been deactivated by an administrator.' if was_deactivated else 'Authentication required. Please log in.'
                return jsonify({
                    'success': False,
                    'error': msg,
                    'redirect': url_for('login')
                }), 401
            
            if was_deactivated:
                flash('Your account has been deactivated by an administrator. Please contact your system DBA.', 'error')
                return redirect(url_for('login'))
                
            if request.path in ('/', url_for('dashboard')):
                return redirect(url_for('login'))
            return redirect(url_for('login', next=request.path))
            
        if g.user.get('role') != 'lead_dba':
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'success': False, 'error': 'Access Denied: Only Super Admin (Lead DBA) can perform this action.'}), 403
            flash('Access Denied: Only Super Admin (Lead DBA) can perform this action.', 'error')
            return redirect(url_for('dashboard'))
        return view(**kwargs)
    return wrapped_view

@app.before_request
def load_logged_in_user():
    g.was_deactivated = False
    try:
        user_id = session.get('user_id')
        if user_id is None:
            g.user = None
        else:
            db_user = UserModel.get_by_id(user_id)
            if not db_user:
                session.clear()
                g.user = None
            elif not db_user.get('is_active', 1):
                # Account has been deactivated by admin while logged in
                g.was_deactivated = True
                session.clear()
                g.user = None
            else:
                g.user = db_user
    except Exception as e:
        app.logger.error(f"Error loading logged in user: {e}")
        session.clear()
        g.user = None

def get_client_ip():
    try:
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr or '127.0.0.1'
    except Exception:
        return '127.0.0.1'

# ----------------- Authentication Routes -----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            user = UserModel.get_by_username(username)
            if user and UserModel.verify_password(user['password_hash'], password):
                if not user.get('is_active', 1):
                    error = 'Account is deactivated. Contact system administrator.'
                else:
                    session.clear()
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user['role']
                    try:
                        UserModel.update_last_login(user['id'])
                        AuditModel.log(
                            username=user['username'],
                            action='LOGIN',
                            target='Authentication System',
                            details='User logged in successfully',
                            ip_address=get_client_ip(),
                            status='SUCCESS',
                            user_id=user['id']
                        )
                    except Exception as log_err:
                        app.logger.warning(f"Failed to record login audit: {log_err}")

                    next_url = request.args.get('next')
                    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                        return redirect(next_url)
                    return redirect(url_for('dashboard'))
            else:
                error = 'Invalid username or password.'
                try:
                    AuditModel.log(
                        username=username or 'anonymous',
                        action='LOGIN_FAILED',
                        target='Authentication System',
                        details='Failed login attempt with invalid credentials',
                        ip_address=get_client_ip(),
                        status='FAILED'
                    )
                except Exception:
                    pass
        except Exception as e:
            app.logger.error(f"Login error: {e}")
            error = "An unexpected error occurred during authentication."

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    try:
        username = session.get('username', 'unknown')
        user_id = session.get('user_id')
        try:
            AuditModel.log(
                username=username,
                action='LOGOUT',
                target='Authentication System',
                details='User logged out',
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=user_id
            )
        except Exception as log_err:
            app.logger.warning(f"Failed to record logout audit: {log_err}")
        session.clear()
        flash('You have been logged out', 'info')
    except Exception as e:
        app.logger.error(f"Logout error: {e}")
        session.clear()
    return redirect(url_for('login'))

# ----------------- Dashboard & Query Execution -----------------

@app.route('/')
@login_required
def dashboard():
    try:
        accessible_dbs = PermissionModel.get_accessible_databases(g.user['id'], g.user['role'], enabled_only=False)
        all_cats = CategoryModel.list_all()
        
        # Filter categories to only those containing accessible DBs
        categories = []
        for c in all_cats:
            matching_count = sum(1 for d in accessible_dbs if d['category_id'] == c['id'] and d.get('is_enabled'))
            if matching_count > 0 or g.user['role'] == 'lead_dba':
                c_copy = dict(c)
                c_copy['db_count'] = matching_count
                categories.append(c_copy)
                
        history_user = None if g.user.get('role') == 'lead_dba' else g.user['username']
        recent_history = QueryHistoryModel.list_recent(limit=10, username=history_user)
        engines = sorted(list(set(d['engine'].upper() for d in accessible_dbs)))
        
        return render_template(
            'dashboard.html',
            categories=categories,
            databases=accessible_dbs,
            recent_history=recent_history,
            engines=engines
        )
    except Exception as e:
        app.logger.error(f"Dashboard load error: {e}")
        flash(f"Error loading dashboard: {str(e)}", 'error')
        return render_template(
            'dashboard.html',
            categories=[],
            databases=[],
            recent_history=[],
            engines=[]
        )

@app.route('/api/analyze-query', methods=['POST'])
@login_required
def analyze_query():
    try:
        data = request.get_json() or {}
        query_text = data.get('query', '')
        target_type = data.get('target_type', 'category')
        target_id = data.get('target_id')
        engine_filter = data.get('engine_filter')

        # Resolve targeted databases to check engines (scoped to user's permissions)
        databases = resolve_target_databases(g.user['id'], g.user['role'], target_type, target_id, engine_filter)
        target_engines = {d['engine'].lower() for d in databases}
        warnings = EngineDialectHelper.inspect_query(query_text, target_engines)

        # Permission advisory
        is_write = EngineDialectHelper.is_write_query(query_text)
        if is_write:
            read_only_targets = [d['name'] for d in databases if d.get('permission_level') == 'read_only']
            if read_only_targets:
                warnings.append(f"Permission Notice: You have Read-Only access on ({', '.join(read_only_targets)}). Write operations will be blocked on these targets.")

        return jsonify({
            "success": True,
            "target_count": len(databases),
            "target_engines": list(target_engines),
            "warnings": warnings
        })
    except Exception as e:
        app.logger.error(f"Analyze query error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def resolve_target_databases(user_id, user_role, target_type, target_id=None, engine_filter=None):
    try:
        accessible_dbs = PermissionModel.get_accessible_databases(user_id, user_role, enabled_only=True)
        targets = []

        if target_type == 'single':
            try:
                db_id = int(target_id)
                targets = [d for d in accessible_dbs if d['id'] == db_id]
            except (ValueError, TypeError):
                targets = []
        elif target_type == 'category':
            try:
                cat_id = int(target_id)
                targets = [d for d in accessible_dbs if d['category_id'] == cat_id]
            except (ValueError, TypeError):
                targets = []
        else:
            targets = []

        if engine_filter and engine_filter.lower() != 'all':
            targets = [d for d in targets if d['engine'].lower() == engine_filter.lower()]

        return targets
    except Exception as e:
        app.logger.error(f"Error resolving target databases: {e}")
        return []

@app.route('/api/execute-query', methods=['POST'])
@login_required
def execute_query():
    try:
        data = request.get_json() or {}
        query_text = (data.get('query') or '').strip()
        target_type = data.get('target_type', 'category')
        target_id = data.get('target_id')
        engine_filter = data.get('engine_filter')
        try:
            max_rows = int(data.get('max_rows', 200))
        except (ValueError, TypeError):
            max_rows = 200

        if not query_text:
            return jsonify({"success": False, "error": "Query cannot be empty"}), 400

        if target_type == 'all':
            return jsonify({
                "success": False,
                "error": "Executing across all registered databases simultaneously is disabled to prevent schema conflicts. Please select a Category Group or Individual Database."
            }), 400

        targets = resolve_target_databases(g.user['id'], g.user['role'], target_type, target_id, engine_filter)

        if not targets:
            return jsonify({
                "success": False, 
                "error": "No database matches the selected target criteria or you do not have permission for the selected targets."
            }), 400

        # Execute concurrently across targets (enforcing per-db permission level)
        execution_result = DatabaseManager.execute_across_databases(
            databases=targets,
            query_text=query_text,
            max_rows=max_rows
        )

        # Record Query History safely
        history_id = None
        try:
            history_id = QueryHistoryModel.record(
                username=g.user['username'],
                query_text=query_text,
                target_type=target_type,
                target_identifier=target_id or 'all',
                target_count=execution_result['total_targets'],
                success_count=execution_result['success_count'],
                failed_count=execution_result['failed_count'],
                total_duration_ms=execution_result['total_duration_ms'],
                user_id=g.user['id']
            )
        except Exception as hist_err:
            app.logger.warning(f"Failed to record query history: {hist_err}")

        # Log to Audit Log safely
        try:
            target_desc = f"{target_type.upper()}"
            if target_type == 'single' and targets:
                target_desc += f": {targets[0]['name']}"
            elif target_type == 'category' and targets:
                target_desc += f": {targets[0]['category_name']}"

            summary_status = 'SUCCESS' if execution_result['failed_count'] == 0 else ('PARTIAL' if execution_result['success_count'] > 0 else 'FAILED')

            AuditModel.log(
                username=g.user['username'],
                action='QUERY_EXECUTE',
                target=target_desc,
                details=json.dumps({
                    "query": query_text[:300] + ('...' if len(query_text) > 300 else ''),
                    "target_count": execution_result['total_targets'],
                    "success_count": execution_result['success_count'],
                    "failed_count": execution_result['failed_count'],
                    "duration_ms": execution_result['total_duration_ms']
                }),
                ip_address=get_client_ip(),
                status=summary_status,
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record query execution audit: {audit_err}")

        execution_result["success"] = True
        execution_result["history_id"] = history_id
        return jsonify(execution_result)
    except Exception as e:
        app.logger.error(f"Execute query unexpected error: {e}")
        return jsonify({"success": False, "error": f"Execution engine error: {str(e)}"}), 500

# ----------------- Database Registry & Category Routes -----------------

# ----------------- Database Registry & Category Routes -----------------

@app.route('/databases')
@login_required
def databases_view():
    try:
        if g.user.get('role') == 'lead_dba':
            categories = CategoryModel.list_all()
            databases = DatabaseModel.list_all(enabled_only=False)
        else:
            databases = PermissionModel.get_accessible_databases(g.user['id'], g.user['role'], enabled_only=False)
            accessible_cat_ids = {d['category_id'] for d in databases}
            all_cats = CategoryModel.list_all()
            categories = [c for c in all_cats if c['id'] in accessible_cat_ids]
        return render_template('databases.html', categories=categories, databases=databases)
    except Exception as e:
        app.logger.error(f"Error loading databases view: {e}")
        flash(f"Error loading database registry: {str(e)}", 'error')
        return render_template('databases.html', categories=[], databases=[])

@app.route('/api/database/create', methods=['POST'])
@lead_dba_required
def database_create():
    try:
        data = request.form or request.get_json() or {}
        name = data.get('name', '').strip()
        category_id = data.get('category_id')
        engine = (data.get('engine') or '').lower().strip()
        host = data.get('host', '').strip()
        port = data.get('port')
        database_name = data.get('database_name', '').strip()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        options = data.get('options', '').strip()

        if not name or not category_id or not engine or not database_name:
            flash('Database Name, Category, Engine, and Database Identifier are required.', 'error')
            return redirect(url_for('databases_view'))

        port_val = int(port) if port and str(port).isdigit() else None
        db_id = DatabaseModel.create(
            name=name,
            category_id=int(category_id),
            engine=engine,
            host=host,
            port=port_val,
            database_name=database_name,
            username=username,
            password=password,
            options=options,
            created_by=g.user['username']
        )

        try:
            AuditModel.log(
                username=g.user['username'],
                action='DB_CREATE',
                target=name,
                details=f"Super Admin registered database '{name}' ({engine.upper()}) under category #{category_id}",
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record DB_CREATE audit: {audit_err}")

        flash(f"Database '{name}' registered successfully.", 'success')
    except Exception as e:
        app.logger.error(f"Error registering database: {e}")
        flash(f"Error registering database: {str(e)}", 'error')

    return redirect(url_for('databases_view'))

@app.route('/api/database/<int:db_id>/update', methods=['POST'])
@lead_dba_required
def database_update(db_id):
    try:
        data = request.form or request.get_json() or {}
        name = data.get('name', '').strip()
        category_id = data.get('category_id')
        engine = (data.get('engine') or '').lower().strip()
        host = data.get('host', '').strip()
        port = data.get('port')
        database_name = data.get('database_name', '').strip()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        options = data.get('options', '').strip()
        is_enabled = 1 if data.get('is_enabled') in ['1', 'on', True] else 0

        port_val = int(port) if port and str(port).isdigit() else None
        DatabaseModel.update(
            db_id=db_id,
            name=name,
            category_id=int(category_id),
            engine=engine,
            host=host,
            port=port_val,
            database_name=database_name,
            username=username,
            password=password,
            options=options,
            is_enabled=is_enabled
        )

        try:
            AuditModel.log(
                username=g.user['username'],
                action='DB_UPDATE',
                target=name,
                details=f"Super Admin updated database ID #{db_id} ({name})",
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record DB_UPDATE audit: {audit_err}")

        flash(f"Database '{name}' updated successfully.", 'success')
    except Exception as e:
        app.logger.error(f"Error updating database: {e}")
        flash(f"Error updating database: {str(e)}", 'error')

    return redirect(url_for('databases_view'))

@app.route('/api/database/<int:db_id>/delete', methods=['POST'])
@lead_dba_required
def database_delete(db_id):
    is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
    try:
        db_item = DatabaseModel.get_by_id(db_id)
        if not db_item:
            if is_ajax:
                return jsonify({"success": False, "error": "Database not found."}), 404
            flash("Database not found.", 'error')
            return redirect(url_for('databases_view'))

        DatabaseModel.delete(db_id)
        try:
            AuditModel.log(
                username=g.user['username'],
                action='DB_DELETE',
                target=db_item['name'],
                details=f"Super Admin deleted database '{db_item['name']}' ({db_item['engine'].upper()})",
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record DB_DELETE audit: {audit_err}")

        if is_ajax:
            return jsonify({"success": True, "message": f"Database '{db_item['name']}' deleted successfully."})
        flash(f"Database '{db_item['name']}' deleted successfully.", 'success')
    except Exception as e:
        app.logger.error(f"Error deleting database #{db_id}: {e}")
        if is_ajax:
            return jsonify({"success": False, "error": str(e)}), 500
        flash(f"Error deleting database: {str(e)}", 'error')

    return redirect(url_for('databases_view'))

@app.route('/api/category/create', methods=['POST'])
@lead_dba_required
def category_create():
    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#4f46e5').strip()

        if not name:
            flash("Category name is required.", 'error')
            return redirect(url_for('databases_view'))

        CategoryModel.create(name=name, description=description, color=color)
        try:
            AuditModel.log(
                username=g.user['username'],
                action='CATEGORY_CREATE',
                target=name,
                details=f"Super Admin created category '{name}'",
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record CATEGORY_CREATE audit: {audit_err}")

        flash(f"Category '{name}' created successfully.", 'success')
    except Exception as e:
        app.logger.error(f"Error creating category: {e}")
        flash(f"Error creating category: {str(e)}", 'error')

    return redirect(url_for('databases_view'))

@app.route('/api/test-connection', methods=['POST'])
@login_required
def test_connection():
    try:
        data = request.get_json() or {}
        db_id = data.get('db_id')
        
        if db_id:
            db_info = DatabaseModel.get_by_id(db_id)
            if not db_info:
                return jsonify({"success": False, "message": "Database not found in registry"}), 404
        else:
            # Only lead_dba can test arbitrary custom host/credentials
            if g.user.get('role') != 'lead_dba':
                return jsonify({"success": False, "message": "Permission Denied: Only Super Admin can test ad-hoc connections"}), 403
            db_info = {
                "name": data.get('name', 'Ad-hoc Test'),
                "engine": data.get('engine', 'postgresql'),
                "host": data.get('host', 'localhost'),
                "port": data.get('port'),
                "database_name": data.get('database_name', ''),
                "username": data.get('username', ''),
                "password": data.get('password', ''),
                "options": data.get('options', '')
            }

        res = DatabaseManager.test_connection(db_info)

        try:
            AuditModel.log(
                username=g.user['username'],
                action='TEST_CONNECTION',
                target=db_info.get('name', 'Ad-hoc Test'),
                details=f"Test connection result: {res['message']} ({res['duration_ms']}ms)",
                ip_address=get_client_ip(),
                status='SUCCESS' if res['success'] else 'FAILED',
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record TEST_CONNECTION audit: {audit_err}")

        return jsonify(res)
    except Exception as e:
        app.logger.error(f"Error in test_connection: {e}")
        return jsonify({"success": False, "message": f"Connection test internal error: {str(e)}", "duration_ms": 0}), 500

# ----------------- Audit Logs & User Management -----------------

@app.route('/audit')
@login_required
def audit_view():
    try:
        action_filter = request.args.get('action')
        search_filter = request.args.get('search')
        is_super_admin = (g.user.get('role') == 'lead_dba')
        user_scope = None if is_super_admin else g.user['username']
        logs = AuditModel.list_recent(limit=150, action=action_filter, search=search_filter, username=user_scope)
        return render_template(
            'audit.html', 
            logs=logs, 
            action_filter=action_filter, 
            search_filter=search_filter,
            is_super_admin=is_super_admin
        )
    except Exception as e:
        app.logger.error(f"Error loading audit view: {e}")
        flash(f"Error loading audit logs: {str(e)}", 'error')
        return render_template(
            'audit.html', 
            logs=[], 
            action_filter=None, 
            search_filter=None,
            is_super_admin=(g.user.get('role') == 'lead_dba' if g.user else False)
        )

@app.route('/users')
@lead_dba_required
def users_view():
    try:
        users = UserModel.list_all()
        all_dbs = DatabaseModel.list_all(enabled_only=False)
        # Attach per-user database permission map safely
        for u in users:
            try:
                u['permissions'] = PermissionModel.get_user_permissions(u['id'])
            except Exception:
                u['permissions'] = {}
        return render_template('users.html', users=users, all_dbs=all_dbs)
    except Exception as e:
        app.logger.error(f"Error loading users view: {e}")
        flash(f"Error loading user administration: {str(e)}", 'error')
        return render_template('users.html', users=[], all_dbs=[])

def parse_permissions_from_form(form, role, all_dbs):
    try:
        perm_preset = form.get('perm_preset', 'custom')
        perms = {}
        
        if perm_preset == 'all_read_write':
            level = 'read_only' if role == 'auditor' else 'read_write'
            for db in all_dbs:
                perms[db['id']] = level
        elif perm_preset == 'all_read_only':
            for db in all_dbs:
                perms[db['id']] = 'read_only'
        else: # custom selection
            for db in all_dbs:
                perm_val = form.get(f"perm_db_{db['id']}")
                if perm_val in ['read_write', 'read_only']:
                    # Auditor cannot be read_write
                    perms[db['id']] = 'read_only' if role == 'auditor' else perm_val
        return perms
    except Exception as e:
        app.logger.error(f"Error parsing permissions from form: {e}")
        return {}

@app.route('/api/user/create', methods=['POST'])
@lead_dba_required
def user_create():
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'dba').strip()
        is_active = 1 if request.form.get('is_active') in ['1', 'on', True] else 0

        if not username or not password:
            flash("Username and password are required.", 'error')
            return redirect(url_for('users_view'))

        existing = UserModel.get_by_username(username)
        if existing:
            flash(f"Username '{username}' already exists.", 'error')
            return redirect(url_for('users_view'))

        new_id = UserModel.create(username=username, password=password, full_name=full_name, role=role, is_active=is_active)
        all_dbs = DatabaseModel.list_all(enabled_only=False)
        perms = parse_permissions_from_form(request.form, role, all_dbs)
        PermissionModel.set_user_permissions(new_id, perms, granted_by=g.user['username'])

        try:
            AuditModel.log(
                username=g.user['username'],
                action='USER_CREATE',
                target=username,
                details=f"Super Admin provisioned {role.upper()} user '{username}' (Active={bool(is_active)}, {len(perms)} DB permissions granted)",
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record USER_CREATE audit: {audit_err}")

        flash(f"User '{username}' created successfully with configured database permissions.", 'success')
    except Exception as e:
        app.logger.error(f"Error creating user: {e}")
        flash(f"Error creating user: {str(e)}", 'error')

    return redirect(url_for('users_view'))

@app.route('/api/user/<int:user_id>/update', methods=['POST'])
@lead_dba_required
def user_update(user_id):
    try:
        target_user = UserModel.get_by_id(user_id)
        if not target_user:
            flash("User not found.", 'error')
            return redirect(url_for('users_view'))

        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'dba').strip()
        is_active = 1 if request.form.get('is_active') in ['1', 'on', True] else 0
        new_password = request.form.get('password', '').strip()

        # Prevent deactivating or demoting the last super admin if it's the current user
        if target_user['username'] == 'admin' and (role != 'lead_dba' or is_active != 1):
            flash("Cannot demote or deactivate the root admin user.", 'error')
            return redirect(url_for('users_view'))

        UserModel.update(user_id, full_name=full_name, role=role, is_active=is_active, password=new_password or None)
        all_dbs = DatabaseModel.list_all(enabled_only=False)
        perms = parse_permissions_from_form(request.form, role, all_dbs)
        PermissionModel.set_user_permissions(user_id, perms, granted_by=g.user['username'])

        try:
            AuditModel.log(
                username=g.user['username'],
                action='USER_UPDATE',
                target=target_user['username'],
                details=f"Super Admin updated user '{target_user['username']}' (Role={role}, Active={bool(is_active)}, {len(perms)} DB permissions granted)",
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=g.user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record USER_UPDATE audit: {audit_err}")

        flash(f"User '{target_user['username']}' updated successfully.", 'success')
    except Exception as e:
        app.logger.error(f"Error updating user: {e}")
        flash(f"Error updating user: {str(e)}", 'error')

    return redirect(url_for('users_view'))

@app.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    is_json = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    try:
        if request.is_json:
            data = request.get_json() or {}
            current_password = data.get('current_password', '')
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')
        else:
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

        # Fetch fresh user record from database
        user = UserModel.get_by_id(g.user['id'])
        if not user:
            session.clear()
            if is_json:
                return jsonify({'success': False, 'error': 'Session expired. Please log in again.'}), 401
            flash('Session expired. Please log in again.', 'error')
            return redirect(url_for('login'))

        # Verify current password
        if not UserModel.verify_password(user['password_hash'], current_password):
            try:
                AuditModel.log(
                    username=user['username'],
                    action='PASSWORD_CHANGE_FAILED',
                    target=user['username'],
                    details='Failed password change: current password incorrect',
                    ip_address=get_client_ip(),
                    status='FAILED',
                    user_id=user['id']
                )
            except Exception:
                pass
            if is_json:
                return jsonify({'success': False, 'error': 'Current password is incorrect.'}), 400
            flash('Current password is incorrect.', 'error')
            return redirect(request.referrer or url_for('dashboard'))

        # Validate new password
        if not new_password or len(new_password) < 6:
            if is_json:
                return jsonify({'success': False, 'error': 'New password must be at least 6 characters long.'}), 400
            flash('New password must be at least 6 characters long.', 'error')
            return redirect(request.referrer or url_for('dashboard'))

        if new_password != confirm_password:
            if is_json:
                return jsonify({'success': False, 'error': 'New password and confirmation do not match.'}), 400
            flash('New password and confirmation do not match.', 'error')
            return redirect(request.referrer or url_for('dashboard'))

        if current_password == new_password:
            if is_json:
                return jsonify({'success': False, 'error': 'New password must be different from current password.'}), 400
            flash('New password must be different from current password.', 'error')
            return redirect(request.referrer or url_for('dashboard'))

        UserModel.change_password(user['id'], new_password)

        try:
            AuditModel.log(
                username=user['username'],
                action='PASSWORD_CHANGE',
                target=user['username'],
                details='User successfully updated account password',
                ip_address=get_client_ip(),
                status='SUCCESS',
                user_id=user['id']
            )
        except Exception as audit_err:
            app.logger.warning(f"Failed to record password change audit: {audit_err}")

        if is_json:
            return jsonify({'success': True, 'message': 'Password changed successfully.'})

        flash('Your password has been changed successfully.', 'success')
        return redirect(request.referrer or url_for('dashboard'))

    except Exception as e:
        app.logger.error(f"Error changing password: {e}")
        if is_json:
            return jsonify({'success': False, 'error': f"Failed to change password: {str(e)}"}), 500
        flash(f"Error changing password: {str(e)}", 'error')
        return redirect(request.referrer or url_for('dashboard'))

# Context processor for templates
@app.context_processor
def inject_global_data():
    try:
        return {
            'current_user': g.user if hasattr(g, 'user') else None
        }
    except Exception:
        return {'current_user': None}

if __name__ == '__main__':
    # Ensure tables exist
    init_app_database()
    host = os.environ.get('FLASK_HOST', '0.0.0.0' if os.environ.get('DOCKER_CONTAINER') else '127.0.0.1')
    port = int(os.environ.get('FLASK_PORT', 5001))
    app.run(host=host, port=port, debug=False)
