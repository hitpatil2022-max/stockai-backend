"""
auth.py — Email OTP Authentication + JWT Session Management
============================================================
WHY BREVO INSTEAD OF GMAIL SMTP:
  Railway free tier blocks outbound port 587 (SMTP). Brevo uses HTTPS port 443
  which is always open. Free = 300 emails/day, no credit card needed.

Railway Variables needed:
  BREVO_API_KEY  — from app.brevo.com → SMTP & API → API Keys → Generate
  SMTP_EMAIL     — sender address verified in Brevo (indiastockhit@gmail.com)
  JWT_SECRET     — python3 -c "import secrets; print(secrets.token_hex(32))"
  APP_NAME       — optional (default: India Stock AI)
  GEMINI_API_KEY — already set (injected into dashboard at login time)
"""

import os, jwt, time, random, string, functools, threading
import urllib.request, urllib.error, json as _json
from flask import Flask, request, redirect, make_response, jsonify

# ── Config ───────────────────────────────────────────────────────────────────
BREVO_API_KEY  = os.environ.get('BREVO_API_KEY', '')
SMTP_EMAIL     = os.environ.get('SMTP_EMAIL',    '')
JWT_SECRET     = os.environ.get('JWT_SECRET',    'change-me-set-in-railway')
APP_NAME       = os.environ.get('APP_NAME',      'India Stock AI')

COOKIE_NAME      = 'india_ai_session'
OTP_EXPIRY_SECS  = 600
OTP_MAX_ATTEMPTS = 5
JWT_SHORT        = 86400
JWT_LONG         = 2592000

# ── OTP store ─────────────────────────────────────────────────────────────────
_otp_store = {}
_lock      = threading.Lock()

def _generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def _store_otp(email, otp):
    with _lock:
        _otp_store[email.lower()] = {
            'otp': otp, 'expires_at': time.time() + OTP_EXPIRY_SECS,
            'attempts': 0, 'sent_at': time.time(),
        }

def _verify_otp(email, otp_input):
    email = email.lower()
    with _lock:
        e = _otp_store.get(email)
        if not e:
            return False, 'No OTP found. Please request a new one.'
        if time.time() > e['expires_at']:
            del _otp_store[email]
            return False, 'OTP expired (10 min limit). Please request a new one.'
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
    with _lock:
        e = _otp_store.get(email.lower())
        if not e:
            return True, 0
        wait = 60 - int(time.time() - e['sent_at'])
        return (True, 0) if wait <= 0 else (False, wait)

