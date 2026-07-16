# -*- coding: utf-8 -*-
"""
Email Utility - ElevateIQ Assessment Notifications.
Sends HTML emails via Gmail SMTP.
  SMTP_EMAIL     - sender Gmail address
  SMTP_PASSWORD  - Gmail App Password
  APP_BASE_URL   - base URL for assessment links (default: http://localhost:5000)
"""
import os, smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

APP_BASE_URL  = os.getenv("APP_BASE_URL", "http://localhost:5000")


def _send(to_email, subject, html_body):
    smtp_email    = os.getenv("SMTP_EMAIL", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_host     = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port     = int(os.getenv("SMTP_PORT", 587))
    if not smtp_email or not smtp_password:
        logger.warning("SMTP credentials not configured - email not sent.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"EduTech Academy <{smtp_email}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo(); server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())
        logger.info(f"Email sent -> {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email failed -> {to_email}: {e}")
        return False


def send_assessment_email(candidate_name, to_email, token, job_title, password=None):
    url = f"{APP_BASE_URL}/assessment.html?token={token}"
    login_url = f"{APP_BASE_URL}/login.html"
    subject = f"Your Job Assessment - {job_title} | ElevateIQ"
    
    cred_html = ""
    if password:
        cred_html = f"""
        <div class="info-box" style="border-color:rgba(0,150,255,0.25);background:rgba(0,150,255,0.02);">
          <div style="font-weight:700;color:#3ea6ff;margin-bottom:8px;font-size:14px;">🔑 Your Candidate Account Details</div>
          <div style="font-size:13px;color:#9baec8;line-height:1.5;margin-bottom:10px;">
            We have automatically created an account for you. Use these credentials to track your application and view your test history in the Candidate Portal:
          </div>
          <div class="info-row"><span class="info-label">Portal URL</span><span class="info-value"><a href="{login_url}" style="color:#3ea6ff;text-decoration:none;">{login_url}</a></span></div>
          <div class="info-row"><span class="info-label">Username</span><span class="info-value" style="color:#fff;">{to_email}</span></div>
          <div class="info-row"><span class="info-label">Temporary Password</span><span class="info-value" style="color:#ff9100;font-family:monospace;">{password}</span></div>
        </div>
        """

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#0a1628;color:#e0e6f0;margin:0;padding:0}}
.container{{max-width:580px;margin:40px auto;background:linear-gradient(135deg,#0f2240,#0a1628);border:1px solid rgba(255,255,255,0.08);border-radius:18px;overflow:hidden}}
.header{{background:linear-gradient(135deg,#1a3a6e,#0e2550);padding:32px 36px 24px;text-align:center}}
.logo{{font-size:26px;font-weight:800;color:#fff}}.logo span{{color:#3ea6ff}}
.badge{{display:inline-block;background:rgba(62,166,255,0.15);border:1px solid rgba(62,166,255,0.3);color:#3ea6ff;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600;margin-top:12px}}
.body{{padding:32px 36px}}h1{{font-size:22px;color:#fff;margin:0 0 8px}}
p{{color:#9baec8;line-height:1.7;font-size:14px;margin:12px 0}}
.info-box{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:18px;margin:20px 0}}
.info-row{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:13px}}
.info-row:last-child{{border-bottom:none}}.info-label{{color:#6b7fa3}}.info-value{{color:#fff;font-weight:600}}
.warning{{background:rgba(255,165,0,0.08);border:1px solid rgba(255,165,0,0.25);border-radius:10px;padding:14px 18px;margin:20px 0}}
.warning p{{color:#ffb347;margin:0;font-size:13px}}
.btn-wrap{{text-align:center;margin:32px 0 20px}}
.btn{{display:inline-block;background:linear-gradient(135deg,#3ea6ff,#0077cc);color:#fff;text-decoration:none;padding:15px 38px;border-radius:12px;font-weight:700;font-size:15px}}
.link-copy{{word-break:break-all;background:rgba(255,255,255,0.04);padding:10px 14px;border-radius:8px;font-size:11px;color:#6b7fa3;margin-top:8px;border:1px solid rgba(255,255,255,0.06)}}
.footer{{text-align:center;padding:20px 36px 28px;color:#4a5a7a;font-size:12px}}
</style></head><body>
<div class="container">
  <div class="header"><div class="logo">Elevate<span>IQ</span></div><div class="badge">Assessment Invitation</div></div>
  <div class="body">
    <h1>Hi {candidate_name},</h1>
    <p>Congratulations on your application! Please complete the short online assessment to proceed.</p>
    
    {cred_html}

    <div class="info-box">
      <div class="info-row"><span class="info-label">Applied Role</span><span class="info-value">{job_title}</span></div>
      <div class="info-row"><span class="info-label">Duration</span><span class="info-value">30 minutes</span></div>
      <div class="info-row"><span class="info-label">Format</span><span class="info-value">Multiple Choice Questions</span></div>
      <div class="info-row"><span class="info-label">Link Valid For</span><span class="info-value">72 hours</span></div>
    </div>
    <div class="warning"><p>Anti-Cheat Notice: Screen sharing is required. Tab switching is monitored - more than 3 switches will auto-submit your test.</p></div>
    <div class="btn-wrap"><a href="{url}" class="btn">Start My Assessment</a></div>
    <p style="text-align:center;font-size:12px;">Or copy: </p><div class="link-copy">{url}</div>
    <p>Good luck! - The ElevateIQ Recruitment Team</p>
  </div>
  <div class="footer">2026 ElevateIQ. Automated email.</div>
</div></body></html>"""
    return _send(to_email, subject, html)


def send_completion_email(candidate_name, to_email, score, total, percentage, job_title):
    subject = f"Assessment Completed - {job_title} | ElevateIQ"
    color = "#00e676" if percentage >= 80 else ("#ffeb3b" if percentage >= 60 else "#ff5252")
    feedback = ("Excellent work! Our team will review your full application shortly." if percentage >= 80
                else ("Good effort! Our recruiters will be in touch." if percentage >= 60
                      else "Thank you for completing the assessment. Our team will evaluate all results carefully."))
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#0a1628;color:#e0e6f0;margin:0;padding:0}}
.container{{max-width:580px;margin:40px auto;background:linear-gradient(135deg,#0f2240,#0a1628);border:1px solid rgba(255,255,255,0.08);border-radius:18px;overflow:hidden}}
.header{{background:linear-gradient(135deg,#1a3a6e,#0e2550);padding:32px 36px 24px;text-align:center}}
.logo{{font-size:26px;font-weight:800;color:#fff}}.logo span{{color:#3ea6ff}}
.badge{{display:inline-block;background:rgba(0,230,118,0.12);border:1px solid rgba(0,230,118,0.3);color:#00e676;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600;margin-top:12px}}
.body{{padding:32px 36px}}h1{{font-size:22px;color:#fff;margin:0 0 8px}}
p{{color:#9baec8;line-height:1.7;font-size:14px;margin:12px 0}}
.score-card{{text-align:center;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:28px;margin:24px 0}}
.score-number{{font-size:52px;font-weight:800;color:{color};line-height:1}}
.score-label{{color:#6b7fa3;font-size:13px;margin-top:6px}}.score-sub{{font-size:18px;font-weight:600;color:#fff;margin-top:10px}}
.info-box{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:18px;margin:20px 0}}
.info-row{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:13px}}
.info-row:last-child{{border-bottom:none}}.info-label{{color:#6b7fa3}}.info-value{{color:#fff;font-weight:600}}
.footer{{text-align:center;padding:20px 36px 28px;color:#4a5a7a;font-size:12px}}
</style></head><body>
<div class="container">
  <div class="header"><div class="logo">Elevate<span>IQ</span></div><div class="badge">Assessment Submitted</div></div>
  <div class="body">
    <h1>Well done, {candidate_name}!</h1>
    <p>You have successfully completed the assessment for <strong style="color:#fff;">{job_title}</strong>.</p>
    <div class="score-card">
      <div class="score-number">{percentage:.0f}%</div>
      <div class="score-label">Overall Score</div>
      <div class="score-sub">{score} / {total} correct</div>
    </div>
    <div class="info-box">
      <div class="info-row"><span class="info-label">Applied Role</span><span class="info-value">{job_title}</span></div>
      <div class="info-row"><span class="info-label">Correct Answers</span><span class="info-value">{score} / {total}</span></div>
      <div class="info-row"><span class="info-label">Score</span><span class="info-value" style="color:{color};">{percentage:.1f}%</span></div>
      <div class="info-row"><span class="info-label">Next Step</span><span class="info-value">Recruiter Review</span></div>
    </div>
    <p>{feedback}</p>
    <p>- The ElevateIQ Recruitment Team</p>
  </div>
  <div class="footer">2026 ElevateIQ. Automated email.</div>
</div></body></html>"""
    return _send(to_email, subject, html)


def send_password_reset_email(user_name, to_email, token, portal):
    """Send a password reset link to the user based on which portal they are reset from."""
    if portal == "edutech":
        url = f"{APP_BASE_URL}/edutech/reset-password.html?token={token}"
        portal_name = "EduTech Academy"
    else:
        url = f"{APP_BASE_URL}/reset-password.html?token={token}"
        portal_name = "ElevateIQ Portal"

    subject = f"Password Reset Request - {portal_name}"
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#0a1628;color:#e0e6f0;margin:0;padding:0}}
.container{{max-width:580px;margin:40px auto;background:linear-gradient(135deg,#0f2240,#0a1628);border:1px solid rgba(255,255,255,0.08);border-radius:18px;overflow:hidden}}
.header{{background:linear-gradient(135deg,#1a3a6e,#0e2550);padding:32px 36px 24px;text-align:center}}
.logo{{font-size:26px;font-weight:800;color:#fff}}.logo span{{color:#3ea6ff}}
.badge{{display:inline-block;background:rgba(255,145,0,0.12);border:1px solid rgba(255,145,0,0.3);color:#ff9100;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600;margin-top:12px}}
.body{{padding:32px 36px}}h1{{font-size:22px;color:#fff;margin:0 0 8px}}
p{{color:#9baec8;line-height:1.7;font-size:14px;margin:12px 0}}
.btn-wrap{{text-align:center;margin:32px 0 20px}}
.btn{{display:inline-block;background:linear-gradient(135deg,#ff9100,#ff6d00);color:#fff;text-decoration:none;padding:15px 38px;border-radius:12px;font-weight:700;font-size:15px}}
.link-copy{{word-break:break-all;background:rgba(255,255,255,0.04);padding:10px 14px;border-radius:8px;font-size:11px;color:#6b7fa3;margin-top:8px;border:1px solid rgba(255,255,255,0.06)}}
.footer{{text-align:center;padding:20px 36px 28px;color:#4a5a7a;font-size:12px}}
</style></head><body>
<div class="container">
  <div class="header"><div class="logo">Elevate<span>IQ</span></div><div class="badge">Password Reset</div></div>
  <div class="body">
    <h1>Hello {user_name},</h1>
    <p>We received a request to reset your password for your {portal_name} account. Click the button below to set a new password:</p>
    <div class="btn-wrap"><a href="{url}" class="btn">Reset Password</a></div>
    <p style="text-align:center;font-size:12px;">This link will expire in 1 hour. If you didn't request a reset, you can safely ignore this email.</p>
    <p style="text-align:center;font-size:12px;">Or copy this link:</p><div class="link-copy">{url}</div>
  </div>
  <div class="footer">2026 ElevateIQ. Automated email.</div>
</div></body></html>"""
    return _send(to_email, subject, html)


def send_enrollment_credentials_email(user_name, to_email, password, course_title):
    subject = f"Your Course Enrollment & Login Credentials | EduTech Academy"
    login_url = f"{APP_BASE_URL}/edutech/login.html"
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#0a1628;color:#e0e6f0;margin:0;padding:0}}
.container{{max-width:580px;margin:40px auto;background:linear-gradient(135deg,#0f2240,#0a1628);border:1px solid rgba(255,255,255,0.08);border-radius:18px;overflow:hidden}}
.header{{background:linear-gradient(135deg,#1a3a6e,#0e2550);padding:32px 36px 24px;text-align:center}}
.logo{{font-size:26px;font-weight:800;color:#fff}}.logo span{{color:#ff7a00}}
.badge{{display:inline-block;background:rgba(255,122,0,0.15);border:1px solid rgba(255,122,0,0.3);color:#ff7a00;padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600;margin-top:12px}}
.body{{padding:32px 36px}}h1{{font-size:22px;color:#fff;margin:0 0 8px}}
p{{color:#9baec8;line-height:1.7;font-size:14px;margin:12px 0}}
.info-box{{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:18px;margin:20px 0}}
.info-row{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:13px}}
.info-row:last-child{{border-bottom:none}}.info-label{{color:#6b7fa3}}.info-value{{color:#fff;font-weight:600}}
.btn-wrap{{text-align:center;margin:32px 0 20px}}
.btn{{display:inline-block;background:linear-gradient(135deg,#ff7a00,#ff5100);color:#fff;text-decoration:none;padding:15px 38px;border-radius:12px;font-weight:700;font-size:15px}}
.footer{{text-align:center;padding:20px 36px 28px;color:#4a5a7a;font-size:12px}}
</style></head><body>
<div class="container">
  <div class="header"><div class="logo">EduTech<span>Academy</span></div><div class="badge">Enrollment Confirmed</div></div>
  <div class="body">
    <h1>Welcome to EduTech Academy, {user_name}!</h1>
    <p>We are excited to help you jumpstart your career track. You have successfully enrolled in <strong>{course_title}</strong>.</p>
    
    <div class="info-box" style="border-color:rgba(255,122,0,0.25);background:rgba(255,122,0,0.02);">
      <div style="font-weight:700;color:#ff7a00;margin-bottom:8px;font-size:14px;">🔑 Your Login Credentials</div>
      <div style="font-size:13px;color:#9baec8;line-height:1.5;margin-bottom:10px;">
        Use these credentials to log in and start learning on your Student Dashboard:
      </div>
      <div class="info-row"><span class="info-label">Portal URL</span><span class="info-value"><a href="{login_url}" style="color:#ff7a00;text-decoration:none;">{login_url}</a></span></div>
      <div class="info-row"><span class="info-label">Username (Email)</span><span class="info-value" style="color:#fff;">{to_email}</span></div>
      <div class="info-row"><span class="info-label">Generated Password</span><span class="info-value" style="color:#ff7a00;font-family:monospace;">{password}</span></div>
    </div>
    
    <div class="btn-wrap"><a href="{login_url}" class="btn">Log In & Start Learning</a></div>
  </div>
  <div class="footer">2026 EduTech Academy. Automated email.</div>
</div></body></html>"""
    return _send(to_email, subject, html)


def send_invoice_email(user_name, to_email, course_title, price_paid, enrollment_id, mode, enrolled_at, expires_at):
    """Send a premium styled invoice email after course enrollment/payment."""
    import datetime
    subject = f"Payment Invoice #{enrollment_id} — {course_title} | EduTech Academy"
    login_url = f"{APP_BASE_URL}/edutech/login.html"
    invoice_url = f"{APP_BASE_URL}/edutech/invoice.html?enrollment_id={enrollment_id}"
    
    gst = round(price_paid * 18 / 118, 2)
    subtotal = round(price_paid - gst, 2)
    invoice_date = enrolled_at.strftime("%d %b %Y") if hasattr(enrolled_at, 'strftime') else str(enrolled_at)
    expiry_str = expires_at.strftime("%d %b %Y") if hasattr(expires_at, 'strftime') else str(expires_at)
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f1f5f9;margin:0;padding:0;color:#1e293b}}
.wrap{{max-width:600px;margin:30px auto;background:#fff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 8px 30px rgba(0,0,0,0.08)}}
.top-bar{{background:linear-gradient(135deg,#0f2240,#1a3a6e);padding:28px 36px;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-size:22px;font-weight:800;color:#fff}}.logo span{{color:#ff7a00}}
.badge{{background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.4);color:#4ade80;padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.5px}}
.body{{padding:32px 36px}}
.inv-ref{{font-size:12px;color:#64748b;margin-bottom:4px}}
.inv-title{{font-size:22px;font-weight:800;color:#0f172a;margin-bottom:24px}}
.course-box{{background:linear-gradient(135deg,#eff6ff,#f0fdf4);border:1px solid #bfdbfe;border-radius:12px;padding:18px;margin-bottom:24px;display:flex;align-items:center;gap:14px}}
.course-icon{{width:46px;height:46px;border-radius:10px;background:linear-gradient(135deg,#ff7a00,#ff5100);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}}
.course-name{{font-size:15px;font-weight:700;color:#0f172a}}.course-mode{{font-size:12px;color:#64748b;margin-top:3px}}
table{{width:100%;border-collapse:collapse;margin-bottom:20px}}
th{{background:#f8fafc;padding:10px 14px;font-size:11px;color:#64748b;text-align:left;border-bottom:1px solid #e2e8f0;font-weight:600;text-transform:uppercase}}
td{{padding:12px 14px;font-size:13px;border-bottom:1px solid #f1f5f9;color:#374151}}
.total-row td{{font-weight:700;color:#0f172a;font-size:14px;border-top:2px solid #e2e8f0;border-bottom:none}}
.paid-stamp{{text-align:center;margin:20px 0}}
.paid-badge{{display:inline-block;background:rgba(34,197,94,0.08);border:2px solid #22c55e;color:#16a34a;padding:8px 28px;border-radius:8px;font-size:18px;font-weight:800;letter-spacing:2px}}
.btn-wrap{{text-align:center;margin:24px 0 8px}}
.btn{{display:inline-block;background:linear-gradient(135deg,#ff7a00,#ff5100);color:#fff;text-decoration:none;padding:13px 32px;border-radius:10px;font-weight:700;font-size:14px}}
.footer{{background:#f8fafc;padding:16px 36px;text-align:center;font-size:11px;color:#94a3b8;border-top:1px solid #e2e8f0}}
</style></head><body>
<div class="wrap">
  <div class="top-bar">
    <div class="logo">EduTech<span>Academy</span></div>
    <div class="badge">✓ PAYMENT RECEIVED</div>
  </div>
  <div class="body">
    <div class="inv-ref">Invoice #{enrollment_id} &nbsp;·&nbsp; {invoice_date}</div>
    <div class="inv-title">Tax Invoice Receipt</div>

    <div class="course-box">
      <div class="course-icon">📚</div>
      <div>
        <div class="course-name">{course_title}</div>
        <div class="course-mode">Mode: {mode} &nbsp;·&nbsp; Access until: {expiry_str}</div>
      </div>
    </div>

    <table>
      <thead><tr><th>Description</th><th style="text-align:right">Amount</th></tr></thead>
      <tbody>
        <tr><td>Course Tuition — {course_title}</td><td style="text-align:right">₹{subtotal:,.2f}</td></tr>
        <tr><td>GST (18% inclusive)</td><td style="text-align:right">₹{gst:,.2f}</td></tr>
        <tr class="total-row"><td>Total Amount Paid</td><td style="text-align:right;color:#ff7a00">₹{price_paid:,.2f}</td></tr>
      </tbody>
    </table>

    <div class="paid-stamp"><div class="paid-badge">PAID</div></div>

    <p style="font-size:13px;color:#475569;text-align:center;margin:16px 0;">
      Hi <strong>{user_name}</strong>, your enrollment for <strong>{course_title}</strong> is confirmed. 
      Keep this email as your payment receipt.
    </p>

    <div class="btn-wrap">
      <a href="{invoice_url}" class="btn">View Full Invoice</a>
    </div>
  </div>
  <div class="footer">EduTech Academy &nbsp;·&nbsp; 2026 &nbsp;·&nbsp; Automated receipt — do not reply</div>
</div></body></html>"""
    return _send(to_email, subject, html)
