import ctypes
from ctypes import wintypes
import tkinter as tk
from center_window import safe_grab

def get_work_area():
    rect = wintypes.RECT()
    SPI_GETWORKAREA = 0x0030
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


def center_window_avoid_taskbar(root, width, height):
    """Centre une fenêtre Tk sans que le bas soit caché par la barre des tâches.

    Important: appeler cette fonction après construction de l'UI (ou la relancer via after)
    car la taille requise peut évoluer après le chargement des polices/thèmes.
    """
    margin = 10
    root.update_idletasks()  # force Tk à connaître les dimensions réelles

    try:
        left, top, right, bottom = get_work_area()
        work_w = max(1, right - left)
        work_h = max(1, bottom - top)
    except Exception:
        left, top = 0, 0
        work_w = root.winfo_screenwidth()
        work_h = root.winfo_screenheight()

    req_w = max(int(width), int(root.winfo_reqwidth()))
    req_h = max(int(height), int(root.winfo_reqheight()))

    w = min(req_w, max(200, work_w - 2 * margin))
    h = min(req_h, max(200, work_h - 2 * margin))

    x = left + (work_w - w) // 2
    y = top + (work_h - h) // 2
    x = max(left + margin, int(x))
    y = max(top + margin, int(y))
    if y + h > top + work_h - margin:
        y = int(top + work_h - h - margin)

    root.geometry(f"{int(w)}x{int(h)}+{int(x)}+{int(y)}")
    root.update_idletasks()

import importlib
import os
import sys

import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog, font as tkfont

Image = None
ImageTk = None
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)  # DPI_AWARENESS_SYSTEM_AWARE
except Exception:
    pass
try:
    Image = importlib.import_module("PIL.Image")
    ImageTk = importlib.import_module("PIL.ImageTk")
except ImportError:
    Image = None
    ImageTk = None

from db import init_db, get_conn
from admin import (
    admin_exists, set_admin_password_plain, check_admin_password_plain,
    store_active_class, load_active_class
)
from tooltip import ToolTip
from i18n import gettext_ as _, get_language
from services.archive_service import (
    list_archives,
    create_archive,
    restore_archive,
)
def get_runtime_home() -> Path:
    """Return the directory that stores writable runtime assets (DB, archives)."""

    if getattr(sys, "frozen", False):
        try:
            return Path(sys.executable).resolve().parent
        except Exception:
            return Path.cwd()
    return Path(__file__).resolve().parent

# استيراد mixins
from tabs.classes_tab import ClassesTabMixin
from tabs.students_tab import StudentsTabMixin
from tabs.attendance_tab import AttendanceTabMixin
from tabs.tests_tab import TestsTabMixin
from tabs.final_tab import FinalTabMixin
from tabs.archive_tab import ArchiveTabMixin
from tabs.session_type_tab import SessionTypeMixin
from tabs.excusedAbsence_tab import ExcusedAbsenceTabMixin
from tabs.exclusion_tab import ExclusionManagerMixin


def install_bundle_fonts(tk_root: tk.Misc, *, set_default_family: str | None = "Tajawal") -> int:
    """Register bundled fonts (assets/fonts) with the given Tk interpreter."""

    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    fonts_dir = base_dir / "assets" / "fonts"
    if not fonts_dir.exists():
        return 0

    registered = 0
    for font_file in fonts_dir.glob("*.*"):
        if font_file.suffix.lower() not in {".ttf", ".otf"}:
            continue
        font_path = font_file.resolve()

        loaded = False
        try:
            tk_root.tk.call("font", "addfont", str(font_path))
            loaded = True
        except tk.TclError:
            if os.name == "nt":
                try:
                    FR_PRIVATE = 0x10
                    added = ctypes.windll.gdi32.AddFontResourceExW(str(font_path), FR_PRIVATE, 0)
                    loaded = added > 0
                except Exception:
                    loaded = False
        if loaded:
            registered += 1

    if registered and set_default_family:
        try:
            default_font = tkfont.nametofont("TkDefaultFont")
            default_font.configure(family=set_default_family)
        except tk.TclError:
            pass

    return registered


