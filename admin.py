# admin.py - utilities for admin password and active class
import os, hashlib, binascii
from db import get_conn

def admin_exists():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='admin_hash'")
    r = cur.fetchone(); conn.close()
    return bool(r)

def set_admin_password_plain(password):
    salt = binascii.hexlify(os.urandom(16)).decode()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    conn = get_conn(); cur = conn.cursor()
    cur.execute("REPLACE INTO settings (key, value) VALUES (?,?)", ('admin_salt', salt))
    cur.execute("REPLACE INTO settings (key, value) VALUES (?,?)", ('admin_hash', hashed))
    conn.commit(); conn.close()

def check_admin_password_plain(password):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='admin_salt'")
    s = cur.fetchone()
    cur.execute("SELECT value FROM settings WHERE key='admin_hash'")
    h = cur.fetchone(); conn.close()
    if not s or not h: return False
    salt = s['value']; stored = h['value']
    candidate = hashlib.sha256((salt + password).encode()).hexdigest()
    return candidate == stored

def store_active_class(cid):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("REPLACE INTO settings (key, value) VALUES (?,?)", ('active_class', cid if cid else ''))
    conn.commit(); conn.close()

def load_active_class():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='active_class'")
    r = cur.fetchone(); conn.close()
    return r['value'] if r and r['value'] else None
