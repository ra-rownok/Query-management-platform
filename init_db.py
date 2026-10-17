from models import init_app_database, UserModel, AuditModel

def setup_admin_account():
    """Initializes PostgreSQL application tables and provisions the default administrator account."""
    # 1. Initialize PostgreSQL tables
    init_app_database()

    # 2. Seed default admin user (lead_dba)
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
        print("Created default admin user (username: admin, role: lead_dba)")
    else:
        UserModel.update(admin['id'], full_name=admin['full_name'], role='lead_dba', is_active=1)
        print("Default admin user already exists (ensured lead_dba role).")

if __name__ == '__main__':
    setup_admin_account()
    print("Application database initialized successfully.")