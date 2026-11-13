"""
Personal Rutin v1.1 - aplikasi desktop Windows (PySide6)

Jalankan: klik dua kali file ini (.pyw = tanpa jendela console)
Install : pip install PySide6

Data tersimpan di file "personal_rutin.cfg" di folder yang sama dengan aplikasi,
jadi cukup copy folder ini ke device lain. Path file di dalam folder aplikasi
disimpan relatif, sedangkan background yang dipilih disalin ke folder
"personal_rutin_assets".
"""

import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from functools import partial
from pathlib import Path
from string import Template

from PySide6.QtCore import (QDate, QFileInfo, QLocale, QSize, Qt, QTimer, QUrl,
                            Signal)
from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QPainter,
                           QPixmap, QTextCharFormat)
from PySide6.QtWidgets import (QApplication, QCalendarWidget, QCheckBox,
                               QColorDialog, QDialog, QDialogButtonBox,
                               QFileDialog, QFileIconProvider, QFrame,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListView, QListWidget, QListWidgetItem, QMenu,
                               QMessageBox, QProgressBar, QPushButton,
                               QRadioButton, QScrollArea, QSlider, QSplitter,
                               QVBoxLayout, QWidget)

APP_NAME = "Personal Rutin"

# --------------------------------------------------------------------------
# Lokasi file (portable: di sebelah aplikasi)
# --------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

if os.access(APP_DIR, os.W_OK):
    DATA_DIR = APP_DIR
else:  # folder read-only (mis. Program Files) -> pakai folder user
    DATA_DIR = Path.home() / ".personal_rutin"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

CFG_FILE = DATA_DIR / "personal_rutin.cfg"
ASSETS_DIR = DATA_DIR / "personal_rutin_assets"
OLD_V10_FILE = Path.home() / ".personal_rutin" / "data.json"  # migrasi v1.0
ERROR_LOG = DATA_DIR / "personal_rutin_error.log"


def _excepthook(t, v, tb):
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}]\n")
            f.write("".join(traceback.format_exception(t, v, tb)) + "\n")
    except Exception:
        pass


sys.excepthook = _excepthook


def to_store(path):
    """Path di dalam folder aplikasi disimpan relatif agar portable."""
    try:
        p = Path(path).resolve()
        if p.is_relative_to(DATA_DIR.resolve()):
            return os.path.normpath(os.path.relpath(p, DATA_DIR))
    except Exception:
        pass
    return os.path.normpath(str(path))


def from_store(path):
    p = Path(path)
    return str(p if p.is_absolute() else DATA_DIR / p)


HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

DEFAULT_LAYOUT = {"v": [0.09, 0.72, 0.19],
                  "h": [0.30, 0.36, 0.34],
                  "r": [0.55, 0.45]}

DEFAULT_DATA = {
    "title": "📅  Personal Rutin",
    "night": False,
    "bg": {"type": "color", "color": "#2b6cb0", "image": ""},
    "panel_opacity": 75,
    "py_bg": "#6c5ce7",
    "show_calendar": True,
    "show_clock": True,
    "cal_scale": 100,
    "layout_locked": False,
    "layout": {},
    "reset_daily": True,
    "last_date": "",
    "tasks": [
        {"text": "Cek email", "done": False},
        {"text": "Review jadwal hari ini", "done": False},
        {"text": "Olahraga ringan", "done": False},
    ],
    "shortcuts": [],
    "pyapps": [],
    "links": [
        {"name": "Google", "url": "https://www.google.com"},
        {"name": "YouTube", "url": "https://www.youtube.com"},
    ],
}