class AttendanceApp(ClassesTabMixin,
                    StudentsTabMixin,
                    AttendanceTabMixin,
                    TestsTabMixin,
                    FinalTabMixin,
                    ArchiveTabMixin,
                    SessionTypeMixin,
                    ExcusedAbsenceTabMixin,
                    ExclusionManagerMixin):
    FONT_SCALE_CHOICES = [
        
        ("100", _("(100%)"), 1.0),
        ("125", _("(125%)"), 1.25),
        ("150", _("(150%)"), 1.5),
    ]

    _SCALABLE_FONTS = (
        "TkDefaultFont",
        "TkTextFont",
        "TkFixedFont",
        "TkMenuFont",
        "TkHeadingFont",
        "TkCaptionFont",
        "TkSmallCaptionFont",
        "TkIconFont",
        "TkTooltipFont",
    )

    def __init__(self, root):
        import sys
        
        self.root = root
        self.root.minsize(600, 400)
        self.root.title(_("ميزان الطالب"))
        self.style = ttk.Style(self.root)
        self._create_themes()
        self._apply_theme("light")
        install_bundle_fonts(self.root)
        self._init_font_scaling_state()
        base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        logo_path = base_dir / "assets" / "logo.png"
        self.logo_img = None
        if Image and ImageTk:
            try:
                img = Image.open(logo_path)
                img = img.resize((80, 80), Image.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
                # --- استعملها كأيقونة للنافذة ---
                self.root.iconphoto(False, self.logo_img)
            except Exception:
                self.logo_img = None
        icon_path = base_dir / "assets" / "logo.ico"
        try:
            if icon_path.exists():
                self.root.iconbitmap(default=str(icon_path))
        except Exception:
            pass
        
        
        init_db()
        self._restore_theme_mode()

        # admin password on first run
        if not admin_exists():
            if not self.prompt_set_admin_password_first_time():
                try:
                    self.root.destroy()
                except Exception:
                    pass
                return

        # state
        self.active_class = load_active_class()
        self.scanner = None
        self.scanned_preview = []
        self.current_token = None

        # UI notebook (بدون الطلبة)
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill='both', expand=True)
        self.tab_classes = ttk.Frame(self.nb)
        self.tab_att = ttk.Frame(self.nb)
        self.tab_tests = ttk.Frame(self.nb)
        self.tab_final = ttk.Frame(self.nb)
        self.tab_archive = ttk.Frame(self.nb)
        self.tab_excused = ttk.Frame(self.nb)

        self.nb.add(self.tab_classes, text=_("🏫 الأقسام"))
        self.nb.add(self.tab_att, text=_("📷 الحضور"))
        self.nb.add(self.tab_tests, text=_("✍️ الاستجوابات/الواجبات"))
        self.nb.add(self.tab_final, text=_("⚖️ الحساب النهائي"))
        self.nb.add(self.tab_archive, text=_("📂 الحصص السابقة"))
        self.nb.add(self.tab_excused, text=_("📑 الغياب المبرر"))
        
        # menu
        menubar = tk.Menu(root)
        root.config(menu=menubar)

        # قائمة الإدارة
        admin_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("الإدارة"), menu=admin_menu)
        admin_menu.add_command(label=_("👨‍🎓 إدارة الطلبة"), command=self.open_students_window)
        admin_menu.add_command(label=_("📚 إدارة حصص التدريس"), command=lambda: self.open_session_types_window(self.refresh_all_session_type_combos))
        # إدارة حالات الإقصاء
        admin_menu.add_separator()
        admin_menu.add_command(label=_("⚠️ إدارة حالات الإقصاء"), command=self.open_exclusion_manager)

        # قائمة الإعدادات
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("الإعدادات"), menu=settings_menu)
        settings_menu.add_command(label=_("تغيير كلمة السر الإدارية"), command=self.change_admin_password)
        settings_menu.add_command(label=_("⚖️ تعديل الأوزان"), command=self.open_weights_dialog)
        settings_menu.add_command(label=_("📦 أرشفة السداسي"), command=self.archive_semester)
        settings_menu.add_separator()
        # --- Menu de langue ---
        from i18n import available_languages
        lang_menu = tk.Menu(settings_menu, tearoff=0)
        import os, sys
        def _set_lang(lang_code):
            # Sauvegarde la langue dans lang.cfg puis relance l'app
            lang_cfg = os.path.join(os.path.dirname(__file__), "i18n", "lang.cfg")
            try:
                with open(lang_cfg, "w", encoding="utf-8") as f:
                    f.write(lang_code + "\n")
            except Exception:
                pass
            os.execl(sys.executable, sys.executable, *sys.argv)
        langs = available_languages()
        lang_labels = {"ar": "العربية", "en": "English"}
        for code in langs:
            label = lang_labels.get(code, code)
            lang_menu.add_command(label=label, command=lambda c=code: _set_lang(c))
        settings_menu.add_cascade(label=_("🌐 تغيير اللغة"), menu=lang_menu)
        # ---
        self._init_font_menu(settings_menu)
        settings_menu.add_command(label=_("🌙 تفعيل الوضع الليلي"), command=self.toggle_theme)
        theme_index = settings_menu.index("end")
        settings_menu.add_command(label=_("❔ تعليمات البرنامج"), command=self.open_help_window)
        self._theme_menu = settings_menu
        self._theme_menu_index = theme_index

        # status bar
        self.status_var = tk.StringVar(value="")
        self.status_container = ttk.Frame(root)
        self.status_container.pack(side='bottom', fill='x')
        self.statusbar = ttk.Label(
            self.status_container,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor='w'
        )
        self.statusbar.pack(side='right', fill='x', expand=True)

        # بناء التبويبات
        self.build_classes_tab()
        self.build_att_tab()
        self.build_tests_tab()
        self.build_final_tab()
        self.build_archive_tab()
        self.build_excused_tab()
        self._create_theme_toggle_button()
        self._apply_theme(getattr(self, "theme_mode", "light"))

        # Centre la fenêtre après construction complète (évite la barre des tâches au 1er lancement)
        try:
            self.root.after(0, lambda: center_window_avoid_taskbar(self.root, 1300, 580))
            self.root.after(250, lambda: center_window_avoid_taskbar(self.root, 1300, 580))
        except Exception:
            try:
                center_window_avoid_taskbar(self.root, 1300, 580)
            except Exception:
                pass

    def _create_themes(self):
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        light_palette = {
            "background": "#f5f7fb",
            "foreground": "#1b1f2a",
            "accent": "#2f6fed",
            "accent_hover": "#224fba",
            "border": "#cdd7f5",
            "input_bg": "#ffffff"
        }

        dark_palette = {
            "background": "#0f141f",
            "foreground": "#f1f3ff",
            "accent": "#5186ff",
            "accent_hover": "#3d6bd6",
            "border": "#2d3958",
            "input_bg": "#1b2233"
        }

        try:
            self.style.theme_use("clam")
            base_theme = "clam"
        except tk.TclError:
            base_theme = self.style.theme_use()

        palettes = {
            "light": light_palette,
            "dark": dark_palette
        }
        self._palettes = palettes

        for mode, palette in palettes.items():
            theme_name = f"attendance_{mode}"
            settings = self._build_theme_settings(palette)
            try:
                self.style.theme_create(theme_name, parent=base_theme, settings=settings)
            except tk.TclError:
                if hasattr(self.style, "theme_settings"):
                    try:
                        self.style.theme_settings(theme_name, settings=settings)
                    except tk.TclError:
                        pass

    def _build_theme_settings(self, palette):
        accent = palette["accent"]
        accent_hover = palette["accent_hover"]
        bg = palette["background"]
        fg = palette["foreground"]
        border = palette["border"]
        input_bg = palette["input_bg"]

        return {
            "TFrame": {
                "configure": {"background": bg}
            },
            "TLabel": {
                "configure": {"background": bg, "foreground": fg}
            },
            "TNotebook": {
                "configure": {"background": bg, "tabmargins": [4, 6, 4, 0], "borderwidth": 0}
            },
            "TNotebook.Tab": {
                "configure": {
                    "padding": [14, 8],
                    "background": bg,
                    "foreground": fg
                },
                "map": {
                    "background": [
                        ("selected", accent),
                        ("active", accent_hover)
                    ],
                    "foreground": [
                        ("selected", bg),
                        ("active", bg)
                    ]
                }
            },
            "TButton": {
                "configure": {
                    "padding": [10, 6],
                    "background": accent,
                    "foreground": bg,
                    "borderwidth": 0,
                    "relief": "flat"
                },
                "map": {
                    "background": [
                        ("active", accent_hover),
                        ("disabled", border)
                    ],
                    "foreground": [
                        ("disabled", fg)
                    ]
                }
            },
            "TCombobox": {
                "configure": {
                    "padding": [8, 4],
                    "fieldbackground": input_bg,
                    "foreground": fg,
                    "background": input_bg,
                    "bordercolor": border
                }
            },
            "TEntry": {
                "configure": {
                    "fieldbackground": input_bg,
                    "foreground": fg,
                    "background": input_bg,
                    "bordercolor": border
                }
            },
            "Treeview": {
                "configure": {
                    "background": input_bg,
                    "foreground": fg,
                    "fieldbackground": input_bg,
                    "bordercolor": border
                },
                "map": {
                    "background": [("selected", accent)],
                    "foreground": [("selected", bg)]
                }
            }
        }

    def _apply_theme(self, mode):
        theme_name = "attendance_light" if mode == "light" else "attendance_dark"
        try:
            self.style.theme_use(theme_name)
        except tk.TclError:
            return

        bg_color = self.style.lookup("TFrame", "background") or "#f5f7fb"
        self.root.configure(bg=bg_color)
        if hasattr(self, "nb"):
            self.nb.configure(style="TNotebook")

        palette = getattr(self, "_palettes", {}).get(mode)
        if palette:
            try:
                self.root.tk_setPalette(
                    background=palette["background"],
                    foreground=palette["foreground"],
                    activeBackground=palette["accent"],
                    activeForeground=palette["background"],
                    highlightColor=palette["accent"],
                    selectBackground=palette["accent"],
                    selectColor=palette["background"],
                )
            except Exception:
                pass

        self.theme_mode = mode
        if hasattr(self, "theme_button"):
            self.theme_button.configure(text="🌙" if mode == "light" else "☀️")
            tooltip_text = _("تفعيل الوضع الليلي") if mode == "light" else _("تفعيل الوضع النهاري")
            if getattr(self, "theme_button_tooltip", None):
                self.theme_button_tooltip.text = tooltip_text
        if getattr(self, "_theme_menu", None) is not None:
            label = _("🌙 تفعيل الوضع الليلي") if mode == "light" else _("☀️ تفعيل الوضع النهاري")
            try:
                self._theme_menu.entryconfigure(self._theme_menu_index, label=label)
            except Exception:
                pass

    def toggle_theme(self):
        current = getattr(self, "theme_mode", "light")
        new_mode = "dark" if current == "light" else "light"
        self._apply_theme(new_mode)
        self._persist_theme_mode(new_mode)

    def _create_theme_toggle_button(self):
        try:
            parent = getattr(self, "status_container", None)
            if parent is None:
                return
            spacer = ttk.Frame(parent, width=12)
            spacer.pack(side="left")
            self.theme_button = ttk.Button(parent, text="🌙", width=3, command=self.toggle_theme)
            self.theme_button.pack(side="left", padx=4, pady=2)
            self.theme_button_tooltip = ToolTip(self.theme_button, "تفعيل الوضع الليلي")
        except Exception:
            self.theme_button = None
            self.theme_button_tooltip = None

    def _init_font_scaling_state(self):
        self._font_scale_map = {key: factor for key, _label, factor in self.FONT_SCALE_CHOICES}
        # StringVar must be attached to the root interpreter to update menu selections automatically
        self.font_scale_var = tk.StringVar(self.root, value="100")
        self._base_font_sizes: dict[str, int] = {}
        self._capture_base_font_sizes(force=True)
        stored_choice = self._load_font_scale_setting()
        if stored_choice not in self._font_scale_map:
            stored_choice = "100"
        self.font_scale_var.set(stored_choice)
        self._apply_font_scale(self._font_scale_map[stored_choice])

    def _init_font_menu(self, settings_menu: tk.Menu):
        font_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label=_("حجم الخط"), menu=font_menu)
        for key, label, _factor in self.FONT_SCALE_CHOICES:
            font_menu.add_radiobutton(
                label=label,
                variable=self.font_scale_var,
                value=key,
                command=lambda choice=key: self._on_choose_font_scale(choice)
            )
        self._font_menu = font_menu

    def _capture_base_font_sizes(self, force: bool = False):
        if getattr(self, "_base_font_sizes", None) and not force:
            return
        self._base_font_sizes = {}
        for name in self._SCALABLE_FONTS:
            try:
                font_obj = tkfont.nametofont(name)
            except tk.TclError:
                continue
            size = font_obj.cget("size")
            if not size:
                try:
                    size = font_obj.actual().get("size", 0)
                except Exception:
                    size = 0
            if size:
                self._base_font_sizes[name] = size

    def _apply_font_scale(self, factor: float):
        if not getattr(self, "_base_font_sizes", None):
            self._capture_base_font_sizes(force=True)
        for name, base_size in self._base_font_sizes.items():
            try:
                font_obj = tkfont.nametofont(name)
            except tk.TclError:
                continue
            sign = 1 if base_size >= 0 else -1
            magnitude = abs(base_size)
            new_size = max(1, int(round(magnitude * factor)))
            font_obj.configure(size=sign * new_size)
        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def _load_font_scale_setting(self) -> str | None:
        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key=? LIMIT 1", ("font_scale_pct",))
            row = cur.fetchone()
            if row is None:
                return None
            value = row["value"]
            if value is None:
                return None
            return str(value).strip()
        except Exception:
            return None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _persist_font_scale(self, choice: str):
        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("font_scale_pct", choice)
            )
            conn.commit()
        except Exception:
            pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _on_choose_font_scale(self, choice: str):
        factor = self._font_scale_map.get(choice)
        if factor is None:
            return
        self.font_scale_var.set(choice)
        self._apply_font_scale(factor)
        self._persist_font_scale(choice)
        label = next((label for key, label, _ in self.FONT_SCALE_CHOICES if key == choice), None)
        if label and hasattr(self, "set_status"):
            try:
                self.set_status(f"تم ضبط حجم الخط على {label}")
            except Exception:
                pass

    def _persist_theme_mode(self, mode):
        if mode not in ("light", "dark"):
            return
        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("theme_mode", mode)
            )
            conn.commit()
        except Exception:
            pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def _restore_theme_mode(self):
        conn = None
        saved_mode = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT value FROM settings WHERE key=? LIMIT 1",
                ("theme_mode",)
            )
            row = cur.fetchone()
            if row:
                candidate = None
                try:
                    candidate = row["value"]
                except Exception:
                    try:
                        candidate = row[0]
                    except Exception:
                        candidate = None
                if candidate in ("light", "dark"):
                    saved_mode = candidate
        except Exception:
            saved_mode = None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

        if saved_mode:
            self._apply_theme(saved_mode)


    def open_help_window(self):
        existing = getattr(self, "_help_window", None)
        if existing and tk.Toplevel.winfo_exists(existing):
            existing.lift()
            existing.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title("دليل استخدام ميزان الطالب")
        width, height = 920, 620
        win.geometry(f"{width}x{height}")
        win.minsize(820, 520)
        win.transient(self.root)
        safe_grab(win)
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        self._help_window = win

        header = ttk.Frame(win, padding=(12, 12))
        header.pack(fill="x")
        ttk.Label(header, text="(2025) دليل البرنامج — ميزان الطالب", font=("Tajawal", 18, "bold")).pack(anchor="center")
        contact_frame = ttk.Frame(header)
        contact_frame.pack(anchor="center", pady=(6, 0))
        ttk.Label(
            contact_frame,
            text=" - تطوير: رؤوف لكحل عياط ",
            font=("Segoe UI", 11)
        ).pack(side="right")
        email_label = ttk.Label(
            contact_frame,
            text="raouf@lakehal-ayat.com",
            font=("Segoe UI", 11, "underline"),
            foreground="#2f6fed",
            cursor="hand2"
        )
        email_label.pack(side="left")

        def _open_email(event=None):
            try:
                webbrowser.open("mailto:raouf@lakehal-ayat.com")
            except Exception:
                messagebox.showinfo(
                    "البريد الإلكتروني",
                    "raouf@lakehal-ayat.com"
                )

        email_label.bind("<Button-1>", _open_email)

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        overview = ttk.Frame(notebook)
        notebook.add(overview, text="⚙️ عام")
        self._add_help_text(overview, """
🔹 فكرة البرنامج:
    • "ميزان الطالب" نظام لإدارة حضور الطلبة، تسجيل الاختبارات، حساب النتائج النهائية، والأرشفة.
    • يعمل على قاعدة بيانات SQLite مدمجة، ما يسمح بحفظ البيانات محليًا وإعادة استخدامها لاحقًا.
    • يدعم العمل بالعربية ويستخدم تبويبات واضحة لتقسيم المهام حسب نوع العملية.

🔹 مكونات الواجهة الرئيسية:
    • شريط تبويبات علوي للتنقل بين المهام الأساسية.
    • شريط حالة سفلي لعرض التنبيهات المختصرة.
    • قائمة إعدادات توفر أدوات الإدارة، تغيير الثيم، وفتح هذا الدليل.

🔹 أفضل ممارسات الاستخدام:
    1. ابدأ بتعريف الأقسام وتفعيل القسم النشط.
    2. أضف الطلبة واستورد بياناتهم قبل بدء جلسات الحضور أو الاختبارات.
    3. استخدم تبويب الحضور أثناء الدروس وتابع النتائج من تبويب الاختبارات والحساب النهائي.
    4. عند نهاية السداسي، استخدم الأرشفة لحفظ نسخة كاملة والبدء من جديد.
        """)

        classes = ttk.Frame(notebook)
        notebook.add(classes, text="🏫  الأقسام")
        self._add_help_text(classes, """
يُستخدم لإدارة أقسام الدراسة:
    • عرض جميع الأقسام في جدول مع تفاصيل الطور والسنة والفوج والفصيلة.
    • إنشاء قسم جديد عبر الزر "➕ إنشاء قسم جديد".
    • حذف قسم محدد بعد إدخال كلمة السر الإدارية.
    • تفعيل قسم واحد ليكون هو القسم النشط، وهو المرجع الافتراضي لباقي التبويبات.
        """)

        students = ttk.Frame(notebook)
        notebook.add(students, text="👨‍🎓  الطلبة")
        self._add_help_text(students, """
مسؤول عن إدارة بيانات الطلبة:
    • إضافة، تعديل، أو حذف طالب من القسم النشط.
    • استيراد قائمة طلبة من ملف Excel أو إدخالهم يدويًا.
    • البحث والتصفية حسب الاسم أو الرقم الجامعي.
        """)

        attendance = ttk.Frame(notebook)
        notebook.add(attendance, text="📷  الحضور")
        self._add_help_text(attendance, """
لتسجيل حضور الطلبة أثناء الحصة:
    • التقاط الحضور باستخدام كاميرا QR أو إدخال الطلبة يدويًا.
    • تحديد نوع الحصة قبل الحفظ وربطها برمز sessionType.
    • حفظ الجلسة لتخزين السجلات في قاعدة البيانات مع إمكانية التذكير بغيابات غير محفوظة عند الإغلاق.
        """)

        tests = ttk.Frame(notebook)
        notebook.add(tests, text="✍️  الاختبارات")
        self._add_help_text(tests, """
متعلق بإدارة الاختبارات ودرجات الطلبة:
    • إنشاء اختبار جديد وربطه بالقسم ونوع الحصة.
    • تعديل أو حذف اختبار (مع مراعاة حظر التعديل بعد إدخال الدرجات).
    • تحديث درجات الطلبة من خلال الجدول أو عبر نافذة التعديل الفردي.
        """)

        final_tab = ttk.Frame(notebook)
        notebook.add(final_tab, text="⚖️  الحساب ")
        self._add_help_text(final_tab, """
حساب النقاط النهائية لكل طالب:
    • اختيار القسم ونوع الحصة لمعرفة مجموع النقاط.
    • يعتمد على أوزان الحضور والمشاركة والاختبارات والواجبات.
    • يوفر زر لتصدير النتائج إلى ملف Excel.
        """)

        excused = ttk.Frame(notebook)
        notebook.add(excused, text="📑  التبريرات")
        self._add_help_text(excused, """
لإدارة الغيابات المبررة:
    • تسجيل الغيابات مع تحديد الوزن التعويضي لكل حالة.
    • تعديل أو حذف إثبات الغياب عند الحاجة.
        """)

        archive = ttk.Frame(notebook)
        notebook.add(archive, text="📂  الأرشيف")
        self._add_help_text(archive, """
إدارة أرشيف قاعدة البيانات:
    • إنشاء نسخة احتياطية لملف attendance.db مع ختم تاريخ ووقت تلقائي.
    • تهيئة قاعدة بيانات جديدة وفارغة مباشرة بعد حفظ النسخة لبدء سداسي جديد بسهولة.
    • استعراض النسخ السابقة من داخل البرنامج واسترجاع أي نسخة بضغطة واحدة.
    • فتح مجلد الأرشيف للاحتفاظ بنسخ خارجية أو مشاركتها مع الإدارة.
        """)

        session_types = ttk.Frame(notebook)
        notebook.add(session_types, text="📚  أنواع الحصص")
        self._add_help_text(session_types, """
إدارة جداول أنواع الحصص:
    • إضافة نوع حصة جديد مع رمز المادة.
    • تعديل أو حذف الأنواع الحالية لتحديث القوائم المرتبطة في الحضور والاختبارات.
        """)

        tests_tab = ttk.Frame(notebook)
        notebook.add(tests_tab, text="🧪  الامتحانات")
        self._add_help_text(tests_tab, """
إذا وُجد تبويب إضافي للاختبارات أو التجارب، يتم استعراض نتائجه هنا حسب التصميم الحالي.
        """)

        footer = ttk.Frame(win, padding=(12, 6))
        footer.pack(fill="x")
        ttk.Button(footer, text="إغلاق", command=win.destroy).pack(side="left")
        ttk.Label(footer, text="© 2025 — فريق ميزان الطالب", font=("Segoe UI", 9)).pack(side="right")

    def _add_help_text(self, parent, text):
        frame = ttk.Frame(parent, padding=(12, 12))
        frame.pack(fill="both", expand=True)

        bg_color = self.style.lookup("TFrame", "background") or "#f9f9fb"
        fg_color = self.style.lookup("TLabel", "foreground") or "#1a1a1a"

        txt = tk.Text(
            frame,
            wrap="word",
            height=12,
            relief=tk.FLAT,
            bg=bg_color,
            fg=fg_color,
            font=("Tajawal", 13),
            padx=18,
            pady=14,
            spacing1=6,
            spacing2=2,
            spacing3=8
        )
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", text.strip())
        txt.tag_configure("rtl", justify="right")
        txt.tag_add("rtl", "1.0", "end")
        try:
            txt.tk.call("tk", "textRightToLeft", txt._w)
        except tk.TclError:
            pass
        txt.configure(state="disabled", cursor="arrow")
    
    # ---------------- نافذة الطلبة ----------------
    def open_students_window(self):
        """فتح نافذة مستقلة لإدارة الطلبة"""
        # Reuse existing window if already open
        try:
            existing = getattr(self, "_students_window", None)
            if existing is not None and existing.winfo_exists():
                try:
                    existing.deiconify()
                except Exception:
                    pass
                try:
                    existing.lift()
                    existing.focus_force()
                except Exception:
                    pass
                return
        except Exception:
            pass

        win = tk.Toplevel(self.root)
        self._students_window = win
        win.title("إدارة الطلبة")
        win.geometry("700x500")
        # Keep it above the main window, but avoid grab_set(): modal grabs can
        # freeze the UI if the grabbed window is minimized (e.g. Win+D).
        win.transient(self.root)

        # Ensure the window comes back when the main window is restored
        bind_id = None
        try:
            def _on_root_map(_event=None):
                try:
                    if not win.winfo_exists():
                        return
                except Exception:
                    return
                try:
                    if str(win.state()) == "iconic":
                        win.deiconify()
                except Exception:
                    pass
                try:
                    win.lift()
                except Exception:
                    pass

            bind_id = self.root.bind("<Map>", _on_root_map, add="+")
        except Exception:
            bind_id = None

        def _on_close():
            try:
                if bind_id:
                    self.root.unbind("<Map>", bind_id)
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _on_close)

        try:
            win.after(0, lambda: (win.lift(), win.focus_force()))
        except Exception:
            pass
        # استغلال mixin للطلبة لكن في نافذة مستقلة
        self.tab_students = ttk.Frame(win)
        self.tab_students.pack(fill='both', expand=True)
        self.build_students_tab(parent=self.tab_students)

    # ---------------- status ----------------
    def set_status(self, text, timeout=5000):
        self.status_var.set(text)
        if timeout:
            self.root.after(timeout, lambda: self.status_var.set(""))

    # ---------------- admin password ----------------
    def prompt_set_admin_password_first_time(self):
        def ask_centered(title, prompt):
            dialog_root = tk.Toplevel(self.root)
            dialog_root.withdraw()
            dialog_root.transient(self.root)
            safe_grab(dialog_root)
            dialog_root.title(title)
            dialog_root.update_idletasks()
            w, h = 360, 140
            sw = dialog_root.winfo_screenwidth()
            sh = dialog_root.winfo_screenheight()
            x = (sw // 2) - (w // 2)
            y = (sh // 2) - (h // 2)
            dialog_root.geometry(f"{w}x{h}+{x}+{y}")
            dialog_root.deiconify()
            entry_var = tk.StringVar()

            def on_ok(event=None):
                dialog_root.destroy()

            def on_cancel(event=None):
                entry_var.set("")
                dialog_root.destroy()

            frame = ttk.Frame(dialog_root, padding=12)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text=prompt, wraplength=320, justify="center").pack(pady=(0, 12))
            entry = ttk.Entry(frame, textvariable=entry_var, show='*', justify="center")
            entry.pack(fill="x")
            entry.focus_set()
            btns = ttk.Frame(frame)
            btns.pack(pady=12)
            ttk.Button(btns, text="✔ موافق", command=on_ok).pack(side="left", padx=6)
            ttk.Button(btns, text="✖ إلغاء", command=on_cancel).pack(side="right", padx=6)

            dialog_root.protocol("WM_DELETE_WINDOW", on_cancel)
            dialog_root.bind("<Return>", on_ok)
            dialog_root.bind("<Escape>", on_cancel)
            dialog_root.wait_window()
            return entry_var.get() or None

        while True:
            pwd = ask_centered("كلمة سر إدارية", "لا توجد كلمة سر إدارية. الرجاء تعيين كلمة سر جديدة:")
            if pwd is None:
                if messagebox.askyesno(
                    "الخروج",
                    "لم يتم تعيين كلمة سر إدارية. هل تريد الخروج من البرنامج؟",
                    parent=self.root
                ):
                    return False
                continue
            confirm = ask_centered("تأكيد", "أعد إدخال كلمة السر الإدارية:")
            if confirm is None:
                if messagebox.askyesno(
                    "الخروج",
                    "لم يتم تأكيد كلمة السر. هل تريد الخروج من البرنامج؟",
                    parent=self.root
                ):
                    return False
                continue
            if pwd != confirm:
                messagebox.showerror("خطأ", "كلمتا السر غير متطابقتين. حاول مرة أخرى.")
                continue
            set_admin_password_plain(pwd)
            messagebox.showinfo("تم", "تم تعيين كلمة السر الإدارية.")
            return True

    def require_admin_password(self):
        while True:
            pwd = simpledialog.askstring(_("التحقق"), _("أدخل كلمة السر الإدارية:"), show='*', parent=self.root)
            if pwd is None:
                return False
            if check_admin_password_plain(pwd):
                return True

            retry = messagebox.askretrycancel(
                _("كلمة السر غير صحيحة"),
                _("كلمة السر الإدارية غير صحيحة. هل تريد إعادة المحاولة؟"),
                parent=self.root
            )
            if not retry:
                return False

    def change_admin_password(self):
        if not self.require_admin_password():
            messagebox.showerror(_("خطأ"), _("كلمة السر غير صحيحة"))
            return
        while True:
            newp = simpledialog.askstring(_("جديد"), _("أدخل كلمة السر الجديدة:"), show='*', parent=self.root)
            if newp is None:
                return
            confirm = simpledialog.askstring(_("تأكيد"), _("أعد إدخال كلمة السر الجديدة:"), show='*', parent=self.root)
            if confirm is None:
                return
            if newp != confirm:
                messagebox.showerror(_("خطأ"), _("كلمتا السر غير متطابقتين"))
                continue
            set_admin_password_plain(newp)
            messagebox.showinfo(_("تم"), _("تم تغيير كلمة السر."))
            return

    # ---------------- أرشفة السداسي ----------------
    def archive_semester(self):
        is_rtl = (get_language() or "ar").lower().startswith("ar")
        action_side = "right" if is_rtl else "left"
        open_side = "left" if is_rtl else "right"

        base_dir = get_runtime_home()
        db_path = base_dir / "attendance.db"
        archives_dir = base_dir / "archives"
        archives_dir.mkdir(parents=True, exist_ok=True)

        win = tk.Toplevel(self.root)
        win.title(_("إدارة أرشيف ميزان الطالب"))
        win.transient(self.root)
        safe_grab(win)
        win.resizable(True, False)
        width, height = (620, 430) if is_rtl else (820, 430)
        win.geometry(f"{width}x{height}")
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        win.geometry(f"{width}x{height}+{x}+{y}")

        header = ttk.Frame(win, padding=(16, 16))
        header.pack(fill="x")
        ttk.Label(header, text=_("إدارة أرشيف ميزان الطالب"), font=("Tajawal", 18, "bold")).pack(anchor="center")
        ttk.Label(
            header,
            text=_("احفظ نسخة من قاعدة البيانات الحالية أو استرجع نسخة محفوظة سابقة."),
            font=("Segoe UI", 11),
            wraplength=max(520, width - 100),
            justify="center"
        ).pack(anchor="center", pady=(6, 0))

        actions = ttk.Frame(win, padding=(16, 8))
        actions.pack(fill="x")

        archive_btn = ttk.Button(actions, text=_("📦 إنشاء أرشيف جديد للسداسي الحالي"))
        archive_btn.pack(side=action_side, padx=6)
        restore_btn = ttk.Button(actions, text=_("⏪ استرجاع الأرشيف المحدد"))
        restore_btn.pack(side=action_side, padx=6)
        open_btn = ttk.Button(actions, text=_("📂 فتح مجلد الأرشيف"))
        open_btn.pack(side=open_side)

        list_container = ttk.Frame(win, padding=(16, 4))
        list_container.pack(fill="both", expand=True)
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        columns = ("name", "created")
        tree = ttk.Treeview(list_container, columns=columns, show="headings", height=9)
        tree.heading("name", text=_("اسم الملف"))
        tree.heading("created", text=_("تاريخ الإنشاء"))
        tree.column("name", anchor="center", width=320)
        tree.column("created", anchor="center", width=200)
        tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)

        empty_label = ttk.Label(
            list_container,
            text=_("لا توجد نسخ أرشيفية بعد."),
            foreground="#777",
            padding=(0, 12)
        )
        empty_label.grid(row=1, column=0, columnspan=2)

        info = ttk.Label(
            win,
            text=_("ملاحظة: إنشاء أرشيف جديد سيحفظ نسخة من قاعدة البيانات الحالية ثم ينشئ قاعدة فارغة تلقائيًا."),
            padding=(16, 8),
            wraplength=max(560, width - 60),
            justify="center"
        )
        info.pack(fill="x")

        archive_records: list[tuple[Path, datetime]] = []

        def refresh_list():
            nonlocal archive_records
            try:
                archive_records = list_archives(archives_dir)
            except Exception:
                archive_records = []
            tree.delete(*tree.get_children())
            if not archive_records:
                empty_label.grid()
                return
            empty_label.grid_remove()
            for idx, (path_obj, created_at) in enumerate(archive_records):
                created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
                tree.insert("", "end", iid=str(idx), values=(path_obj.name, created_str))

        def open_archives_folder():
            try:
                archives_dir.mkdir(exist_ok=True)
                if hasattr(os, "startfile"):
                    os.startfile(archives_dir)
                else:
                    messagebox.showinfo(_("المجلد"), _("المجلد متوفر في:\n{path}").format(path=archives_dir), parent=win)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر فتح مجلد الأرشيف:\n{error}").format(error=exc), parent=win)

        def perform_archive():
            if not messagebox.askyesno(
                _("تأكيد الأرشفة"),
                _("سيتم حفظ نسخة من قاعدة البيانات الحالية وإنشاء قاعدة جديدة فارغة.\nهل تريد المتابعة؟"),
                parent=win
            ):
                return
            try:
                backup_path = create_archive(db_path, archives_dir)
            except FileNotFoundError:
                messagebox.showinfo(_("لا يوجد بيانات"), _("لم يتم العثور على ملف قاعدة البيانات الحالي للأرشفة"), parent=win)
                return
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر حفظ نسخة الأرشيف:\n{error}").format(error=exc), parent=win)
                return

            self._reload_after_db_switch(restore_active=False)
            messagebox.showinfo(_("تم"), _("تم حفظ الأرشيف باسم:\n{filename}").format(filename=backup_path.name), parent=win)
            self.set_status(_("تم إنشاء أرشيف جديد وتهيئة قاعدة بيانات جديدة."))
            refresh_list()

        def restore_selected():
            if not archive_records:
                messagebox.showinfo(_("لا يوجد أرشيف"), _("لا توجد ملفات أرشيف للاسترجاع."), parent=win)
                return
            selection = tree.selection()
            if not selection:
                messagebox.showinfo(_("اختر ملفًا"), _("الرجاء اختيار ملف أرشيف من القائمة قبل الاسترجاع."), parent=win)
                return
            try:
                index = int(selection[0])
            except ValueError:
                messagebox.showerror(_("خطأ"), _("تعذر تحديد الملف المحدد."), parent=win)
                return
            backup_path, created_at = archive_records[index]
            if not backup_path.exists():
                messagebox.showerror(_("خطأ"), _("ملف الأرشيف المحدد غير موجود."), parent=win)
                refresh_list()
                return
            if not messagebox.askyesno(
                _("تأكيد الاسترجاع"),
                _("سيتم استبدال قاعدة البيانات الحالية بالملف:\n{filename}\nهل تريد المتابعة؟").format(filename=backup_path.name),
                parent=win
            ):
                return
            try:
                restore_archive(db_path, backup_path)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر استرجاع الأرشيف:\n{error}").format(error=exc), parent=win)
                return

            self._reload_after_db_switch(restore_active=True)
            messagebox.showinfo(_("تم"), _("تم استرجاع الأرشيف:\n{filename}").format(filename=backup_path.name), parent=win)
            self.set_status(_("تم استرجاع الأرشيف المحدد."))
            win.destroy()

        archive_btn.configure(command=perform_archive)
        restore_btn.configure(command=restore_selected)
        open_btn.configure(command=open_archives_folder)

        refresh_list()

    def _reload_after_db_switch(self, restore_active):
        if restore_active:
            try:
                self.active_class = load_active_class()
            except Exception:
                self.active_class = None
        else:
            try:
                store_active_class(None)
            except Exception:
                pass
            self.active_class = None

        self.current_token = None
        self.scanned_preview = []

        loaders = (
            "load_classes",
            "load_tests_tab",
            "load_final",
            "load_archive_tab",
            "load_excused_tab",
            "refresh_all_session_type_combos",
        )
        for name in loaders:
            func = getattr(self, name, None)
            if callable(func):
                try:
                    func()
                except Exception:
                    pass

        if hasattr(self, "tree_preview"):
            try:
                for child in self.tree_preview.get_children():
                    self.tree_preview.delete(child)
            except Exception:
                pass

    # ---------------- الأوزان (الحساب النهائي) ----------------
    def get_weights(self):
        """
        تُرجع قاموسًا يحوي جميع مفاتيح الأوزان مع قيم افتراضية عند النقص.
        """
        defaults = {
            "attendance_weight": 10.0,
            "quiz_weight": 5.0,
            "homework_weight": 5.0,
            "participation_weight": 5.0,
            "max_participation_points": 10.0,
            "max_quiz_points": 20.0,
            "max_homework_points": 10.0,
        }
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM weights WHERE id=1")
        row = cur.fetchone()
        conn.close()
        if row:
            w = dict(row)
            # ضمان جميع المفاتيح
            for k, v in defaults.items():
                if k not in w or w[k] is None:
                    w[k] = v
            return w
        else:
            return defaults
    def open_weights_dialog(self):
        """نافذة لتعديل الأوزان (مركزه، RTL، تحقق مباشر، Enter للحفظ، إلغاء)"""
        if not self.require_admin_password():
            return

        is_rtl = (get_language() or "ar").lower().startswith("ar")
        label_col = 1 if is_rtl else 0
        field_col = 0 if is_rtl else 1
        label_sticky = "e" if is_rtl else "w"
        entry_padx = (10, 6) if is_rtl else (6, 10)
        label_padx = (6, 10) if is_rtl else (10, 6)

        w = self.get_weights()
        win = tk.Toplevel(self.root)
        win.title(_("تعديل الأوزان"))
        win.transient(self.root)
        safe_grab(win)  # modal

        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)

        content = ttk.Frame(win, padding=10)
        content.grid(row=0, column=0, sticky="nsew")

        # --- مقاس ابتدائي (سيعاد ضبطه ديناميكيًا بعد بناء المحتوى) ---
        win.geometry("460x420")

        # إعداد شبكة بسيطة (RTL/LTR)
        content.columnconfigure(0, weight=(1 if field_col == 0 else 0))
        content.columnconfigure(1, weight=(1 if field_col == 1 else 0))

        labels = {
            "attendance_weight": _("وزن الحضور (/20)"),
            "quiz_weight": _("وزن الاستجوابات (/20)"),
            "homework_weight": _("وزن الواجبات المنزلية (/20)"),
            "participation_weight": _("وزن المشاركة (/20)")
        }
        entries = {}

        # تحقق عددي
        def validate_number(text):
            if text == "":
                return True
            try:
                float(text)
                return True
            except Exception:
                return False

        vcmd = (win.register(validate_number), "%P")

        # إنشاء الحقول
        for i, (k, lbl) in enumerate(labels.items()):
            ent_var = tk.StringVar(value=str(w.get(k, 0)))
            e = ttk.Entry(content, textvariable=ent_var, justify="center",
                        validate="key", validatecommand=vcmd)
            e.grid(row=i, column=field_col, padx=entry_padx, pady=8, sticky='we')
            ttk.Label(content, text=lbl, anchor=label_sticky).grid(
                row=i,
                column=label_col,
                padx=label_padx,
                pady=8,
                sticky=label_sticky,
            )
            entries[k] = ent_var

        # ---------------- الغياب المبرر ----------------
        row_excused = len(labels) + 1
        ttk.Label(
            content,
            text=_("تفعيل الوزن المخفض للغياب المبرر"),
            font=("Arial", 10, "bold"),
        ).grid(row=row_excused, column=0, columnspan=2, pady=(12, 5))

        self.excused_enabled = tk.BooleanVar(value=True)
        chk_col = 1 if is_rtl else 0
        combo_col = 0 if is_rtl else 1
        chk_sticky = "e" if is_rtl else "w"
        combo_sticky = "w" if is_rtl else "e"
        chk = ttk.Checkbutton(content, text=_("تفعيل"), variable=self.excused_enabled)
        chk.grid(row=row_excused+1, column=chk_col, sticky=chk_sticky, padx=10, pady=5)

        self.excused_var = tk.StringVar(value=str(w.get("excused_weight", 0.75)))
        excused_combo = ttk.Combobox(content, textvariable=self.excused_var,
                                    values=["0.25", "0.5", "0.75"],
                                    state="readonly", width=6, justify="center")
        excused_combo.grid(row=row_excused+1, column=combo_col, sticky=combo_sticky, padx=10, pady=5)

        # تمكين/تعطيل الكومبو
        def toggle_excused(*_args):
            if self.excused_enabled.get():
                excused_combo.configure(state="readonly")
            else:
                excused_combo.configure(state="disabled")
        self.excused_enabled.trace_add("write", toggle_excused)
        toggle_excused()

        # ---------------- سطر مجموع الأوزان ----------------
        sum_var = tk.StringVar(value="")
        sum_lbl = ttk.Label(
            content,
            textvariable=sum_var,
            anchor="center",
            font=("Arial", 10, "bold"),
        )
        sum_lbl.grid(row=len(labels), column=0, columnspan=2, pady=(0, 5))

        def update_sum(*_args):
            try:
                a = float(entries["attendance_weight"].get() or 0)
                q = float(entries["quiz_weight"].get() or 0)
                h = float(entries["homework_weight"].get() or 0)
                p = float(entries["participation_weight"].get() or 0)
                s = round(a + q + h + p, 2)
                sum_var.set(_("مجموع الأوزان الآن = {value} / 20").format(value=s))
                sum_lbl.configure(foreground=("green" if abs(s - 20.0) < 1e-6 else "red"))
            except Exception:
                sum_var.set(_("مجموع الأوزان: مدخلات غير صالحة"))
                sum_lbl.configure(foreground="red")

        for v in entries.values():
            v.trace_add("write", lambda *a: update_sum())
        update_sum()

        # ---------------- حفظ ----------------
        def save(event=None):
            try:
                attendance = float(entries["attendance_weight"].get() or 0)
                quiz = float(entries["quiz_weight"].get() or 0)
                homework = float(entries["homework_weight"].get() or 0)
                participation = float(entries["participation_weight"].get() or 0)
            except ValueError:
                messagebox.showerror(_("خطأ"), _("يجب إدخال أرقام صحيحة أو عشرية فقط.\nصحح القيم ثم أعد المحاولة."))
                return

            total = round(attendance + quiz + homework + participation, 2)
            if abs(total - 20.0) > 1e-6:
                messagebox.showerror(
                    _("خطأ"),
                    _("مجموع الأوزان يجب أن يساوي 20 (المجموع الحالي = {total}).\nصحح القيم ثم أعد المحاولة.").format(total=total),
                )
                return

            # الوزن المبرر
            if self.excused_enabled.get():
                excused_w = float(self.excused_var.get())
            else:
                excused_w = 1  # افتراضي

            conn = get_conn(); cur = conn.cursor()
            cur.execute("""
                UPDATE weights SET
                attendance_weight=?,
                quiz_weight=?,
                homework_weight=?,
                participation_weight=?,
                excused_weight=?
                WHERE id=1
            """, (attendance, quiz, homework, participation, excused_w))
            conn.commit(); conn.close()

            messagebox.showinfo(_("تم"), _("تم حفظ الأوزان الجديدة."))
            win.destroy()
            try:
                self.load_final()
            except Exception:
                pass

        # ---------------- أزرار داخل نفس الشبكة ----------------
        buttons_row = row_excused + 2
        ttk.Button(content, text=_("💾 حفظ الأوزان"), command=save).grid(
            row=buttons_row,
            column=field_col,
            sticky="e" if is_rtl else "w",
            padx=entry_padx,
            pady=(12, 8),
        )
        ttk.Button(content, text=_("❌ إلغاء"), command=win.destroy).grid(
            row=buttons_row,
            column=label_col,
            sticky="w" if is_rtl else "e",
            padx=label_padx,
            pady=(12, 8),
        )

        # --- ضبط المقاس النهائي بعد اكتمال كل العناصر ---
        win.update_idletasks()
        req_w = max(460, win.winfo_reqwidth() + 20)
        req_h = max(420, win.winfo_reqheight() + 20)
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        W = min(req_w, max(320, screen_w - 40))
        H = min(req_h, max(300, screen_h - 80))
        x = max(0, (screen_w // 2) - (W // 2))
        y = max(0, (screen_h // 2) - (H // 2))
        win.geometry(f"{W}x{H}+{x}+{y}")
        win.minsize(420, 360)

        win.bind("<Return>", save)
        for child in content.winfo_children():
            if isinstance(child, ttk.Entry):
                child.bind("<Return>", save)

        win.after(50, lambda: win.focus_force() or win.focus_get() or None)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
    def refresh_all_session_type_combos(self):
        try:
        # تحديث كومبو الحضور
            conn = get_conn(); cur = conn.cursor()
            cur.execute("SELECT subject_code, type FROM session_types ORDER BY subject_code, type")
            rows = cur.fetchall(); conn.close()
            values = [f"{r['subject_code']}-{r['type']}" for r in rows]
            self.session_type_combo["values"] = values
            if values and not self.session_type_var.get():
                self.session_type_combo.current(0)
        except Exception as e:
            print("refresh session_type_combo error:", e)

        # تحديث كومبو الحساب النهائي
        self._populate_final_session_types()


