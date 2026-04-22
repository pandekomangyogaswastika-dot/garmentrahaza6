import jwt
import bcrypt
import uuid
import os
import string
import random
from datetime import datetime, timezone, timedelta
from fastapi import Request, HTTPException
from database import get_db

JWT_SECRET = os.environ.get('JWT_SECRET', 'garment_erp_jwt_secret_2025')

def generate_password(length=10):
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789@#!'
    return ''.join(random.choice(chars) for _ in range(length))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(10)).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_data: dict) -> str:
    payload = {
        'id': user_data['id'],
        'email': user_data['email'],
        'role': user_data['role'],
        'name': user_data['name'],
        'vendor_id': user_data.get('vendor_id'),
        'buyer_id': user_data.get('buyer_id'),
        'customer_name': user_data.get('customer_name', user_data.get('buyer_company', '')),
        'exp': datetime.now(timezone.utc) + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(request: Request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    try:
        token = auth_header.split(' ')[1]
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except Exception:
        return None

async def require_auth(request: Request):
    user = verify_token(request)
    if not user:
        raise HTTPException(status_code=401, detail='Unauthorized')
    # Pre-load permissions for custom roles
    role = user.get('role', '')
    if role == 'superadmin' or role == 'admin':
        user['_permissions'] = ['*']
    elif role == 'vendor':
        user['_permissions'] = ['dashboard.view', 'shipment.view', 'jobs.view', 'jobs.create', 'progress.view', 'progress.create']
    elif role == 'buyer':
        user['_permissions'] = ['dashboard.view', 'po.view', 'shipment.view']
    else:
        # Custom role: load from DB
        db = get_db()
        custom_role = await db.roles.find_one({'name': role})
        if custom_role:
            role_perms = await db.role_permissions.find({'role_id': custom_role['id']}, {'_id': 0}).to_list(None)
            user['_permissions'] = [rp.get('permission_key') for rp in role_perms]
        else:
            user['_permissions'] = []
    return user

def check_role(user: dict, allowed_roles: list, perm_key: str = None) -> bool:
    if user.get('role') == 'superadmin':
        return True
    if user.get('role') in allowed_roles:
        return True
    # Check custom role permissions loaded by require_auth
    perms = user.get('_permissions', [])
    if '*' in perms:
        return True
    if perm_key and perm_key in perms:
        return True
    # If no specific perm_key provided, check if user has any admin-level permissions
    if not perm_key and perms:
        return True
    return False

async def log_activity(user_id, user_name, action, module, details=''):
    db = get_db()
    await db.activity_logs.insert_one({
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'user_name': user_name,
        'action': action,
        'module': module,
        'details': details,
        'timestamp': datetime.now(timezone.utc)
    })

async def seed_initial_data():
    db = get_db()

    # Ensure superadmin
    admin = await db.users.find_one({'email': 'admin@garment.com'})
    if not admin:
        hashed = hash_password('Admin@123')
        await db.users.insert_one({
            'id': str(uuid.uuid4()),
            'name': 'Super Admin',
            'email': 'admin@garment.com',
            'password': hashed,
            'role': 'superadmin',
            'status': 'active',
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        })
        print('Superadmin seeded: admin@garment.com / Admin@123')

    # Seed default custom roles for PT Rahaza RBAC (Fase 1 kerangka)
    await _seed_default_roles(db)

    # Seed company profile placeholder (PT Rahaza)
    existing_co = await db.company_settings.find_one({})
    if not existing_co:
        await db.company_settings.insert_one({
            'id': str(uuid.uuid4()),
            'company_name': 'PT Rahaza Global Indonesia',
            'industry': 'Knit Manufacturing (Sweater)',
            'address': '',
            'phone': '',
            'email': '',
            'website': '',
            'tax_number': '',
            'currency': 'IDR',
            'locale': 'id-ID',
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc)
        })
        print('Company profile seeded: PT Rahaza Global Indonesia')


# ── Default role seed (baseline; fully editable via Role Management) ─────────
_DEFAULT_ROLES = [
    {
        'name': 'admin',
        'description': 'Administrator sistem — akses penuh semua portal.',
        'permissions': ['*'],
    },
    {
        'name': 'owner',
        'description': 'Pemilik — akses lihat menyeluruh + approval terbatas.',
        'permissions': [
            'dashboard.view', 'report.view', 'report.export',
            'products.view', 'customers.view',
            'prod.dashboard.view', 'prod.line.view', 'prod.wip.view',
            'wh.receiving.view', 'wh.opname.manage',
            'fin.ar.view', 'fin.ap.view', 'fin.invoice.view', 'fin.payment.view', 'fin.recap.view',
            'fin.approval.manage',
            'hr.dashboard.view', 'hr.payroll.view',
            'hpp.view',
            'activity.view', 'users.view',
        ],
    },
    {
        'name': 'supervisor',
        'description': 'Supervisor produksi & gudang — input transaksi harian.',
        'permissions': [
            'dashboard.view',
            'prod.dashboard.view', 'prod.line.view', 'prod.line.manage',
            'prod.process.input', 'prod.wip.view',
            'wh.receiving.view', 'wh.receiving.manage',
            'wh.putaway.manage', 'wh.opname.manage', 'wh.bin.manage', 'wh.accessory.manage',
            'products.view', 'customers.view',
        ],
    },
    {
        'name': 'operator',
        'description': 'Operator mesin/proses — akses khusus Operator View.',
        'permissions': [
            'operator.view', 'operator.input',
        ],
    },
    {
        'name': 'hr',
        'description': 'Tim HR — karyawan, absensi, payroll.',
        'permissions': [
            'dashboard.view',
            'hr.dashboard.view',
            'hr.employee.view', 'hr.employee.manage',
            'hr.attendance.manage',
            'hr.payroll.view', 'hr.payroll.run',
            'report.view',
        ],
    },
    {
        'name': 'accounting',
        'description': 'Tim Accounting — finance penuh + HPP.',
        'permissions': [
            'dashboard.view',
            'fin.ar.view', 'fin.ar.manage',
            'fin.ap.view', 'fin.ap.manage',
            'fin.invoice.view', 'fin.invoice.manage',
            'fin.payment.view', 'fin.payment.manage',
            'fin.recap.view', 'fin.approval.manage',
            'hpp.view', 'hpp.manage',
            'report.view', 'report.export',
        ],
    },
]


async def _seed_default_roles(db):
    """Seed baseline roles if not exists. Editable via RoleManagement."""
    for role_def in _DEFAULT_ROLES:
        existing = await db.roles.find_one({'name': role_def['name']})
        if existing:
            continue
        rid = str(uuid.uuid4())
        await db.roles.insert_one({
            'id': rid,
            'name': role_def['name'],
            'description': role_def['description'],
            'is_system': True,
            'created_at': datetime.now(timezone.utc),
            'updated_at': datetime.now(timezone.utc),
        })
        for perm_key in role_def['permissions']:
            await db.role_permissions.insert_one({
                'id': str(uuid.uuid4()),
                'role_id': rid,
                'permission_key': perm_key,
                'created_at': datetime.now(timezone.utc),
            })
        print(f"  · Role seeded: {role_def['name']} ({len(role_def['permissions'])} permissions)")

def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(d) for d in doc]
    if isinstance(doc, dict):
        result = {}
        for k, v in doc.items():
            if k == '_id':
                continue
            result[k] = serialize_doc(v)
        return result
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc
