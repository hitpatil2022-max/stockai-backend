"""
auth.py — Email OTP Authentication + JWT Session Management
============================================================
Flow:
  1. User visits any protected route → no valid JWT → redirect /login
  2. /login → user enters any email → POST /auth/send-otp
  3. Server generates 6-digit OTP → sends via Gmail SMTP
  4. User enters OTP → POST /auth/verify-otp
  5. Server checks OTP (10 min expiry, max 5 attempts)
  6. Success → JWT cookie (24h without remember, 30d with remember) → redirect /

Open to anyone with a valid email — no whitelist.

Env vars (Railway dashboard):
  SMTP_EMAIL      — Gmail address to send OTPs from
  SMTP_PASSWORD   — Gmail App Password (not your regular password)
                    Google Account → Security → 2-Step Verification → App Passwords
  JWT_SECRET      — random string: python3 -c "import secrets; print(secrets.token_hex(32))"
  APP_NAME        — display name in emails (default: India Stock AI)
"""

import os, jwt, time, random, string, smtplib, ssl, functools, threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, redirect, make_response, jsonify

# ── Config ──────────────────────────────────────────────────────────────
SMTP_EMAIL      = os.environ.get('SMTP_EMAIL',     '')
SMTP_PASSWORD   = os.environ.get('SMTP_PASSWORD',  '')
SMTP_HOST       = 'smtp.gmail.com'
SMTP_PORT       = 587
JWT_SECRET      = os.environ.get('JWT_SECRET', 'change-me-set-in-railway')
APP_NAME        = os.environ.get('APP_NAME',   'India Stock AI')

COOKIE_NAME      = 'india_ai_session'
OTP_EXPIRY_SECS  = 600       # 10 minutes
OTP_MAX_ATTEMPTS = 5
JWT_SHORT        = 86400     # 24h  — no remember
JWT_LONG         = 2592000   # 30d  — remember me

# ── OTP store ────────────────────────────────────────────────────────────
_otp_store = {}
_lock      = threading.Lock()

def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def _store_otp(email, otp):
    with _lock:
        _otp_store[email] = {
            'otp': otp,
            'expires_at': time.time() + OTP_EXPIRY_SECS,
            'attempts': 0,
            'sent_at': time.time(),
        }

def _verify_otp(email, otp_input):
    """Returns (ok: bool, error: str)"""
    email = email.lower()
    with _lock:
        e = _otp_store.get(email)
        if not e:
            return False, 'No OTP found for this email. Request a new one.'
        if time.time() > e['expires_at']:
            del _otp_store[email]
            return False, 'OTP has expired (10 min limit). Please request a new one.'
        if e['attempts'] >= OTP_MAX_ATTEMPTS:
            del _otp_store[email]
            return False, 'Too many wrong attempts. Please request a new OTP.'
        e['attempts'] += 1
        if otp_input.strip() != e['otp']:
            left = OTP_MAX_ATTEMPTS - e['attempts']
            return False, f'Incorrect OTP. {left} attempt{"s" if left != 1 else ""} left.'
        del _otp_store[email]
        return True, ''

def _can_resend(email):
    """Returns (ok: bool, wait_seconds: int)"""
    with _lock:
        e = _otp_store.get(email.lower())
        if not e:
            return True, 0
        wait = 60 - int(time.time() - e['sent_at'])
        return (True, 0) if wait <= 0 else (False, wait)

