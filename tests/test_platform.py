import os
import unittest
import json
from app import app
from models import init_app_database, UserModel, CategoryModel, DatabaseModel, AuditModel
from init_db import setup_demo_environment

class TestQueryManagementPlatform(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = app.test_client()
        # Initialize test data
        setup_demo_environment()
        # Clean up transient test users for test isolation
        for test_user in ['trader_tina', 'inactive_user_ian', 'auditor_bob']:
            existing = UserModel.get_by_username(test_user)
            if existing:
                UserModel.delete(existing['id'])

    def login_as_admin(self):
        return self.client.post('/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)

    def test_01_authentication(self):
        # Failed login
        res_fail = self.client.post('/login', data={
            'username': 'admin',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'Invalid username or password', res_fail.data)

        # Successful login
        res_ok = self.login_as_admin()
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn(b'Query Execution Studio', res_ok.data)

    def test_02_database_registry_and_categories(self):
        self.login_as_admin()
        res = self.client.get('/databases')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Quotera DB', res.data)
        self.assertIn(b'Trade DB', res.data)
        self.assertIn(b'Backoffice DB', res.data)
        self.assertIn(b'Quotera NY (Primary)', res.data)

    def test_03_query_execution_category_quotera(self):
        self.login_as_admin()
        categories = {c['name']: c['id'] for c in CategoryModel.list_all()}
        quotera_id = categories['Quotera DB']

        # Query all Quotera DBs (should broadcast to NY, London, Tokyo, etc.)
        payload = {
            'query': 'SELECT symbol, bid_price, ask_price, volume, source FROM market_quotes;',
            'target_type': 'category',
            'target_id': quotera_id,
            'engine_filter': 'all'
        }
        res = self.client.post('/api/execute-query', 
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['total_targets'], 3)
        self.assertGreaterEqual(data['success_count'], 3)
        
        # Verify result contains records from databases
        sample_res = [r for r in data['results'] if r['status'] == 'SUCCESS'][0]
        self.assertIn('columns', sample_res)
        self.assertIn('symbol', sample_res['columns'])
        self.assertGreater(sample_res['row_count'], 0)

    def test_04_query_execution_single_db(self):
        self.login_as_admin()
        dbs = DatabaseModel.list_all()
        target_db = [d for d in dbs if d['name'] == 'Quotera NY (Primary)'][0]

        payload = {
            'query': 'SELECT count(*) as total FROM market_quotes;',
            'target_type': 'single',
            'target_id': target_db['id']
        }
        res = self.client.post('/api/execute-query', 
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['total_targets'], 1)
        self.assertEqual(data['success_count'], 1)
        self.assertGreater(data['results'][0]['rows'][0]['total'], 0)

    def test_05_query_failure_and_reason_reporting(self):
        self.login_as_admin()
        dbs = DatabaseModel.list_all()
        target_db = [d for d in dbs if d['name'] == 'Quotera NY (Primary)'][0]

        # Execute query on nonexistent table to test failure diagnosis
        payload = {
            'query': 'SELECT * FROM nonexistent_table_xyz;',
            'target_type': 'single',
            'target_id': target_db['id']
        }
        res = self.client.post('/api/execute-query', 
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['failed_count'], 1)
        res_item = data['results'][0]
        self.assertEqual(res_item['status'], 'FAILED')
        self.assertIsNotNone(res_item['error_message'])
        self.assertIn('no such table', res_item['error_message'].lower())

    def test_06_audit_logging(self):
        self.login_as_admin()
        
        # Create a new user
        self.client.post('/api/user/create', data={
            'username': 'auditor_bob',
            'password': 'password123',
            'full_name': 'Bob Auditor',
            'role': 'auditor'
        }, follow_redirects=True)

        # Check audit log contains USER_CREATE
        logs = AuditModel.list_recent(limit=10, action='USER_CREATE')
        self.assertTrue(any(l['target'] == 'auditor_bob' for l in logs))

        # Check audit log contains QUERY_EXECUTE
        query_logs = AuditModel.list_recent(limit=10, action='QUERY_EXECUTE')
        self.assertGreater(len(query_logs), 0)

    def test_07_engine_awareness_analyzer(self):
        self.login_as_admin()
        payload = {
            'query': 'SELECT * FROM orders WHERE name ILIKE `test` LIMIT 10;',
            'target_type': 'all'
        }
        res = self.client.post('/api/analyze-query',
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(len(data['warnings']) > 0)

    def test_08_role_permissions_enforcement(self):
        # 1. Super admin provisions a standard DBA
        self.login_as_admin()
        self.client.post('/api/user/create', data={
            'username': 'standard_dba_dan',
            'password': 'password123',
            'full_name': 'Dan Standard',
            'role': 'dba',
            'is_active': '1',
            'perm_preset': 'all_read_write'
        }, follow_redirects=True)

        # 2. Login as standard_dba_dan
        self.client.get('/logout')
        res_login = self.client.post('/login', data={
            'username': 'standard_dba_dan',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)

        # 3. Standard DBA attempts to access /users -> should be blocked and redirected
        res_users = self.client.get('/users', follow_redirects=True)
        self.assertIn(b'Access Denied: Only Super Admin (Lead DBA) can perform this action', res_users.data)

        # 4. Standard DBA attempts to register a database -> blocked
        res_db_create = self.client.post('/api/database/create', data={
            'name': 'Hacker DB',
            'category_id': 1,
            'engine': 'postgresql',
            'database_name': 'hack'
        }, follow_redirects=True)
        self.assertIn(b'Access Denied: Only Super Admin (Lead DBA) can perform this action', res_db_create.data)

    def test_09_inactive_user_cannot_login(self):
        self.login_as_admin()
        # Create an inactive user
        self.client.post('/api/user/create', data={
            'username': 'inactive_user_ian',
            'password': 'password123',
            'full_name': 'Ian Inactive',
            'role': 'dba',
            'is_active': '0', # Inactive
            'perm_preset': 'all_read_only'
        }, follow_redirects=True)

        self.client.get('/logout')
        # Attempt login
        res = self.client.post('/login', data={
            'username': 'inactive_user_ian',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Account is deactivated. Contact system administrator.', res.data)

    def test_10_granular_db_permissions_read_only_restriction(self):
        self.login_as_admin()
        dbs = DatabaseModel.list_all()
        ny_db = [d for d in dbs if d['name'] == 'Quotera NY (Primary)'][0]
        trade_db = [d for d in dbs if d['name'] == 'Trade Execution (Primary)'][0]

        # Provision DBA 'trader_tina' with read_only access to trade_db ONLY
        res_create = self.client.post('/api/user/create', data={
            'username': 'trader_tina',
            'password': 'password123',
            'full_name': 'Tina Trader',
            'role': 'dba',
            'is_active': '1',
            'perm_preset': 'custom',
            f'perm_db_{trade_db["id"]}': 'read_only' # Only trade_db, read_only
        }, follow_redirects=True)

        self.client.get('/logout')
        self.client.post('/login', data={'username': 'trader_tina', 'password': 'password123'}, follow_redirects=True)

        # 1. Tina queries Quotera NY (not permitted) -> should return error
        res_unpermitted = self.client.post('/api/execute-query', data=json.dumps({
            'query': 'SELECT * FROM market_quotes;',
            'target_type': 'single',
            'target_id': ny_db['id']
        }), content_type='application/json')
        self.assertEqual(res_unpermitted.status_code, 400)
        self.assertIn(b'No database matches', res_unpermitted.data)

        # 2. Tina runs SELECT query on permitted Trade DB -> SUCCESS
        res_select = self.client.post('/api/execute-query', data=json.dumps({
            'query': 'SELECT * FROM orders;',
            'target_type': 'single',
            'target_id': trade_db['id']
        }), content_type='application/json')
        self.assertEqual(res_select.status_code, 200)
        data_select = res_select.get_json()
        self.assertEqual(data_select['success_count'], 1)

        # 3. Tina runs write query on permitted Trade DB -> BLOCKED by read_only restriction
        res_write = self.client.post('/api/execute-query', data=json.dumps({
            'query': "UPDATE orders SET status = 'CANCELLED' WHERE order_id = 'ORD-8801';",
            'target_type': 'single',
            'target_id': trade_db['id']
        }), content_type='application/json')
        self.assertEqual(res_write.status_code, 200)
        data_write = res_write.get_json()
        self.assertEqual(data_write['failed_count'], 1)
        self.assertIn('Permission Denied', data_write['results'][0]['error_message'])

    def test_11_audit_log_and_query_history_scoping(self):
        # 1. Super admin provisions a standard DBA 'auditee_alice' with access to Trade DB
        self.login_as_admin()
        dbs = DatabaseModel.list_all()
        trade_db = [d for d in dbs if d['name'] == 'Trade Execution (Primary)'][0]

        self.client.post('/api/user/create', data={
            'username': 'auditee_alice',
            'password': 'password123',
            'full_name': 'Alice Auditee',
            'role': 'dba',
            'is_active': '1',
            'perm_preset': 'custom',
            f'perm_db_{trade_db["id"]}': 'read_write'
        }, follow_redirects=True)

        # 2. Alice logs in and executes a query
        self.client.get('/logout')
        self.client.post('/login', data={'username': 'auditee_alice', 'password': 'password123'}, follow_redirects=True)
        self.client.post('/api/execute-query', data=json.dumps({
            'query': 'SELECT count(*) FROM orders;',
            'target_type': 'single',
            'target_id': trade_db['id']
        }), content_type='application/json')

        # 3. Alice visits /audit -> should ONLY see her own activity
        res_alice_audit = self.client.get('/audit')
        self.assertEqual(res_alice_audit.status_code, 200)
        self.assertIn(b'PERSONAL LOGS: auditee_alice', res_alice_audit.data)
        # Alice should NOT see admin's activity
        self.assertNotIn(b'admin provisioned', res_alice_audit.data)
        self.assertNotIn(b'Initial Super Admin', res_alice_audit.data)

        # 4. Super admin visits /audit -> should see ALL activity (including Alice's and admin's)
        self.client.get('/logout')
        self.login_as_admin()
        res_admin_audit = self.client.get('/audit')
        self.assertEqual(res_admin_audit.status_code, 200)
        self.assertIn(b'SUPER ADMIN SCOPE', res_admin_audit.data)
        self.assertIn(b'auditee_alice', res_admin_audit.data)

if __name__ == '__main__':
    unittest.main()
