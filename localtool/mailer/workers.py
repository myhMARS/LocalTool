from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.parser import BytesParser, BytesHeaderParser
from email.utils import parsedate_to_datetime

from PyQt6.QtCore import QThread, pyqtSignal

from localtool.mailer.mail import connect_imap, decode_rfc2047, load_email_body

FOLDER_INBOX = "Inbox"
FOLDER_SENT = "Sent"
_SENT_ALIASES = ("Sent Messages", "Sent Items", "[Gmail]/Sent Mail")
_header_parser = BytesHeaderParser()


def _resolve_folder(conn, folder: str) -> tuple[str, str]:
    """Select *folder* on *conn*, trying Sent aliases if needed.
    Returns (status, resolved_folder_name)."""
    status, _data = conn.select(folder)
    resolved = folder
    if status != "OK" and folder == FOLDER_SENT:
        for alt in _SENT_ALIASES:
            status, _data = conn.select(alt)
            if status == "OK":
                resolved = alt
                break
    return status, resolved


def _parse_unseen(flags_data) -> bool:
    """Return True if the message has no \\Seen flag (i.e. is unread)."""
    raw = flags_data.decode(errors="replace") if isinstance(flags_data, bytes) else str(flags_data)
    return "\\Seen" not in raw


def _parse_date(date_value) -> tuple[str, float]:
    """Parse a Date header once and return (display_str, timestamp)."""
    date_str = str(date_value) if date_value else ""
    try:
        dt = parsedate_to_datetime(date_str)
        now = datetime.now(dt.tzinfo)
        diff = now - dt
        if diff.days == 0:
            display = dt.strftime("%H:%M")
        elif diff.days < 7:
            display = dt.strftime("%a %H:%M")
        elif diff.days < 365:
            display = dt.strftime("%m-%d %H:%M")
        else:
            display = dt.strftime("%Y-%m-%d %H:%M")
        return display, dt.timestamp()
    except Exception:
        return date_str[:16] if len(date_str) > 16 else date_str, 0.0


def _parse_headers(body_part: bytes, flags_raw: bytes, is_sent: bool) -> dict | None:
    """Parse headers from a single message fetch response. Returns dict or None on failure."""
    try:
        _msg = _header_parser.parsebytes(body_part)
        _subject = decode_rfc2047(_msg.get("Subject", "")) or "(no subject)"
        _to_raw = decode_rfc2047(_msg.get("To", "")) or ""
        _from = decode_rfc2047(_msg.get("From", "")) or "(unknown)"
        if _from.endswith(">"):
            name_part = _from.rsplit("<", 1)[0].strip().strip('"')
            if name_part:
                _from = name_part
        _display = _from
        if is_sent and _to_raw:
            _display = _to_raw
            if _display.endswith(">"):
                name_part = _display.rsplit("<", 1)[0].strip().strip('"')
                if name_part:
                    _display = name_part
        _date, _ts = _parse_date(_msg.get("Date", ""))
        mid_str = flags_raw.split()[0].decode()
        return {
            "id": mid_str,
            "from": _from,
            "display": _display,
            "to": _to_raw,
            "subject": _subject,
            "date": _date,
            "ts": _ts,
            "unread": _parse_unseen(flags_raw),
        }
    except Exception:
        return None


def _fetch_chunk(cfg: dict, folder: str, id_chunk: list[bytes], is_sent: bool) -> list[dict]:
    """Fetch a chunk of message headers over a dedicated IMAP connection."""
    conn = connect_imap(cfg)
    conn.select(folder)
    parsed = []
    for batch_start in range(0, len(id_chunk), 200):
        batch_ids = id_chunk[batch_start:batch_start + 200]
        id_range = b",".join(batch_ids)
        _status, _msg_data = conn.fetch(
            id_range, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])"
        )
        if _status != "OK":
            continue
        for item in _msg_data:
            if not isinstance(item, tuple):
                continue
            try:
                flags_raw = item[0]
                body_part = item[1]
            except (IndexError, TypeError):
                continue
            entry = _parse_headers(body_part, flags_raw, is_sent)
            if entry is not None:
                parsed.append(entry)
    conn.logout()
    return parsed