# --------------------------------------------------------------------------
# Penyimpanan data
# --------------------------------------------------------------------------
class Store:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULT_DATA))
        self.load()

    def load(self):
        src = CFG_FILE if CFG_FILE.exists() else (
            OLD_V10_FILE if OLD_V10_FILE.exists() else None)
        if not src:
            return
        try:
            with open(src, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            bg = {**DEFAULT_DATA["bg"], **loaded.get("bg", {})}
            self.data.update(loaded)
            self.data["bg"] = bg
        except Exception:
            pass

    def save(self):
        try:
            tmp = CFG_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            tmp.replace(CFG_FILE)
        except Exception as ex:
            _excepthook(type(ex), ex, ex.__traceback__)

    def check_new_day(self):
        """True bila hari berganti dan centang direset."""
        today = datetime.now().date().isoformat()
        if self.data["last_date"] == today:
            return False
        changed = False
        if self.data["reset_daily"] and self.data["last_date"]:
            for t in self.data["tasks"]:
                if t["done"]:
                    t["done"] = False
                    changed = True
        self.data["last_date"] = today
        self.save()
        return changed


# --------------------------------------------------------------------------
# Tema
# --------------------------------------------------------------------------
QSS = Template("""
QWidget { color: $text; font-family: "Segoe UI"; font-size: 15px; }
QSplitter { background: transparent; }
QSplitter::handle { background: transparent; }
QSplitter[unlocked="true"]::handle { background: $soft; border-radius: 4px; }

QFrame#panel {
    background: $panel; border: 1px solid $border; border-radius: 14px;
}
QFrame#panelClear { background: transparent; border: none; }
QFrame#panelClear QLabel { color: $calfg; }
QLabel { background: transparent; }
QLabel#appTitle { font-size: 26px; font-weight: 700; }
QLabel#panelTitle { font-size: 20px; font-weight: 600; }
QLabel#clock { font-size: ${clock_px}px; font-weight: 300; }
QLabel#dateLbl { font-size: ${date_px}px; }
QLabel#sub { color: $sub; }

QPushButton {
    background: $field; border: 1px solid $border; border-radius: 8px;
    padding: 8px 14px;
}
QPushButton:hover { background: $hover; }
QPushButton:checked { background: $soft; border: 1px solid $accent; }
QPushButton#primary { background: $accent; color: white; border: none; }
QPushButton#primary:hover { background: $accent; }
QPushButton#danger:hover { background: #e5484d; color: white; border: none; }
QPushButton#mini {
    background: transparent; border: none; padding: 2px 10px;
    color: $calfg; font-size: 18px;
}
QPushButton#mini:hover { background: $hover; }

QLineEdit {
    background: $field; border: 1px solid $border; border-radius: 8px;
    padding: 8px;
}

QProgressBar { background: $field; border: none; border-radius: 5px; }
QProgressBar::chunk { background: #2ecc71; border-radius: 5px; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollArea#pyScroll { background: $pysec; border-radius: 12px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: $hover; border-radius: 5px; min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QFrame#taskRow {
    background: $field; border: 1px solid $border; border-radius: 12px;
}
QFrame#taskRow:hover { background: $hover; }
QFrame#taskRow[done="true"] {
    background: rgba(46,204,113,80); border: 1px solid rgba(46,204,113,170);
}
QFrame#taskRow[done="true"] QLabel#taskText { color: $sub; }
QLabel#taskText { font-size: 17px; }
QPushButton#check {
    min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
    border-radius: 15px; border: 2px solid $sub; background: transparent;
    padding: 0; font-size: 16px; font-weight: 700; color: white;
}
QPushButton#check:hover { border-color: #2ecc71; }
QPushButton#check:checked { background: #2ecc71; border: 2px solid #2ecc71; }
QPushButton#rowBtn {
    background: transparent; border: none; padding: 4px 8px;
    border-radius: 6px; font-size: 15px;
}
QPushButton#rowBtn:hover { background: $hover; }

QPushButton#pyBtn {
    background: $pybtn; color: $pyfg; border: none; border-radius: 10px;
    padding: 12px; font-size: 16px; font-weight: 600;
}
QPushButton#pyBtn:hover { background: $pyhover; }

QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 8px; border-radius: 8px; }
QListWidget::item:hover { background: $hover; }
QListWidget::item:selected { background: $soft; color: $text; }

QCalendarWidget { background: transparent; }
QCalendarWidget QWidget { background: transparent; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background: transparent; }
QCalendarWidget QToolButton {
    color: $calfg; background: transparent; border: none; border-radius: 8px;
    font-size: ${cal_px}px; font-weight: 600; padding: 6px 10px;
}
QCalendarWidget QToolButton:hover { background: $hover; }
QCalendarWidget QMenu { background: $dlg; color: $text; }
QCalendarWidget QSpinBox { background: $dlg; color: $text; border-radius: 6px; }
QCalendarWidget QAbstractItemView:enabled {
    background: transparent; alternate-background-color: transparent;
    color: $calfg; font-size: ${cal_px}px; outline: 0;
    selection-background-color: $accent; selection-color: white;
}
QCalendarWidget QAbstractItemView:disabled { color: $calsub; }

QDialog, QMessageBox, QInputDialog { background: $dlg; }
QMenu { background: $dlg; border: 1px solid $border; padding: 6px; }
QMenu::item { padding: 8px 26px; border-radius: 6px; }
QMenu::item:selected { background: $soft; }
""")


def theme_colors(d, bg_dark):
    night = d["night"]
    a = int(255 * d["panel_opacity"] / 100)
    s = d["cal_scale"] / 100
    if night:
        c = dict(text="#f2f4f8", sub="#a9b1c0", panel=f"rgba(20,24,32,{a})",
                 field="rgba(255,255,255,26)", border="rgba(255,255,255,45)",
                 hover="rgba(255,255,255,38)", accent="#4aa3ff",
                 soft="rgba(74,163,255,90)", dlg="#1b2029")
    else:
        c = dict(text="#1c2330", sub="#5d6778", panel=f"rgba(255,255,255,{a})",
                 field="rgba(0,0,0,14)", border="rgba(0,0,0,40)",
                 hover="rgba(0,0,0,22)", accent="#2d7dd2",
                 soft="rgba(45,125,210,70)", dlg="#f4f6fa")
    py = QColor(d["py_bg"])
    lum = (0.299 * py.red() + 0.587 * py.green() + 0.114 * py.blue()) / 255
    r, g, b = py.red(), py.green(), py.blue()
    c.update(
        calfg="#ffffff" if bg_dark else "#1c2330",
        calsub="rgba(255,255,255,110)" if bg_dark else "rgba(0,0,0,100)",
        clock_px=int(56 * s), date_px=int(18 * s), cal_px=int(17 * s),
        pysec=f"rgba({r},{g},{b},70)", pybtn=f"rgba({r},{g},{b},215)",
        pyhover=f"rgb({r},{g},{b})", pyfg="#ffffff" if lum < 0.6 else "#111111")
    return c


# --------------------------------------------------------------------------
# Helper peluncur
# --------------------------------------------------------------------------
def run_python(path, console=False):
    names = ["python", "py"] if console else ["pythonw", "pyw"]
    cands = []
    if not getattr(sys, "frozen", False):
        exe = "python.exe" if console else "pythonw.exe"
        cands.append(str(Path(sys.executable).with_name(exe)))
    cands += [shutil.which(n) for n in names]
    for c in cands:
        if c and os.path.exists(c):
            flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if console else 0
            subprocess.Popen([c, path], cwd=os.path.dirname(path) or None,
                             creationflags=flags)
            return
    os.startfile(path)  # cadangan: pakai asosiasi file Windows


def launch_entry(entry, parent=None, console=False):
    """Buka entri {name, path}. Return True bila path berubah (perlu disimpan)."""
    changed = False
    path = from_store(entry["path"])
    if not os.path.exists(path):
        ans = QMessageBox.question(
            parent, APP_NAME,
            f"File tidak ditemukan di perangkat ini:\n{path}\n\n"
            "Cari lokasi barunya?")
        if ans != QMessageBox.Yes:
            return False
        new, _ = QFileDialog.getOpenFileName(parent, "Cari file", "",
                                             "Semua file (*.*)")
        if not new:
            return False
        entry["path"] = to_store(new)
        path = new
        changed = True
    try:
        if Path(path).suffix.lower() in (".py", ".pyw"):
            run_python(path, console)
        elif hasattr(os, "startfile"):
            os.startfile(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
    except Exception as ex:
        QMessageBox.warning(parent, APP_NAME, f"Gagal membuka:\n{path}\n\n{ex}")
    return changed


def open_url(url):
    if "://" not in url:
        url = "https://" + url
    QDesktopServices.openUrl(QUrl(url))


def import_asset(src):
    """Salin gambar ke personal_rutin_assets agar ikut terbawa ke device lain."""
    try:
        src_p = Path(src).resolve()
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        if ASSETS_DIR.resolve() in src_p.parents:
            return to_store(src_p)
        dest = ASSETS_DIR / src_p.name
        if dest.exists():
            dest = ASSETS_DIR / f"{src_p.stem}_{datetime.now():%H%M%S}{src_p.suffix}"
        shutil.copy2(src_p, dest)
        return to_store(dest)
    except Exception:
        return to_store(src)


class Panel(QFrame):
    """Kotak dengan judul dan baris header (tombol ditambah ke kanan)."""

    def __init__(self, title, name="panel"):
        super().__init__()
        self.setObjectName(name)
        self.setMinimumSize(160, 80)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(18, 14, 18, 14)
        self.root.setSpacing(10)
        self.header = QHBoxLayout()
        self.title = QLabel(title)
        self.title.setObjectName("panelTitle")
        self.header.addWidget(self.title)
        self.header.addStretch()
        self.root.addLayout(self.header)


# --------------------------------------------------------------------------
# Kiri: kerjaan rutin (ceklis cantik, hijau transparan bila selesai)
# --------------------------------------------------------------------------
class TaskRow(QFrame):
    toggled_done = Signal(bool)
    edit_req = Signal()
    del_req = Signal()

    def __init__(self, text, done):
        super().__init__()
        self.setObjectName("taskRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 8)
        lay.setSpacing(12)

        self.check = QPushButton()
        self.check.setObjectName("check")
        self.check.setCheckable(True)
        self.check.setCursor(Qt.PointingHandCursor)
        self.check.toggled.connect(self._toggled)

        self.label = QLabel(text)
        self.label.setObjectName("taskText")
        self.label.setWordWrap(True)

        btn_edit = QPushButton("✎")
        btn_del = QPushButton("🗑")
        for b in (btn_edit, btn_del):
            b.setObjectName("rowBtn")
            b.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self.edit_req)
        btn_del.clicked.connect(self.del_req)

        lay.addWidget(self.check)
        lay.addWidget(self.label, 1)
        lay.addWidget(btn_edit)
        lay.addWidget(btn_del)

        self.check.blockSignals(True)
        self.check.setChecked(done)
        self.check.blockSignals(False)
        self.apply(done)

    def _toggled(self, done):
        self.apply(done)
        self.toggled_done.emit(done)

    def apply(self, done):
        self.check.setText("✓" if done else "")
        f = self.label.font()
        f.setStrikeOut(done)
        self.label.setFont(f)
        self.setProperty("done", done)
        for w in (self, self.label):
            w.style().unpolish(w)
            w.style().polish(w)

    def mouseDoubleClickEvent(self, e):
        self.edit_req.emit()


class TasksPanel(Panel):
    def __init__(self, store):
        super().__init__("✅  Kerjaan Rutin")
        self.store = store

        self.progress_lbl = QLabel()
        self.progress_lbl.setObjectName("sub")
        btn_reset = QPushButton("↺ Reset")
        btn_reset.clicked.connect(self.reset_checks)
        self.header.addWidget(self.progress_lbl)
        self.header.addWidget(btn_reset)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.root.addWidget(self.bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.host = QWidget()
        self.vbox = QVBoxLayout(self.host)
        self.vbox.setContentsMargins(0, 0, 4, 0)
        self.vbox.setSpacing(8)
        self.scroll.setWidget(self.host)
        self.root.addWidget(self.scroll, 1)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Tambah kerjaan rutin baru...")
        self.input.returnPressed.connect(self.add_task)
        btn_add = QPushButton("Tambah")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.add_task)
        row.addWidget(self.input, 1)
        row.addWidget(btn_add)
        self.root.addLayout(row)

        self.refresh()

    def refresh(self):
        while self.vbox.count():
            it = self.vbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, t in enumerate(self.store.data["tasks"]):
            r = TaskRow(t["text"], t["done"])
            r.toggled_done.connect(partial(self.on_toggle, i))
            r.edit_req.connect(partial(self.edit_task, i))
            r.del_req.connect(partial(self.delete_task, i))
            self.vbox.addWidget(r)
        self.vbox.addStretch(1)
        self.update_progress()

    def update_progress(self):
        tasks = self.store.data["tasks"]
        done = sum(1 for t in tasks if t["done"])
        self.progress_lbl.setText(f"{done}/{len(tasks)} selesai")
        self.bar.setMaximum(max(1, len(tasks)))
        self.bar.setValue(done)

    def on_toggle(self, i, done):
        self.store.data["tasks"][i]["done"] = done
        self.update_progress()
        self.store.save()

    def add_task(self):
        text = self.input.text().strip()
        if not text:
            return
        self.store.data["tasks"].append({"text": text, "done": False})
        self.input.clear()
        self.store.save()
        self.refresh()

    def edit_task(self, i):
        cur = self.store.data["tasks"][i]["text"]
        text, ok = QInputDialog.getText(self, "Ubah kerjaan", "Kerjaan:", text=cur)
        if ok and text.strip():
            self.store.data["tasks"][i]["text"] = text.strip()
            self.store.save()
            self.refresh()

    def delete_task(self, i):
        del self.store.data["tasks"][i]
        self.store.save()
        self.refresh()

    def reset_checks(self):
        for t in self.store.data["tasks"]:
            t["done"] = False
        self.store.save()
        self.refresh()


# --------------------------------------------------------------------------
# Tengah: jam + kalender (transparan penuh)
# --------------------------------------------------------------------------
class CalendarPanel(Panel):
    close_req = Signal()
    scale_req = Signal(int)

    def __init__(self, store):
        super().__init__("Kalender", name="panelClear")
        self.store = store
        self._marked = None
        self.title.hide()

        for text, tip, slot in (("－", "Perkecil", lambda: self.scale_req.emit(-10)),
                                ("＋", "Perbesar", lambda: self.scale_req.emit(10)),
                                ("✕", "Tutup kalender", self.close_req.emit)):
            b = QPushButton(text)
            b.setObjectName("mini")
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            self.header.addWidget(b)

        self.clock = QLabel("00:00:00")
        self.clock.setObjectName("clock")
        self.clock.setAlignment(Qt.AlignCenter)
        self.date_lbl = QLabel("")
        self.date_lbl.setObjectName("dateLbl")
        self.date_lbl.setAlignment(Qt.AlignCenter)
        self.root.addWidget(self.clock)
        self.root.addWidget(self.date_lbl)

        self.cal = QCalendarWidget()
        self.cal.setLocale(QLocale(QLocale.Indonesian, QLocale.Indonesia))
        self.cal.setFirstDayOfWeek(Qt.Monday)
        self.cal.setGridVisible(False)
        self.cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.cal.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.root.addWidget(self.cal, 1)

        self.tick()

    def set_clock_visible(self, vis):
        self.clock.setVisible(vis)
        self.date_lbl.setVisible(vis)

    def apply_formats(self, fg, accent):
        hdr = QTextCharFormat()
        hdr.setForeground(QColor(fg))
        hdr.setBackground(QBrush(Qt.transparent))
        hdr.setFontWeight(QFont.DemiBold)
        self.cal.setHeaderTextFormat(hdr)

        normal = QTextCharFormat()
        normal.setForeground(QColor(fg))
        red = QTextCharFormat()
        red.setForeground(QColor("#ff6b6b"))
        for d in (Qt.Monday, Qt.Tuesday, Qt.Wednesday, Qt.Thursday, Qt.Friday):
            self.cal.setWeekdayTextFormat(d, normal)
        self.cal.setWeekdayTextFormat(Qt.Saturday, red)
        self.cal.setWeekdayTextFormat(Qt.Sunday, red)
        self.mark_today(accent)

    def mark_today(self, accent):
        if self._marked is not None:
            self.cal.setDateTextFormat(self._marked, QTextCharFormat())
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(accent))
        fmt.setForeground(QColor("white"))
        fmt.setFontWeight(QFont.Bold)
        self._marked = QDate.currentDate()
        self.cal.setDateTextFormat(self._marked, fmt)

    def tick(self):
        now = datetime.now()
        self.clock.setText(now.strftime("%H:%M:%S"))
        self.date_lbl.setText(
            f"{HARI[now.weekday()]}, {now.day} {BULAN[now.month - 1]} {now.year}")


# --------------------------------------------------------------------------
# Kanan atas: aplikasi (ikon exe, py, pyw, lnk, dll)
# --------------------------------------------------------------------------
class AppsPanel(Panel):
    def __init__(self, store):
        super().__init__("💻  Aplikasi")
        self.store = store
        self.icons = QFileIconProvider()
        self.setAcceptDrops(True)

        btn_add = QPushButton("＋ Tambah")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.pick_app)
        self.header.addWidget(btn_add)

        self.list = QListWidget()
        self.list.setViewMode(QListView.IconMode)
        self.list.setIconSize(QSize(48, 48))
        self.list.setGridSize(QSize(120, 100))
        self.list.setResizeMode(QListView.Adjust)
        self.list.setMovement(QListView.Static)
        self.list.setWordWrap(True)
        self.list.setUniformItemSizes(True)
        self.list.viewport().setAcceptDrops(False)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.menu)
        self.list.itemClicked.connect(self.launch)
        self.root.addWidget(self.list, 1)

        self.refresh()

    def refresh(self):
        self.list.clear()
        for s in self.store.data["shortcuts"]:
            path = from_store(s["path"])
            it = QListWidgetItem(self.icons.icon(QFileInfo(path)), s["name"])
            it.setToolTip(path)
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            self.list.addItem(it)

    def pick_app(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih aplikasi / file", "",
            "Aplikasi (*.exe *.lnk *.bat *.cmd *.py *.pyw);;Semua file (*.*)")
        for p in paths:
            self.add_path(p)

    def add_path(self, path):
        name = QFileInfo(path).completeBaseName() or path
        self.store.data["shortcuts"].append({"name": name, "path": to_store(path)})
        self.store.save()
        self.refresh()

    def launch(self, item):
        entry = self.store.data["shortcuts"][self.list.row(item)]
        if launch_entry(entry, self):
            self.store.save()
            self.refresh()

    def menu(self, pos):
        item = self.list.itemAt(pos)
        if not item:
            return
        row = self.list.row(item)
        m = QMenu(self)
        a_ren = m.addAction("Ubah nama")
        a_del = m.addAction("Hapus")
        act = m.exec(self.list.viewport().mapToGlobal(pos))
        if act == a_ren:
            cur = self.store.data["shortcuts"][row]["name"]
            text, ok = QInputDialog.getText(self, "Ubah nama", "Nama baru:", text=cur)
            if ok and text.strip():
                self.store.data["shortcuts"][row]["name"] = text.strip()
        elif act == a_del:
            del self.store.data["shortcuts"][row]
        else:
            return
        self.store.save()
        self.refresh()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.add_path(u.toLocalFile())


