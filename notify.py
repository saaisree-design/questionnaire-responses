
Notify · PY
#!/usr/bin/env python3
"""Emails you the report for each new response.
 
Runs at the end of the GitHub Action, after score.py has written the reports.
Standard library only.
 
Two ways to send, whichever you configure:
 
  Resend   set RESEND_API_KEY and NOTIFY_TO
  SMTP     set SMTP_HOST, SMTP_USER, SMTP_PASS and NOTIFY_TO
           (Gmail: smtp.gmail.com, port 465, an App Password as SMTP_PASS)
 
If both are set, Resend is used. If neither is set the script prints a notice
and exits quietly, so the rest of the workflow still succeeds.
 
Usage:
    python3 notify.py responses/2026-09-06T09-14-22Z_abc.json ...
    python3 notify.py                # newest response only
    python3 notify.py --dry-run ...  # print what would be sent, send nothing
"""
 
import base64
import html
import json
import os
import pathlib
import smtplib
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
 
HERE = pathlib.Path(__file__).resolve().parent
RESPONSES = HERE / "responses"
REPORTS = HERE / "reports"
 
TO = os.environ.get("NOTIFY_TO", "").strip()
FROM = os.environ.get("NOTIFY_FROM", "onboarding@resend.dev").strip()
RESEND_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_BASE = os.environ.get("RESEND_API_BASE", "https://api.resend.com").strip()
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
SMTP_STARTTLS = os.environ.get("SMTP_STARTTLS", "").strip() == "1"
 
E = html.escape
 
TRAIT_ORDER = [("E", "Extraversion"), ("A", "Agreeableness"), ("C", "Conscientiousness"),
               ("S", "Emotional stability"), ("O", "Openness")]
DICH_ORDER = [("IE", "Introversion", "Extraversion"), ("SN", "Sensing", "Intuition"),
              ("FT", "Feeling", "Thinking"), ("JP", "Judging", "Perceiving")]
 
 
def load_score_module():
    """Reuse score.py so the email can never disagree with the report."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("score", HERE / "score.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
 
 
def bar_row(label, sub, value, lo, hi, colour, note):
    """A table row with a bar drawn in table cells, because email clients
    strip <style> blocks and ignore most modern CSS."""
    pct = int(round((value - lo) / (hi - lo) * 100))
    filled = max(1, pct)
    return f"""
    <tr><td style="padding:10px 0 2px;font:600 14px -apple-system,Segoe UI,Roboto,sans-serif;color:#22272A">
      {E(label)} <span style="font-weight:400;color:#8C979A;font-size:12px">{E(sub)}</span>
      <span style="float:right;font-weight:500">{value} <span style="color:#8C979A;font-size:12px">/ {hi}</span></span>
    </td></tr>
    <tr><td style="padding:0 0 3px">
      <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse">
        <tr>
          <td width="{filled}%" style="background:{colour};height:8px;line-height:8px;font-size:0">&nbsp;</td>
          <td width="{100 - filled}%" style="background:#E7EBE6;height:8px;line-height:8px;font-size:0">&nbsp;</td>
        </tr>
      </table>
    </td></tr>
    <tr><td style="padding:0 0 8px;font:400 12px -apple-system,Segoe UI,Roboto,sans-serif;color:#5D686B">{E(note)}</td></tr>
    """
 
 
def build_email_html(rec, scored, flags, m):
    t, d = scored["traits"], scored["dichs"]
    rows = "".join(
        bar_row(name, "", t[k], 10, 50, m.TRAITS[k][2], m.trait_band(t[k]))
        for k, name in TRAIT_ORDER)
    drows = ""
    for k, low, high in DICH_ORDER:
        v = d[k]
        dist = v - m.MID
        side = "neither side" if dist == 0 else (high if dist > 0 else low)
        pct = m.REF[k]["pct"][v - 12]
        note = f"{side}, {m.lean(dist)} preference · {m.ordinal(pct)} percentile of 2,923"
        drows += bar_row(f"{low} or {high}", "", v, 12, 60, m.DICHS[k][5], note)
 
    flagbox = ""
    if flags:
        items = "; ".join(E(why) for _, why in flags)
        flagbox = f"""
        <tr><td style="background:#F2DED9;border-radius:3px;padding:12px 14px;
          font:400 13px -apple-system,Segoe UI,Roboto,sans-serif;color:#B3402E">
          <b>Answer quality warning.</b> {items}. Treat the reading below as unreliable.
        </td></tr><tr><td style="height:14px"></td></tr>"""
 
    secs = int((rec.get("elapsed_ms") or 0) / 1000)
    answered = scored["answered_a"] + scored["answered_b"]
    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#DDE4DF">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#DDE4DF;padding:24px 12px">
<tr><td align="center">
<table role="presentation" cellpadding="0" cellspacing="0" width="600" style="max-width:600px;background:#FBFBF8;border-radius:3px;padding:28px 26px">
  <tr><td style="font:500 20px Georgia,serif;color:#22272A;padding-bottom:2px">New response</td></tr>
  <tr><td style="font:400 13px -apple-system,Segoe UI,Roboto,sans-serif;color:#5D686B;padding-bottom:16px">
    {E(rec.get('email',''))} &middot; {E((rec.get('received_at') or '')[:16].replace('T',' '))} &middot;
    {answered} of 98 answered{f' &middot; {secs // 60}m {secs % 60}s' if secs else ''}
  </td></tr>
  {flagbox}
  <tr><td style="font:500 15px Georgia,serif;color:#22272A;padding:6px 0 2px">Four-letter code</td></tr>
  <tr><td style="font:500 34px Georgia,serif;color:#22272A;letter-spacing:3px;padding-bottom:10px">{E(scored['type'])}</td></tr>
  <tr><td><table role="presentation" cellpadding="0" cellspacing="0" width="100%">
    <tr><td style="font:500 15px Georgia,serif;color:#22272A;padding:14px 0 4px">Traits</td></tr>
    {rows}
    <tr><td style="font:500 15px Georgia,serif;color:#22272A;padding:18px 0 4px">Preferences</td></tr>
    {drows}
  </table></td></tr>
  <tr><td style="font:400 13px -apple-system,Segoe UI,Roboto,sans-serif;color:#5D686B;padding-top:16px">
    The full report is attached as an HTML file. Open it in a browser, or print it to PDF from there.
  </td></tr>
</table>
</td></tr></table></body></html>"""
 
 
def build_text(rec, scored, flags, m):
    t, d = scored["traits"], scored["dichs"]
    lines = [f"New response from {rec.get('email','')}",
             f"Received {rec.get('received_at','')}",
             f"Four-letter code: {scored['type']}", ""]
    if flags:
        lines += ["ANSWER QUALITY WARNING: " + "; ".join(w for _, w in flags), ""]
    lines.append("Traits (10-50)")
    for k, name in TRAIT_ORDER:
        lines.append(f"  {name:<22} {t[k]:>3}   {m.trait_band(t[k])}")
    lines.append("")
    lines.append("Preferences (12-60, midpoint 36)")
    for k, low, high in DICH_ORDER:
        v = d[k]
        side = "midpoint" if v == m.MID else (high if v > m.MID else low)
        lines.append(f"  {low}-{high:<18} {v:>3}   {side}, {m.lean(v - m.MID)}")
    lines += ["", "Full report attached."]
    return "\n".join(lines)
 
 