class FetchListWorker(QThread):
    """Fetch email list using multiple concurrent IMAP connections.

    Message IDs are partitioned across *NUM_WORKERS* connections, each
    fetching its chunk independently. This overlaps network round-trips
    and server-side processing, giving roughly NUM_WORKERS× speedup for
    large mailboxes.
    """

    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

    NUM_WORKERS = 4
    MIN_IDS_FOR_PARALLEL = 800

    def __init__(self, cfg: dict, folder: str = FOLDER_INBOX):
        super().__init__()
        self.cfg = cfg
        self.folder = folder

    def run(self):
        try:
            conn = connect_imap(self.cfg)
            status, folder = _resolve_folder(conn, self.folder)
            if status != "OK":
                conn.logout()
                self.error.emit(f'folder "{self.folder}" not found')
                return
            status, data = conn.search(None, "ALL")
            conn.logout()
            if status != "OK":
                self.error.emit("search failed")
                return
            ids = data[0].split()
            is_sent = folder != FOLDER_INBOX
            reversed_ids = list(reversed(ids))

            if len(reversed_ids) >= self.MIN_IDS_FOR_PARALLEL:
                parsed = self._fetch_parallel(reversed_ids, folder, is_sent)
            else:
                parsed = _fetch_chunk(self.cfg, folder, reversed_ids, is_sent)

            unread_count = sum(1 for e in parsed if e["unread"])
            folder_label = "Sent" if is_sent else "Inbox"
            self.finished.emit(parsed, f"{len(parsed)} messages in {folder_label}  ({unread_count} unread)")
        except Exception as e:
            self.error.emit(str(e))

    def _fetch_parallel(self, reversed_ids: list, folder: str, is_sent: bool) -> list[dict]:
        """Split IDs across NUM_WORKERS connections, fetch concurrently, sort by date desc."""
        chunk_size = max(200, len(reversed_ids) // self.NUM_WORKERS)
        chunks = []
        for i in range(0, len(reversed_ids), chunk_size):
            chunks.append(reversed_ids[i:i + chunk_size])
        all_parsed = []
        with ThreadPoolExecutor(max_workers=self.NUM_WORKERS) as pool:
            futures = {
                pool.submit(_fetch_chunk, self.cfg, folder, chunk, is_sent): idx
                for idx, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                all_parsed.extend(future.result())

        all_parsed.sort(key=lambda e: e.get("ts", 0), reverse=True)
        return all_parsed


class FetchBodyWorker(QThread):
    finished = pyqtSignal(str, str, list, dict)
    error = pyqtSignal(str)

    def __init__(self, cfg: dict, msg_id: str, folder: str = FOLDER_INBOX):
        super().__init__()
        self.cfg = cfg
        self.msg_id = msg_id
        self.folder = folder

    def run(self):
        try:
            conn = connect_imap(self.cfg)
            status, _folder = _resolve_folder(conn, self.folder)
            if status != "OK":
                conn.logout()
                self.error.emit(f'folder "{self.folder}" not found')
                return
            status, msg_data = conn.fetch(self.msg_id.encode(), "(RFC822)")
            if status != "OK":
                conn.logout()
                self.error.emit("fetch failed")
                return
            raw = msg_data[0][1]
            msg = BytesParser().parsebytes(raw)
            # mark as seen on server (inbox only)
            if self.folder == FOLDER_INBOX:
                conn.store(self.msg_id.encode(), "+FLAGS", "\\Seen")
            conn.logout()
            html_b, text_b, attachments, inline_images = load_email_body(msg)
            self.finished.emit(html_b, text_b, attachments, inline_images)
        except Exception as e:
            self.error.emit(str(e))


class SendWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, cfg: dict, to_addr: str, subject: str, body: str):
        super().__init__()
        self.cfg = cfg
        self.to_addr = to_addr
        self.subject = subject
        self.body = body

    def run(self):
        import smtplib
        from email.mime.text import MIMEText

        try:
            msg = MIMEText(self.body)
            msg["From"] = self.cfg["email"]
            msg["To"] = self.to_addr
            msg["Subject"] = self.subject
            with smtplib.SMTP(self.cfg["smtp_host"], self.cfg.get("smtp_port", 587)) as smtp:
                smtp.starttls()
                smtp.login(self.cfg["email"], self.cfg["password"])
                smtp.send_message(msg)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))