# --------------------------------------------------------------------------
# Kanan bawah: Aplikasi Python (hanya nama, lebar tombol 80%)
# --------------------------------------------------------------------------
class PyAppsPanel(Panel):
    def __init__(self, store):
        super().__init__("🐍  Aplikasi Python")
        self.store = store
        self.setAcceptDrops(True)

        btn_add = QPushButton("＋ Tambah")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.pick_app)
        self.header.addWidget(btn_add)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("pyScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.host = QWidget()
        self.vbox = QVBoxLayout(self.host)
        self.vbox.setContentsMargins(8, 10, 8, 10)
        self.vbox.setSpacing(10)
        self.scroll.setWidget(self.host)
        self.root.addWidget(self.scroll, 1)

        self.refresh()

    def refresh(self):
        while self.vbox.count():
            it = self.vbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, a in enumerate(self.store.data["pyapps"]):
            wrap = QWidget()
            h = QHBoxLayout(wrap)
            h.setContentsMargins(0, 0, 0, 0)
            btn = QPushButton(a["name"])
            btn.setObjectName("pyBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(from_store(a["path"]))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.clicked.connect(partial(self.launch, i, False))
            btn.customContextMenuRequested.connect(partial(self.menu, i, btn))
            h.addStretch(1)        # 10% | 80% | 10%
            h.addWidget(btn, 8)
            h.addStretch(1)
            self.vbox.addWidget(wrap)
        self.vbox.addStretch(1)

    def pick_app(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Pilih aplikasi Python", "",
            "Python (*.py *.pyw);;Semua file (*.*)")
        for p in paths:
            self.add_path(p)

    def add_path(self, path):
        stem = QFileInfo(path).completeBaseName() or path
        name = stem.replace("_", " ").replace("-", " ").title()
        self.store.data["pyapps"].append({"name": name, "path": to_store(path)})
        self.store.save()
        self.refresh()

    def launch(self, i, console, *_):
        entry = self.store.data["pyapps"][i]
        if launch_entry(entry, self, console):
            self.store.save()
            self.refresh()

    def menu(self, i, btn, pos):
        m = QMenu(self)
        a_run = m.addAction("Jalankan")
        a_con = m.addAction("Jalankan dengan console")
        m.addSeparator()
        a_ren = m.addAction("Ubah nama")
        a_del = m.addAction("Hapus")
        act = m.exec(btn.mapToGlobal(pos))
        if act == a_run:
            self.launch(i, False)
            return
        if act == a_con:
            self.launch(i, True)
            return
        if act == a_ren:
            cur = self.store.data["pyapps"][i]["name"]
            text, ok = QInputDialog.getText(self, "Ubah nama", "Nama baru:", text=cur)
            if ok and text.strip():
                self.store.data["pyapps"][i]["name"] = text.strip()
        elif act == a_del:
            del self.store.data["pyapps"][i]
        else:
            return
        self.store.save()
        self.refresh()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.isLocalFile():
                self.add_path(u.toLocalFile())


# --------------------------------------------------------------------------
# Bawah: link favorit
# --------------------------------------------------------------------------
class LinksPanel(Panel):
    def __init__(self, store):
        super().__init__("🔗  Link Sering Dibuka")
        self.store = store

        btn_add = QPushButton("＋ Tambah Link")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self.add_link)
        self.header.addWidget(btn_add)

        self.list = QListWidget()
        self.list.setFlow(QListView.LeftToRight)
        self.list.setWrapping(True)
        self.list.setSpacing(6)
        self.list.setMovement(QListView.Static)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self.menu)
        self.list.itemClicked.connect(self.launch)
        self.root.addWidget(self.list, 1)

        self.refresh()

    def refresh(self):
        self.list.clear()
        for l in self.store.data["links"]:
            it = QListWidgetItem("🌐  " + l["name"])
            it.setToolTip(l["url"])
            self.list.addItem(it)

    def ask(self, name="", url=""):
        name, ok = QInputDialog.getText(self, "Link", "Nama link:", text=name)
        if not ok or not name.strip():
            return None
        url, ok = QInputDialog.getText(self, "Link", "Alamat (URL):", text=url)
        if not ok or not url.strip():
            return None
        return {"name": name.strip(), "url": url.strip()}

    def add_link(self):
        link = self.ask()
        if link:
            self.store.data["links"].append(link)
            self.store.save()
            self.refresh()

    def launch(self, item):
        open_url(self.store.data["links"][self.list.row(item)]["url"])

    def menu(self, pos):
        item = self.list.itemAt(pos)
        if not item:
            return
        row = self.list.row(item)
        m = QMenu(self)
        a_edit = m.addAction("Ubah")
        a_del = m.addAction("Hapus")
        act = m.exec(self.list.viewport().mapToGlobal(pos))
        if act == a_edit:
            cur = self.store.data["links"][row]
            link = self.ask(cur["name"], cur["url"])
            if not link:
                return
            self.store.data["links"][row] = link
        elif act == a_del:
            del self.store.data["links"][row]
        else:
            return
        self.store.save()
        self.refresh()


