"""
Authentication Routes
Extracted from server.py monolith.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from database import get_db
from auth import (verify_token, require_auth, check_role, hash_password, verify_password,
                  create_token, log_activity, serialize_doc, generate_password)
from routes.shared import new_id, now, parse_date, to_end_of_day, PO_STATUSES, get_user_portals
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["auth"])

# ─── AUTH ────────────────────────────────────────────────────────────────────
@router.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    db = get_db()
    email = body.get('email', '')
    password = body.get('password', '')
    u = await db.users.find_one({'email': email})
    if not u or not verify_password(password, u['password']):
        raise HTTPException(401, 'Email atau password salah')
    if u.get('status') != 'active':
        raise HTTPException(403, 'Akun tidak aktif')
    
    # Get user permissions for immediate use (without /auth/me call)
    user_perms = []
    role = u.get('role', '')
    if role == 'superadmin':
        user_perms = ['*']
    elif role == 'vendor':
        user_perms = ['dashboard.view', 'shipment.view', 'jobs.view', 'jobs.create', 'progress.view', 'progress.create']
    elif role == 'buyer':
        user_perms = ['dashboard.view', 'po.view', 'shipment.view']
    else:
        # Check custom role
        if u.get('role_id'):
            role_perms = await db.role_permissions.find({'role_id': u['role_id']}, {'_id': 0}).to_list(None)
            user_perms = [rp.get('permission_key') for rp in role_perms]
        else:
            custom_role = await db.roles.find_one({'name': role})
            if custom_role:
                role_perms = await db.role_permissions.find({'role_id': custom_role['id']}, {'_id': 0}).to_list(None)
                user_perms = [rp.get('permission_key') for rp in role_perms]
    
    token = create_token(u)
    await log_activity(u['id'], u['name'], 'Login', 'Auth', f"User {u['email']} logged in")
    return {'token': token, 'user': {'id': u['id'], 'name': u['name'], 'email': u['email'], 'role': u['role'],
            'vendor_id': u.get('vendor_id'), 'buyer_id': u.get('buyer_id'),
            'customer_name': u.get('customer_name', u.get('buyer_company', '')),
            'permissions': user_perms}}

@router.get("/auth/me")
async def auth_me(request: Request):
    user = await require_auth(request)
    db = get_db()
    u = await db.users.find_one({'id': user['id']}, {'password': 0, '_id': 0})
    # Include user permissions for RBAC
    user_perms = []
    role = u.get('role', '') if u else ''
    
    if role == 'superadmin':
        user_perms = ['*']  # Full access
    elif role == 'vendor':
        user_perms = ['dashboard.view', 'shipment.view', 'jobs.view', 'jobs.create', 'progress.view', 'progress.create']
    elif role == 'buyer':
        user_perms = ['dashboard.view', 'po.view', 'shipment.view']
    else:
        # Check if this is a custom role
        if u.get('role_id'):
            # User has custom role assigned via role_id
            role_perms = await db.role_permissions.find({'role_id': u['role_id']}, {'_id': 0}).to_list(None)
            user_perms = [rp.get('permission_key') for rp in role_perms]
        else:
            # Try to find role by name (legacy)
            custom_role = await db.roles.find_one({'name': role})
            if custom_role:
                role_perms = await db.role_permissions.find({'role_id': custom_role['id']}, {'_id': 0}).to_list(None)
                user_perms = [rp.get('permission_key') for rp in role_perms]
    
    result = serialize_doc(u) if u else {}
    result['permissions'] = user_perms
    result['portals'] = get_user_portals({"role": role})
    return result

