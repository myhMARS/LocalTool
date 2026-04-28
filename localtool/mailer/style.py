AVATAR_COLORS = [
    "#4D6BFE", "#F97316", "#10B981", "#EF4444", "#8B5CF6",
    "#06B6D4", "#E11D48", "#3B82F6", "#059669", "#EC4899",
    "#1E3A5F", "#14B8A6", "#DC2626", "#D97706", "#475569",
]


def avatar_color(name: str) -> str:
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return AVATAR_COLORS[h % len(AVATAR_COLORS)]


def avatar_initials(name: str) -> str:
    name = name.strip()
    if not name:
        return "?"
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


STYLE = """
/* ============================================================
   GLOBAL
   ============================================================ */
QMainWindow {
    background: #F9FAFB;
}
QStatusBar {
    background: #F3F4F6;
    color: #6B7280;
    font-size: 11px;
    letter-spacing: 0.3px;
    border-top: 1px solid #E5E7EB;
    padding: 4px 16px;
}

/* ============================================================
   TOOLBAR
   ============================================================ */
#toolbar {
    background: #FFFFFF;
    border-bottom: 1px solid #E5E7EB;
    padding: 12px 24px;
}
#toolbar_title {
    font-size: 18px;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.3px;
}
#toolbar_subtitle {
    font-size: 12px;
    color: #9CA3AF;
    font-weight: 500;
}

/* ============================================================
   BUTTONS
   ============================================================ */
QPushButton {
    background: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 8px 18px;
    color: #374151;
    font-size: 12.5px;
    font-weight: 600;
    letter-spacing: 0.2px;
}
QPushButton:hover {
    background: #F3F4F6;
    border-color: #D1D5DB;
}
QPushButton:pressed {
    background: #E5E7EB;
}
QPushButton:disabled {
    background: #F9FAFB;
    color: #D1D5DB;
    border-color: #E5E7EB;
}

QPushButton#primary_btn {
    background: #4D6BFE;
    color: #FFFFFF;
    border: none;
    padding: 9px 22px;
    font-weight: 700;
    letter-spacing: 0.3px;
}
QPushButton#primary_btn:hover {
    background: #3F5CE5;
}
QPushButton#primary_btn:pressed {
    background: #2F4CD4;
}
QPushButton#primary_btn:disabled {
    background: #A5B4FC;
    color: #E0E7FF;
}

QPushButton#danger_btn {
    background: #FEF2F2;
    border: 1px solid #FECACA;
    color: #EF4444;
}
QPushButton#danger_btn:hover {
    background: #FEE2E2;
}

QPushButton#text_btn {
    background: transparent;
    border: none;
    color: #4D6BFE;
    padding: 6px 12px;
    font-weight: 600;
}
QPushButton#text_btn:hover {
    background: #EEF2FF;
    border-radius: 6px;
}

QPushButton#tool_btn {
    background: transparent;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 6px 14px;
    color: #6B7280;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#tool_btn:hover {
    background: #F3F4F6;
    border-color: #D1D5DB;
    color: #4D6BFE;
}

/* ============================================================
   EMAIL LIST
   ============================================================ */
QListWidget {
    background: #FFFFFF;
    border: none;
    outline: none;
    padding: 6px 8px;
}
QListWidget::item {
    border: none;
    padding: 0px;
    background: #FFFFFF;
    border-radius: 8px;
    margin: 1px 0;
}
QListWidget::item:selected {
    background: #EEF2FF;
}
QListWidget::item:hover {
    background: #F9FAFB;
}

/* ============================================================
   DETAIL PANEL
   ============================================================ */
#detail_panel {
    background: #FFFFFF;
}
#detail_header {
    background: #F9FAFB;
    border-bottom: 1px solid #E5E7EB;
    padding: 24px 28px;
}
#detail_subject {
    font-size: 21px;
    font-weight: 800;
    color: #111827;
    letter-spacing: -0.2px;
}
#detail_meta {
    font-size: 13px;
    color: #6B7280;
    font-weight: 500;
}
#detail_meta_light {
    font-size: 12px;
    color: #9CA3AF;
}
QWebEngineView {
    background: #F9FAFB;
    border: none;
}

/* ============================================================
   DIALOGS
   ============================================================ */
QDialog {
    background: #F9FAFB;
    border-radius: 12px;
}
QLineEdit, QTextEdit {
    background: #FFFFFF;
    border: 1.5px solid #E5E7EB;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    color: #111827;
    selection-background-color: #4D6BFE;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #4D6BFE;
    background: #FFFFFF;
}
QLineEdit::placeholder, QTextEdit::placeholder {
    color: #D1D5DB;
}
QLabel {
    color: #374151;
    font-size: 13px;
}
QFormLayout QLabel {
    font-weight: 600;
    color: #6B7280;
}

/* ============================================================
   SCROLLBAR
   ============================================================ */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 4px 2px;
}
QScrollBar::handle:vertical {
    background: #D1D5DB;
    border-radius: 3px;
    min-height: 36px;
}
QScrollBar::handle:vertical:hover {
    background: #9CA3AF;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    height: 6px;
    margin: 2px 4px;
}
QScrollBar::handle:horizontal {
    background: #D1D5DB;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: #9CA3AF;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ============================================================
   SPLITTER
   ============================================================ */
QSplitter::handle {
    background: #E5E7EB;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ============================================================
   SCROLL AREA
   ============================================================ */
QScrollArea {
    background: transparent;
    border: none;
}

/* ============================================================
   MISC
   ============================================================ */
QToolTip {
    background: #111827;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
}
"""