# ── Email via Brevo HTTP API ──────────────────────────────────────────────────
def _send_otp_email(to_email, otp):
    """Send OTP via Brevo API (HTTPS 443 — not blocked by Railway free tier)."""
    if not BREVO_API_KEY:
        print('[AUTH] BREVO_API_KEY not set in Railway Variables')
        return False, 'Email service not configured. Add BREVO_API_KEY in Railway Variables.'
    if not SMTP_EMAIL:
        print('[AUTH] SMTP_EMAIL not set in Railway Variables')
        return False, 'Sender email not configured. Add SMTP_EMAIL in Railway Variables.'

    html_body = (
        '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#060a12;font-family:Arial,sans-serif">'
        '<table width="100%" cellpadding="0" cellspacing="0" style="background:#060a12;padding:40px 20px">'
        '<tr><td align="center">'
        '<table width="480" cellpadding="0" cellspacing="0" style="background:#0d1525;border:1px solid rgba(255,255,255,0.1);border-radius:16px;overflow:hidden;max-width:480px;width:100%">'
        '<tr><td style="background:linear-gradient(135deg,#0d1525,#1a2744);padding:32px 36px 28px;text-align:center;border-bottom:1px solid rgba(0,212,170,0.2)">'
        '<div style="font-size:36px;margin-bottom:10px">📈</div>'
        f'<div style="font-size:22px;font-weight:800;color:#fff;letter-spacing:2px">{APP_NAME}</div>'
        '<div style="font-size:11px;color:#64748b;margin-top:4px;letter-spacing:1px">NSE &middot; BSE &middot; INTELLIGENCE TERMINAL</div>'
        '</td></tr>'
        '<tr><td style="padding:36px 36px 28px">'
        '<p style="color:#94a3b8;font-size:15px;margin:0 0 24px;line-height:1.6">Your verification code:</p>'
        '<div style="background:#060a12;border:2px solid #00d4aa;border-radius:12px;padding:28px;text-align:center;margin-bottom:28px">'
        f'<div style="font-size:52px;font-weight:900;letter-spacing:14px;color:#00d4aa;font-family:\'Courier New\',monospace;text-shadow:0 0 24px rgba(0,212,170,0.5)">{otp}</div>'
        '<div style="font-size:12px;color:#475569;margin-top:12px;font-family:\'Courier New\',monospace">Valid for 10 minutes &middot; One-time use</div>'
        '</div>'
        '<p style="color:#475569;font-size:13px;margin:0;line-height:1.7">If you did not request this, ignore this email.</p>'
        '</td></tr>'
        '<tr><td style="padding:20px 36px 28px;border-top:1px solid rgba(255,255,255,0.06);text-align:center">'
        f'<p style="color:#334155;font-size:11px;margin:0;line-height:1.8">Sent to <strong style="color:#475569">{to_email}</strong><br>Do not share this code &middot; {APP_NAME}</p>'
        '</td></tr>'
        '</table></td></tr></table></body></html>'
    )

    payload = _json.dumps({
        "sender":      {"name": f"noreply {APP_NAME}", "email": SMTP_EMAIL},
        "to":          [{"email": to_email}],
        "subject":     f"{otp} is your {APP_NAME} verification code",
        "htmlContent": html_body,
        "textContent": f"{APP_NAME} OTP: {otp}\nValid 10 minutes. Do not share.",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data    = payload,
            headers = {
                "api-key":      BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept":       "application/json",
            },
            method = "POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[AUTH] OTP sent to {to_email} via Brevo (HTTP {resp.status})")
            return True, ''

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='ignore')
        print(f"[AUTH] Brevo HTTP {e.code}: {body[:200]}")
        if e.code == 401:
            return False, "Invalid BREVO_API_KEY — check Railway Variables."
        if e.code == 400:
            return False, (
                f"Brevo rejected the request — make sure '{SMTP_EMAIL}' "
                "is verified as a sender in your Brevo dashboard."
            )
        return False, f"Email API error (HTTP {e.code}). Please try again."
    except Exception as e:
        print(f"[AUTH] Brevo error: {e}")
        return False, f"Could not send email. Please try again."

# ── JWT helpers ───────────────────────────────────────────────────────────────
def _make_jwt(email, remember):
    exp = JWT_LONG if remember else JWT_SHORT
    return jwt.encode(
        {'email': email, 'remember': remember,
         'iat': int(time.time()), 'exp': int(time.time()) + exp},
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

# ── Routes ────────────────────────────────────────────────────────────────────
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
            return jsonify({'ok': False,
                            'error': f'Please wait {wait}s before requesting another OTP.',
                            'wait': wait}), 429

        otp = _generate_otp()
        _store_otp(email, otp)

        ok, err = _send_otp_email(email, otp)
        if not ok:
            with _lock:
                _otp_store.pop(email, None)
            return jsonify({'ok': False, 'error': err}), 500

        return jsonify({'ok': True}), 200

    @app.route('/auth/verify-otp', methods=['POST'])
    def verify_otp_route():
        data     = request.get_json(silent=True) or {}
        email    = (data.get('email')    or '').strip().lower()
        otp_in   = (data.get('otp')      or '').strip()
        remember = bool(data.get('remember', False))
        if not email or not otp_in:
            return jsonify({'ok': False, 'error': 'Email and OTP are required.'}), 400

        ok, err = _verify_otp(email, otp_in)
        if not ok:
            return jsonify({'ok': False, 'error': err}), 401

        token  = _make_jwt(email, remember)
        expiry = JWT_LONG if remember else None
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
            return 'Starting up — refresh in 10 seconds.', 503
        # Inject Gemini key from Railway env var — key never in GitHub
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
