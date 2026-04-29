import imaplib
from datetime import datetime
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime


def connect_imap(cfg: dict):
    conn = imaplib.IMAP4_SSL(cfg["imap_host"], cfg.get("imap_port", 993))
    conn.login(cfg["email"], cfg["password"])
    return conn


def _safe_charset(charset: str | None) -> str:
    """Normalize a charset to a Python-compatible codec name."""
    if not charset:
        return "utf-8"
    cs = charset.lower().replace("-", "")
    # map common non-standard names
    aliases = {
        "unknown8bit": "utf-8",
        "unknown": "utf-8",
        "xunknown": "utf-8",
        "default": "utf-8",
        "ansi_x3.1101983": "utf-8",
    }
    if cs in aliases:
        return aliases[cs]
    # validate: try looking up the codec
    import codecs
    try:
        codecs.lookup(charset)
        return charset
    except LookupError:
        try:
            codecs.lookup(cs)
            return cs
        except LookupError:
            return "utf-8"


def decode_rfc2047(value) -> str:
    parts = decode_header(value)
    result = []
    for text, charset in parts:
        if isinstance(text, bytes):
            result.append(text.decode(_safe_charset(charset), errors="replace"))
        else:
            result.append(str(text))
    return "".join(result)


def load_email_body(msg: Message) -> tuple[str, str, list[dict], dict[str, dict]]:
    html_body, text_body = "", ""
    attachments: list[dict] = []
    inline_images: dict[str, dict] = {}

    def _safe_payload(part):
        try:
            return part.get_payload(decode=True)
        except Exception:
            # handle non-standard charsets (e.g. unknown-8bit)
            raw = part.get_payload(decode=False)
            if isinstance(raw, str):
                return raw.encode("utf-8", errors="replace")
            return raw

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            disp = part.get_content_disposition()
            payload = _safe_payload(part)
            cid = part.get("Content-ID", "").strip().strip("<>")
            if payload and cid:
                inline_images[cid] = {"content_type": ct, "data": payload}
            elif disp == "attachment" and payload:
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
        raw_payload = _safe_payload(msg)
        if raw_payload:
            ct = msg.get_content_type()
            body = raw_payload.decode(errors="replace")
            if ct == "text/html":
                html_body = body
            else:
                text_body = body
    return html_body, text_body, attachments, inline_images


def format_date(date_value) -> str:
    date_str = str(date_value) if date_value else ""
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
