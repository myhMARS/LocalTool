import email.parser

from PyQt6.QtCore import QThread, pyqtSignal

from localtool.mailer.mail import connect_imap, decode_rfc2047, format_date, load_email_body

FOLDER_INBOX = "Inbox"
FOLDER_SENT = "Sent"
_SENT_ALIASES = ("Sent Messages", "Sent Items", "[Gmail]/Sent Mail")


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


class FetchListWorker(QThread):
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)

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
            if status != "OK":
                conn.logout()
                self.error.emit("search failed")
                return
            ids = data[0].split()
            parsed = []
            is_sent = folder != FOLDER_INBOX
            for mid in reversed(ids):
                _status, _msg_data = conn.fetch(
                    mid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])"
                )
                if _status == "OK":
                    flags_raw = _msg_data[0][0]
                    body_part = _msg_data[0][1]
                    unread = _parse_unseen(flags_raw)

                    _msg = email.parser.BytesParser().parsebytes(body_part)
                    _subject = decode_rfc2047(_msg.get("Subject", "")) or "(no subject)"
                    _to_raw = decode_rfc2047(_msg.get("To", "")) or ""
                    _from = decode_rfc2047(_msg.get("From", "")) or "(unknown)"
                    if _from.endswith(">"):
                        name_part = _from.rsplit("<", 1)[0].strip().strip('"')
                        if name_part:
                            _from = name_part
                    # for sent folder, display the recipient instead of sender
                    _display = _from
                    if is_sent and _to_raw:
                        _display = _to_raw
                        if _display.endswith(">"):
                            name_part = _display.rsplit("<", 1)[0].strip().strip('"')
                            if name_part:
                                _display = name_part
                    _date = format_date(_msg.get("Date", ""))
                    parsed.append({
                        "id": mid.decode(),
                        "from": _from,
                        "display": _display,
                        "to": _to_raw,
                        "subject": _subject,
                        "date": _date,
                        "unread": unread,
                    })
            conn.logout()
            unread_count = sum(1 for e in parsed if e["unread"])
            folder_label = "Sent" if is_sent else "Inbox"
            self.finished.emit(parsed, f"{len(parsed)} messages in {folder_label}  ({unread_count} unread)")
        except Exception as e:
            self.error.emit(str(e))


class FetchBodyWorker(QThread):
    finished = pyqtSignal(str, str)
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
            conn.logout()
            if status != "OK":
                self.error.emit("fetch failed")
                return
            raw = msg_data[0][1]
            msg = email.parser.BytesParser().parsebytes(raw)
            html_b, text_b = load_email_body(msg)
            self.finished.emit(html_b, text_b)
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
