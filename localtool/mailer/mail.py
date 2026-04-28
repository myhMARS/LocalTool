import imaplib
from datetime import datetime
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime


def connect_imap(cfg: dict):
    conn = imaplib.IMAP4_SSL(cfg["imap_host"], cfg.get("imap_port", 993))
    conn.login(cfg["email"], cfg["password"])
    return conn


def decode_rfc2047(value: str) -> str:
    parts = decode_header(value)
    result = []
    for text, charset in parts:
        if isinstance(text, bytes):
            result.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(text))
    return "".join(result)


def load_email_body(msg: Message) -> tuple[str, str, list[dict]]:
    html_body, text_body = "", ""
    attachments: list[dict] = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = part.get_content_disposition()
            payload = part.get_payload(decode=True)
            if disp == "attachment" and payload:
                filename = part.get_filename() or "unnamed"
                attachments.append({
                    "filename": filename,
                    "content_type": ct,
                    "size": len(payload),
                    "data": payload,
                })
            elif payload:
                if ct == "text/html" and not html_body:
                    html_body = payload.decode(errors="replace")
                elif ct == "text/plain" and not text_body:
                    text_body = payload.decode(errors="replace")
    else:
        raw_payload = msg.get_payload(decode=True)
        if raw_payload:
            ct = msg.get_content_type()
            body = raw_payload.decode(errors="replace")
            if ct == "text/html":
                html_body = body
            else:
                text_body = body
    return html_body, text_body, attachments


def format_date(date_str: str) -> str:
    try:
        dt = parsedate_to_datetime(date_str)
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        if diff.days == 0:
            return dt.strftime("%H:%M")
        elif diff.days < 7:
            return dt.strftime("%a %H:%M")
        elif diff.days < 365:
            return dt.strftime("%m-%d %H:%M")
        else:
            return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return date_str[:16] if len(date_str) > 16 else date_str
