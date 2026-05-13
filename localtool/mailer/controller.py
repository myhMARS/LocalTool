from PyQt6.QtCore import QObject, pyqtSignal

from localtool.mailer.config import AppConfig
from localtool.mailer.workers import (
    FOLDER_INBOX, FOLDER_SENT, FetchBodyWorker, FetchListWorker, SendWorker,
)


class MailController(QObject):
    """Owns all business state, caching, filtering, and worker orchestration.

    Communicates with the View exclusively through pyqtSignals.
    """

    # ── Signals (Controller → View) ──
    emails_updated = pyqtSignal(list)       # filtered+sorted email list, or grouped tuples
    loading_changed = pyqtSignal(bool)
    status_message = pyqtSignal(str)
    detail_header_ready = pyqtSignal(dict, object, bool)  # em, active_cfg, is_sent
    detail_loading = pyqtSignal()
    detail_body_ready = pyqtSignal(str, str, list, dict)  # html, text, attachments, inline_images
    detail_error = pyqtSignal(str)
    counts_updated = pyqtSignal(int, int, int)  # total, unread_count, visible_count
    marked_read = pyqtSignal(str)            # msg_id that was marked read
    config_loaded = pyqtSignal()
    list_error = pyqtSignal(str)
    send_finished = pyqtSignal()
    send_error = pyqtSignal(str)
    folder_reset = pyqtSignal(str)           # folder name — View should reset UI state

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = AppConfig()
        self._active_idx = 0
        self._email_cache: dict[str, list[dict]] = {}
        self._sent_cache: dict[str, list[dict]] = {}
        self._current_folder = FOLDER_INBOX
        self._unread_only = False
        self._grouped = False
        self._search_text = ""
        self._selected_msg_id: str | None = None
        self._fetch_worker: FetchListWorker | None = None
        self._body_worker: FetchBodyWorker | None = None
        self._send_worker: SendWorker | None = None

    # ── public properties ──

    @property
    def current_folder(self) -> str:
        return self._current_folder

    @property
    def unread_only(self) -> bool:
        return self._unread_only

    @property
    def is_grouped(self) -> bool:
        return self._grouped

    @property
    def active_idx(self) -> int:
        return self._active_idx

    @property
    def _active_cfg(self):
        return self.cfg.accounts[self._active_idx]

    @property
    def _cache_key(self) -> str:
        return self._active_cfg.email

    # ── data access ──

    def _active_emails(self) -> list[dict]:
        cache = self._sent_cache if self._current_folder == FOLDER_SENT else self._email_cache
        key = self._cache_key
        if key not in cache:
            cache[key] = []
        return cache[key]

    # ── public API (called by View) ──

    def load_config(self, cfg: AppConfig):
        """Initial config injection from app.py bootstrap."""
        self.cfg = cfg
        self._active_idx = cfg.active
        self.config_loaded.emit()
        self.refresh()

    def refresh(self):
        folder = self._current_folder
        self.status_message.emit(f"Refreshing {folder.lower()}...")
        self.loading_changed.emit(True)
        self._fetch_worker = FetchListWorker(self._active_cfg, folder)
        self._fetch_worker.finished.connect(self._on_list_fetched)
        self._fetch_worker.error.connect(self._on_list_error)
        self._fetch_worker.start()

    def switch_folder(self, folder: str):
        if self._current_folder == folder:
            return
        self._current_folder = folder
        self._unread_only = False
        self._search_text = ""
        if folder == FOLDER_SENT:
            self._grouped = False
        self.folder_reset.emit(folder)
        cached = self._active_emails()
        if cached:
            self._emit_filtered()
        else:
            self.refresh()

    def set_search(self, text: str):
        self._search_text = text.strip().lower()
        self._emit_filtered()

    def toggle_filter(self):
        if self._current_folder == FOLDER_SENT:
            return
        self._unread_only = not self._unread_only
        self._emit_filtered()

    def toggle_grouped(self):
        if self._current_folder == FOLDER_SENT:
            return
        self._grouped = not self._grouped
        self._emit_filtered()

    def select_email(self, msg_id: str):
        em = next((e for e in self._active_emails() if e["id"] == msg_id), None)
        if em is None:
            return
        self._selected_msg_id = msg_id
        is_sent = self._current_folder == FOLDER_SENT
        self.detail_header_ready.emit(em, self._active_cfg, is_sent)
        self.detail_loading.emit()
        folder = FOLDER_SENT if is_sent else FOLDER_INBOX
        self._body_worker = FetchBodyWorker(self._active_cfg, msg_id, folder)
        self._body_worker.finished.connect(self._on_body_fetched)
        self._body_worker.error.connect(self._on_body_error)
        self._body_worker.start()

    def send_email(self, to_addr: str, subject: str, body: str):
        self._send_worker = SendWorker(self._active_cfg, to_addr, subject, body)
        self._send_worker.finished.connect(self._on_sent)
        self._send_worker.error.connect(self._on_send_error)
        self._send_worker.start()

    def switch_account(self, idx: int):
        if idx < 0 or idx == self._active_idx:
            return
        self._active_idx = idx
        self.cfg.active = idx
        self._current_folder = FOLDER_INBOX
        self._unread_only = False
        self._search_text = ""
        self._grouped = False
        self._selected_msg_id = None
        self.folder_reset.emit(FOLDER_INBOX)
        cached = self._active_emails()
        if cached:
            self._emit_filtered()
        else:
            self.refresh()

    def apply_config(self, cfg: AppConfig):
        """Apply config after SettingsDialog save."""
        old_accounts = self.cfg.accounts
        self.cfg = cfg
        new_accounts = cfg.accounts
        if len(new_accounts) != len(old_accounts) or \
           any(a.email != b.email for a, b in zip(new_accounts, old_accounts)):
            self._email_cache.clear()
            self._sent_cache.clear()
        self._active_idx = min(self._active_idx, len(new_accounts) - 1)
        self.cfg.active = self._active_idx
        self.refresh()

    # ── internal: filtering ──

    def _emit_filtered(self):
        """Run filter → group → sort pipeline and emit results."""
        src = self._active_emails()
        visible = [e for e in src if not self._unread_only or e.get("unread", False)]
        if self._search_text:
            visible = [
                e for e in visible
                if self._search_text in e.get("display", "").lower()
                or self._search_text in e.get("subject", "").lower()
            ]

        from collections import OrderedDict

        if self._grouped:
            groups: dict[str, list[dict]] = OrderedDict()
            for em in visible:
                key = em.get("display", "unknown")
                groups.setdefault(key, []).append(em)
            result = []
            for key in sorted(groups, key=str.casefold):
                emails = sorted(groups[key], key=lambda e: (not e.get("unread", False), -e.get("ts", 0)))
                unread = sum(1 for e in emails if e.get("unread"))
                result.append((key, len(emails), unread, emails))
        else:
            visible.sort(key=lambda e: e.get("ts", 0), reverse=True)
            result = visible

        total = len(src)
        unread_count = sum(1 for e in src if e.get("unread"))
        visible_count = len(visible)
        self.counts_updated.emit(total, unread_count, visible_count)
        self.emails_updated.emit(result)

    # ── internal: worker callbacks ──

    def _on_list_fetched(self, emails: list[dict], status: str):
        cache = self._sent_cache if self._current_folder == FOLDER_SENT else self._email_cache
        cache[self._cache_key] = emails
        self.loading_changed.emit(False)
        self.status_message.emit(status)
        self._emit_filtered()

    def _on_list_error(self, err: str):
        self.loading_changed.emit(False)
        self.status_message.emit(f"Error: {err}")
        self.list_error.emit(err)

    def _on_body_fetched(self, html_b: str, text_b: str,
                         attachments: list | None = None,
                         inline_images: dict | None = None):
        self._mark_as_read()
        self.detail_body_ready.emit(html_b, text_b, attachments or [], inline_images or {})

    def _on_body_error(self, err: str):
        self.detail_error.emit(err)

    def _on_sent(self):
        self.send_finished.emit()
        self.status_message.emit("Message sent")
        self.refresh()

    def _on_send_error(self, err: str):
        self.send_error.emit(err)

    # ── internal: mark as read ──

    def _mark_as_read(self):
        if self._current_folder == FOLDER_SENT or not self._selected_msg_id:
            return
        src = self._active_emails()
        em = next((e for e in src if e["id"] == self._selected_msg_id), None)
        if not em or not em.get("unread"):
            return
        em["unread"] = False
        self.marked_read.emit(self._selected_msg_id)
        total = len(src)
        unread_count = sum(1 for e in src if e.get("unread"))
        visible_count = sum(1 for e in src if e.get("unread")) if self._unread_only else total
        self.counts_updated.emit(total, unread_count, visible_count)