# --------------------------------------------------------------------------
# Dialog pengaturan
# --------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.reset_layout = False
        self.setWindowTitle("Pengaturan")
        self.setMinimumWidth(500)
        d = store.data

        self.color = d["bg"]["color"]
        self.image = from_store(d["bg"]["image"]) if d["bg"]["image"] else ""
        self.py_color = d["py_bg"]

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        def heading(text):
            l = QLabel(text)
            l.setObjectName("panelTitle")
            return l

        # Judul
        lay.addWidget(heading("Judul Aplikasi"))
        self.ed_title = QLineEdit(d["title"])
        self.ed_title.setPlaceholderText("Contoh: 📅  Personal Rutin")
        lay.addWidget(self.ed_title)

        # Background
        lay.addWidget(heading("Background"))
        self.r_color = QRadioButton("Warna polos")
        self.r_image = QRadioButton("Gambar")
        (self.r_image if d["bg"]["type"] == "image" else self.r_color).setChecked(True)

        row_c = QHBoxLayout()
        self.swatch = QLabel()
        self.swatch.setFixedSize(36, 24)
        btn_color = QPushButton("Pilih warna...")
        btn_color.clicked.connect(lambda: self.pick_color("color"))
        row_c.addWidget(self.r_color)
        row_c.addStretch()
        row_c.addWidget(self.swatch)
        row_c.addWidget(btn_color)
        lay.addLayout(row_c)

        row_i = QHBoxLayout()
        btn_img = QPushButton("Pilih gambar...")
        btn_img.clicked.connect(self.pick_image)
        row_i.addWidget(self.r_image)
        row_i.addStretch()
        row_i.addWidget(btn_img)
        lay.addLayout(row_i)
        self.img_lbl = QLabel()
        self.img_lbl.setObjectName("sub")
        self.img_lbl.setWordWrap(True)
        lay.addWidget(self.img_lbl)

        lay.addWidget(QLabel("Kepekatan kotak panel:"))
        self.slider = self._slider(20, 100, d["panel_opacity"], "%")
        lay.addLayout(self.slider[0])

        # Aplikasi Python
        lay.addWidget(heading("Aplikasi Python"))
        row_p = QHBoxLayout()
        self.py_swatch = QLabel()
        self.py_swatch.setFixedSize(36, 24)
        btn_py = QPushButton("Pilih warna...")
        btn_py.clicked.connect(lambda: self.pick_color("py_color"))
        row_p.addWidget(QLabel("Warna background:"))
        row_p.addStretch()
        row_p.addWidget(self.py_swatch)
        row_p.addWidget(btn_py)
        lay.addLayout(row_p)

        # Kalender
        lay.addWidget(heading("Kalender"))
        self.chk_cal = QCheckBox("Tampilkan kalender")
        self.chk_cal.setChecked(d["show_calendar"])
        self.chk_clock = QCheckBox("Tampilkan jam digital & tanggal")
        self.chk_clock.setChecked(d["show_clock"])
        lay.addWidget(self.chk_cal)
        lay.addWidget(self.chk_clock)
        lay.addWidget(QLabel("Ukuran kalender:"))
        self.scale = self._slider(60, 160, d["cal_scale"], "%")
        lay.addLayout(self.scale[0])

        # Lainnya
        lay.addWidget(heading("Lainnya"))
        self.chk_reset = QCheckBox("Reset centang kerjaan rutin setiap hari baru")
        self.chk_reset.setChecked(d["reset_daily"])
        lay.addWidget(self.chk_reset)
        self.btn_layout = QPushButton("Kembalikan tata letak ke bawaan")
        self.btn_layout.clicked.connect(self.mark_reset_layout)
        lay.addWidget(self.btn_layout)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self.update_preview()

    def _slider(self, lo, hi, val, suffix):
        row = QHBoxLayout()
        s = QSlider(Qt.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        lbl = QLabel(f"{val}{suffix}")
        s.valueChanged.connect(lambda v: lbl.setText(f"{v}{suffix}"))
        row.addWidget(s, 1)
        row.addWidget(lbl)
        return row, s

    def mark_reset_layout(self):
        self.reset_layout = True
        self.btn_layout.setText("✓ Tata letak akan dikembalikan saat OK ditekan")

    def update_preview(self):
        style = "background: {}; border: 1px solid #888; border-radius: 5px;"
        self.swatch.setStyleSheet(style.format(self.color))
        self.py_swatch.setStyleSheet(style.format(self.py_color))
        self.img_lbl.setText(self.image or "(belum ada gambar dipilih)")

    def pick_color(self, attr):
        c = QColorDialog.getColor(QColor(getattr(self, attr)), self, "Pilih warna")
        if c.isValid():
            setattr(self, attr, c.name())
            if attr == "color":
                self.r_color.setChecked(True)
            self.update_preview()

    def pick_image(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Pilih gambar background", "",
            "Gambar (*.png *.jpg *.jpeg *.bmp *.webp)")
        if p:
            self.image = p
            self.r_image.setChecked(True)
            self.update_preview()

    def apply(self):
        d = self.store.data
        d["title"] = self.ed_title.text().strip() or "Personal Rutin"
        use_image = self.r_image.isChecked() and bool(self.image)
        d["bg"] = {"type": "image" if use_image else "color",
                   "color": self.color,
                   "image": import_asset(self.image) if self.image else ""}
        d["panel_opacity"] = self.slider[1].value()
        d["py_bg"] = self.py_color
        d["show_calendar"] = self.chk_cal.isChecked()
        d["show_clock"] = self.chk_clock.isChecked()
        d["cal_scale"] = self.scale[1].value()
        d["reset_daily"] = self.chk_reset.isChecked()
        self.store.save()


# --------------------------------------------------------------------------
# Background
# --------------------------------------------------------------------------
class BgWidget(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.night = False
        self.lum = 0.3
        self._pix = None
        self._cache = None
        self.reload()

    def reload(self):
        bg = self.store.data["bg"]
        self._pix = None
        if bg["type"] == "image" and bg["image"]:
            path = from_store(bg["image"])
            if os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    self._pix = pm
        # Tingkat terang background -> menentukan warna teks kalender
        if self._pix:
            img = self._pix.scaled(8, 8, Qt.IgnoreAspectRatio,
                                   Qt.SmoothTransformation).toImage()
            tot = 0.0
            for x in range(8):
                for y in range(8):
                    c = img.pixelColor(x, y)
                    tot += 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
            self.lum = tot / 64 / 255
        else:
            c = QColor(bg["color"])
            self.lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255
        self._cache = None
        self.update()

    def is_dark(self):
        return self.night or self.lum < 0.55

    def resizeEvent(self, e):
        self._cache = None
        super().resizeEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        if self._pix:
            if self._cache is None:
                s = self._pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding,
                                     Qt.SmoothTransformation)
                x = (s.width() - self.width()) // 2
                y = (s.height() - self.height()) // 2
                self._cache = s.copy(x, y, self.width(), self.height())
            p.drawPixmap(0, 0, self._cache)
        else:
            p.fillRect(self.rect(), QColor(self.store.data["bg"]["color"]))
        if self.night:
            p.fillRect(self.rect(), QColor(0, 0, 0, 120))


# --------------------------------------------------------------------------
# Jendela utama
# --------------------------------------------------------------------------
class MainWindow(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
        # Tanpa title bar, tapi TIDAK menutupi taskbar (ukuran = area kerja layar)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowTitle(APP_NAME)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(400)
        self.save_timer.timeout.connect(self.save_layout)

        self.bg = BgWidget(store)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.bg)
        main = QVBoxLayout(self.bg)
        main.setContentsMargins(20, 16, 20, 16)

        # --- Top bar
        self.top = QFrame()
        self.top.setObjectName("panel")
        self.top.setMinimumHeight(58)
        tl = QHBoxLayout(self.top)
        tl.setContentsMargins(20, 6, 14, 6)
        self.title_lbl = QLabel(store.data["title"])
        self.title_lbl.setObjectName("appTitle")
        tl.addWidget(self.title_lbl)
        tl.addStretch()

        self.btn_cal = QPushButton("📅  Kalender")
        self.btn_cal.setCheckable(True)
        self.btn_cal.clicked.connect(lambda: self.set_calendar_visible(
            not self.store.data["show_calendar"]))
        self.btn_lock = QPushButton()
        self.btn_lock.setCheckable(True)
        self.btn_lock.clicked.connect(self.toggle_lock)
        self.btn_settings = QPushButton("⚙  Pengaturan")
        self.btn_settings.clicked.connect(self.open_settings)
        self.btn_night = QPushButton("🌙  Night Mode")
        self.btn_night.clicked.connect(self.toggle_night)
        self.btn_close = QPushButton("✕  Tutup")
        self.btn_close.setObjectName("danger")
        self.btn_close.clicked.connect(self.close)
        for b in (self.btn_cal, self.btn_lock, self.btn_settings,
                  self.btn_night, self.btn_close):
            b.setCursor(Qt.PointingHandCursor)
            tl.addWidget(b)

        # --- Panel
        self.tasks = TasksPanel(store)
        self.calendar = CalendarPanel(store)
        self.apps = AppsPanel(store)
        self.pyapps = PyAppsPanel(store)
        self.links = LinksPanel(store)
        self.calendar.close_req.connect(lambda: self.set_calendar_visible(False))
        self.calendar.scale_req.connect(self.change_scale)

        # --- Splitter (geser pakai mouse, bisa dikunci)
        self.sr = self._splitter(Qt.Vertical)
        self.sr.addWidget(self.apps)
        self.sr.addWidget(self.pyapps)
        self.sh = self._splitter(Qt.Horizontal)
        self.sh.addWidget(self.tasks)
        self.sh.addWidget(self.calendar)
        self.sh.addWidget(self.sr)
        self.sv = self._splitter(Qt.Vertical)
        self.sv.addWidget(self.top)
        self.sv.addWidget(self.sh)
        self.sv.addWidget(self.links)
        main.addWidget(self.sv)

        self.store.check_new_day()
        self.tasks.refresh()
        self.calendar.setVisible(store.data["show_calendar"])
        self.btn_cal.setChecked(store.data["show_calendar"])
        self.apply_theme()
        self.apply_lock()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(1000)

        scr = QApplication.primaryScreen()
        if scr:
            scr.availableGeometryChanged.connect(lambda *_: self.fit_screen())

    # ----- layar & layout
    def _splitter(self, orient):
        sp = QSplitter(orient)
        sp.setHandleWidth(12)
        sp.setChildrenCollapsible(False)
        sp.splitterMoved.connect(lambda *_: self.save_timer.start())
        return sp

    def fit_screen(self):
        scr = self.screen() or QApplication.primaryScreen()
        self.setGeometry(scr.availableGeometry())

    def start(self):
        self.fit_screen()
        self.show()
        QTimer.singleShot(50, self.fit_screen)
        QTimer.singleShot(100, self.apply_layout)

    def _splitters(self):
        return (("v", self.sv), ("h", self.sh), ("r", self.sr))

    def save_layout(self):
        lay = self.store.data.setdefault("layout", {})
        for key, sp in self._splitters():
            if key == "h" and not self.store.data["show_calendar"]:
                continue
            sizes = sp.sizes()
            total = sum(sizes)
            if total > 0 and all(s > 0 for s in sizes):
                lay[key] = [round(s / total, 4) for s in sizes]
        self.store.save()

    def apply_layout(self, reset=False):
        if reset:
            self.store.data["layout"] = {}
        lay = self.store.data.get("layout", {})
        for key, sp in self._splitters():
            if key == "h" and not self.store.data["show_calendar"]:
                continue
            fr = lay.get(key)
            if not (isinstance(fr, list) and len(fr) == sp.count()):
                fr = DEFAULT_LAYOUT[key]
            total = sp.height() if sp.orientation() == Qt.Vertical else sp.width()
            if total > 0:
                sp.setSizes([max(1, int(f * total)) for f in fr])

    def apply_lock(self):
        locked = self.store.data["layout_locked"]
        for _, sp in self._splitters():
            sp.setProperty("unlocked", not locked)
            sp.style().unpolish(sp)
            sp.style().polish(sp)
            cursor = Qt.SplitVCursor if sp.orientation() == Qt.Vertical else Qt.SplitHCursor
            for i in range(1, sp.count()):
                h = sp.handle(i)
                h.setEnabled(not locked)
                h.setCursor(Qt.ArrowCursor if locked else cursor)
        self.btn_lock.setChecked(not locked)
        self.btn_lock.setText("🔒  Tata Letak Terkunci" if locked
                              else "🔓  Atur Tata Letak")

    def toggle_lock(self):
        self.store.data["layout_locked"] = not self.store.data["layout_locked"]
        self.store.save()
        self.apply_lock()

    # ----- kalender
    def set_calendar_visible(self, vis):
        self.store.data["show_calendar"] = vis
        self.calendar.setVisible(vis)
        self.btn_cal.setChecked(vis)
        self.store.save()
        if vis:
            QTimer.singleShot(0, self.apply_layout)
            QTimer.singleShot(0, self.apply_lock)

    def change_scale(self, delta):
        s = self.store.data["cal_scale"] + delta
        self.store.data["cal_scale"] = max(60, min(160, s))
        self.store.save()
        self.apply_theme()

    # ----- tema & pengaturan
    def on_tick(self):
        self.calendar.tick()
        if self.store.check_new_day():
            self.tasks.refresh()
        if self.calendar._marked != QDate.currentDate():
            self.apply_theme()

    def apply_theme(self):
        d = self.store.data
        self.bg.night = d["night"]
        self.bg.reload()
        colors = theme_colors(d, self.bg.is_dark())
        QApplication.instance().setStyleSheet(QSS.substitute(colors))
        self.btn_night.setText("☀  Mode Terang" if d["night"] else "🌙  Night Mode")
        self.calendar.set_clock_visible(d["show_clock"])
        self.calendar.apply_formats(colors["calfg"], colors["accent"])

    def toggle_night(self):
        self.store.data["night"] = not self.store.data["night"]
        self.store.save()
        self.apply_theme()

    def open_settings(self):
        dlg = SettingsDialog(self.store, self)
        if dlg.exec() != QDialog.Accepted:
            return
        dlg.apply()
        d = self.store.data
        self.title_lbl.setText(d["title"])
        self.calendar.setVisible(d["show_calendar"])
        self.btn_cal.setChecked(d["show_calendar"])
        self.apply_theme()
        if dlg.reset_layout:
            self.apply_layout(reset=True)
            self.store.save()
        elif d["show_calendar"]:
            QTimer.singleShot(0, self.apply_layout)
        QTimer.singleShot(0, self.apply_lock)

    def closeEvent(self, e):
        self.save_layout()
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow(Store())
    win.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