def send_resend(subject, html_body, text_body, attachment_name, attachment_bytes):
    payload = {
        "from": FROM, "to": [TO], "subject": subject,
        "html": html_body, "text": text_body,
        "attachments": [{"filename": attachment_name,
                         "content": base64.b64encode(attachment_bytes).decode()}],
    }
    req = urllib.request.Request(
        f"{RESEND_BASE}/emails", data=json.dumps(payload).encode(),
        headers={"authorization": f"Bearer {RESEND_KEY}", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.status, res.read().decode()[:200]
 
 
def send_smtp(subject, html_body, text_body, attachment_name, attachment_bytes):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FROM if "@" in FROM and FROM != "onboarding@resend.dev" else SMTP_USER
    msg["To"] = TO
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    msg.add_attachment(attachment_bytes, maintype="text", subtype="html", filename=attachment_name)
    if SMTP_STARTTLS:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    elif SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    return 200, "sent via smtp"
 
 
def pick_files(args):
    paths = [pathlib.Path(a) for a in args if a.endswith(".json")]
    paths = [p if p.exists() else HERE / p for p in paths]
    paths = [p for p in paths if p.exists()]
    if paths:
        return paths
    files = sorted(RESPONSES.glob("*.json"))
    return files[-1:] if files else []
 
 
def main():
    argv = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv[1:]
 
    if not dry and not TO:
        print("NOTIFY_TO is not set — skipping email, nothing else is affected")
        return 0
    if not dry and not RESEND_KEY and not SMTP_HOST:
        print("neither RESEND_API_KEY nor SMTP_HOST is set — skipping email")
        return 0
 
    files = pick_files(argv)
    if not files:
        print("no new response files to notify about")
        return 0
 
    m = load_score_module()
    sent = failed = 0
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  {f.name}: unreadable, skipped")
            continue
        scored = m.score_response(rec)
        flags = m.quality_flags(rec, scored)
        rid = rec.get("id") or f.stem
        report = REPORTS / f"{rid}.html"
        attachment = report.read_bytes() if report.exists() else b"<p>Report file not found.</p>"
        warn = " [check answers]" if flags else ""
        subject = f"Response: {rec.get('email','unknown')} — {scored['type']}{warn}"
        html_body = build_email_html(rec, scored, flags, m)
        text_body = build_text(rec, scored, flags, m)
 
        if dry:
            print(f"  would send to {TO or '(NOTIFY_TO unset)'}: {subject}")
            print(f"    attachment {report.name}, {len(attachment):,} bytes")
            out = HERE / "email-preview.html"
            out.write_text(html_body, encoding="utf-8")
            print(f"    body written to {out.name} so you can look at it")
            continue
 
        try:
            if RESEND_KEY:
                status, body = send_resend(subject, html_body, text_body, report.name, attachment)
            else:
                status, body = send_smtp(subject, html_body, text_body, report.name, attachment)
            print(f"  sent {subject} ({status})")
            sent += 1
        except urllib.error.HTTPError as err:
            detail = err.read().decode()[:300]
            print(f"  FAILED {subject}: HTTP {err.code} {detail}")
            failed += 1
        except Exception as err:
            print(f"  FAILED {subject}: {type(err).__name__} {err}")
            failed += 1
 
    if failed:
        print(f"{sent} sent, {failed} failed")
        # non-zero so the Action shows red and you find out
        return 1
    if sent:
        print(f"{sent} email(s) sent to {TO}")
    return 0
 
 
if __name__ == "__main__":
    sys.exit(main())
 