# ── Email sending ─────────────────────────────────────────────────────────
def _send_otp_email(to_email, otp):
    """Returns (ok: bool, error: str)"""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print('[AUTH] SMTP not configured')
        return False, 'Email service not configured. Contact admin.'

    subject = f'{otp} is your {APP_NAME} verification code'

    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#060a12;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#060a12;padding:40px 20px">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" style="background:#0d1525;border:1px solid rgba(255,255,255,0.1);border-radius:16px;overflow:hidden;max-width:480px;width:100%">
  <tr><td style="background:linear-gradient(135deg,#0d1525,#1a2744);padding:32px 36px 28px;text-align:center;border-bottom:1px solid rgba(0,212,170,0.2)">
    <div style="font-size:36px;margin-bottom:10px">📈</div>
    <div style="font-size:22px;font-weight:800;color:#fff;letter-spacing:2px">{APP_NAME}</div>
    <div style="font-size:11px;color:#64748b;margin-top:4px;letter-spacing:1px">NSE · BSE · INTELLIGENCE TERMINAL</div>
  </td></tr>
  <tr><td style="padding:36px 36px 28px">
    <p style="color:#94a3b8;font-size:15px;margin:0 0 24px;line-height:1.6">
      Your verification code for <strong style="color:#e2e8f0">{APP_NAME}</strong>:
    </p>
    <div style="background:#060a12;border:2px solid #00d4aa;border-radius:12px;padding:28px;text-align:center;margin-bottom:28px">
      <div style="font-size:52px;font-weight:900;letter-spacing:14px;color:#00d4aa;font-family:'Courier New',monospace;text-shadow:0 0 24px rgba(0,212,170,0.5)">{otp}</div>
      <div style="font-size:12px;color:#475569;margin-top:12px;font-family:'Courier New',monospace">Valid for 10 minutes · One-time use</div>
    </div>
    <p style="color:#475569;font-size:13px;margin:0;line-height:1.7">
      If you didn't request this, ignore this email. The code expires automatically.
    </p>
  </td></tr>
  <tr><td style="padding:20px 36px 28px;border-top:1px solid rgba(255,255,255,0.06);text-align:center">
    <p style="color:#334155;font-size:11px;margin:0;line-height:1.8">
      Sent to <strong style="color:#475569">{to_email}</strong><br>
      Do not share this code · {APP_NAME} Private Access
    </p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

    text = f"{APP_NAME} Verification Code\n\nYour OTP: {otp}\n\nValid for 10 minutes. Do not share.\n"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'{APP_NAME} <{SMTP_EMAIL}>'
        msg['To']      = to_email
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        print(f'[AUTH] OTP sent to {to_email}')
        return True, ''

    except smtplib.SMTPAuthenticationError:
        print('[AUTH] Gmail auth failed — check SMTP_PASSWORD is an App Password')
        return False, 'Email service auth error. Contact admin.'
    except Exception as e:
        print(f'[AUTH] Email error: {e}')
        return False, 'Could not deliver email. Please try again.'

# ── JWT helpers ───────────────────────────────────────────────────────────
def _make_jwt(email, remember):
    exp = JWT_LONG if remember else JWT_SHORT
    return jwt.encode(
        {'email': email, 'remember': remember, 'iat': int(time.time()), 'exp': int(time.time()) + exp},
        JWT_SECRET, algorithm='HS256'
    )

def _verify_jwt(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    except Exception:
        return None

def get_current_user():
    token = request.cookies.get(COOKIE_NAME)
    return _verify_jwt(token) if token else None

def require_auth(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapped

# ── Route registration ────────────────────────────────────────────────────
def register_auth_routes(app: Flask, get_login_html, get_dashboard_html):

    @app.route('/login')
    def login_page():
        if get_current_user():
            return redirect('/')
        return get_login_html(), 200

    @app.route('/auth/send-otp', methods=['POST'])
    def send_otp_route():
        data  = request.get_json(silent=True) or {}
        email = (data.get('email') or '').strip().lower()

        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            return jsonify({'ok': False, 'error': 'Enter a valid email address.'}), 400

        can, wait = _can_resend(email)
        if not can:
            return jsonify({'ok': False, 'error': f'Wait {wait}s before requesting another OTP.', 'wait': wait}), 429

        otp = _generate_otp()
        _store_otp(email, otp)

        # Send synchronously — returns real error to user if SMTP fails
        ok, err = _send_otp_email(email, otp)
        if not ok:
            with _lock:
                _otp_store.pop(email, None)
            return jsonify({'ok': False, 'error': f'Could not send OTP email: {err}'}), 500

        return jsonify({'ok': True}), 200

    @app.route('/auth/verify-otp', methods=['POST'])
    def verify_otp_route():
        data     = request.get_json(silent=True) or {}
        email    = (data.get('email')    or '').strip().lower()
        otp_in   = (data.get('otp')      or '').strip()
        remember = bool(data.get('remember', False))

        if not email or not otp_in:
            return jsonify({'ok': False, 'error': 'Email and OTP required.'}), 400

        ok, err = _verify_otp(email, otp_in)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 401

        token  = _make_jwt(email, remember)
        expiry = JWT_LONG if remember else None  # None = session cookie

        print(f'[AUTH] Login: {email} remember={remember}')
        resp = make_response(jsonify({'ok': True}))
        resp.set_cookie(COOKIE_NAME, token, httponly=True, secure=True,
                        samesite='Lax', max_age=expiry, path='/')
        return resp

    @app.route('/')
    def dashboard():
        if not get_current_user():
            return redirect('/login')
        html = get_dashboard_html()
        if html is None:
            return 'Starting up...', 503
        # Inject Gemini key from Railway env var — never stored in GitHub
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        html = html.replace(
            "const GEMINI_API_KEY = '';",
            f"const GEMINI_API_KEY = '{gemini_key}';"
        )
        return html, 200

    @app.route('/logout')
    def logout():
        resp = make_response(redirect('/login'))
        resp.delete_cookie(COOKIE_NAME, path='/')
        return resp
