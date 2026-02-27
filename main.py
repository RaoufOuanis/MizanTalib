import importlib
import tkinter as tk
from tkinter import ttk
from pathlib import Path

Image = None
ImageTk = None
try:
    Image = importlib.import_module("PIL.Image")
    ImageTk = importlib.import_module("PIL.ImageTk")
except ImportError:
    Image = None
    ImageTk = None

from db import init_db
from app import AttendanceApp, install_bundle_fonts
from i18n import install as install_i18n, gettext_ as _


class SplashScreen:
    """نافذة سبلاش أنيقة تظهر قبل تحميل التطبيق الرئيسي."""

    DURATION_MS = 2500

    def __init__(self, root, logo_path):
        self._root = root
        self._top = tk.Toplevel(root)
        self._top.withdraw()
        self._top.overrideredirect(True)
        self._top.configure(bg="#0b0f1d")
        self._top.attributes("-topmost", True)

        style = ttk.Style(self._top)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("SplashFrame.TFrame", background="#141a33")
        style.configure("SplashTitle.TLabel", background="#141a33", foreground="#f6f7fb",
                        font=("Tajawal", 22, "bold"))
        style.configure("SplashTag.TLabel", background="#141a33", foreground="#a8a3d2",
                        font=("Segoe UI", 11))
        progress_style = "Splash.Horizontal.TProgressbar"
        try:
            style.layout(progress_style, style.layout("Horizontal.TProgressbar"))
        except tk.TclError:
            pass
        style.configure(progress_style, troughcolor="#141a33", bordercolor="#141a33",
                        background="#3f7bff", lightcolor="#6895ff", darkcolor="#2a60e9", thickness=6)

        container = ttk.Frame(self._top, style="SplashFrame.TFrame", padding=(32, 28))
        container.pack(fill="both", expand=True)

        self._logo_img = None
        logo_path = Path(logo_path)
        if logo_path.exists() and Image and ImageTk:
            try:
                with Image.open(logo_path) as img:
                    img = img.resize((120, 120), Image.LANCZOS)
                    self._logo_img = ImageTk.PhotoImage(img)
            except Exception:
                self._logo_img = None

        if self._logo_img:
            ttk.Label(container, image=self._logo_img, style="SplashTitle.TLabel").pack(pady=(0, 16))

        ttk.Label(container, text=_("ميزان الطالب"), style="SplashTitle.TLabel").pack()
        ttk.Label(container, text=_("منصة ذكية لإدارة حضور الطلبة ونتائجهم"), style="SplashTag.TLabel").pack(pady=(8, 20))

        self._progress = ttk.Progressbar(container, mode="indeterminate", length=240,
                                          style=progress_style)
        self._progress.pack()
        self._progress.start(12)

        self._center_window(420, 360)
        self._top.deiconify()
        self._top.after(50, self._top.lift)

    def _center_window(self, width, height):
        self._top.update_idletasks()
        sw = self._top.winfo_screenwidth()
        sh = self._top.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self._top.geometry(f"{width}x{height}+{x}+{y}")

    def destroy(self):
        if self._progress:
            try:
                self._progress.stop()
            except Exception:
                pass
        self._top.destroy()


def main():

    # Charger la langue depuis le fichier de config
    lang_cfg = Path(__file__).parent / "i18n" / "lang.cfg"
    lang = "ar"
    if lang_cfg.exists():
        try:
            lang = lang_cfg.read_text(encoding="utf-8").strip()
        except Exception:
            lang = "ar"
    init_db()
    install_i18n(lang)

    root = tk.Tk()
    install_bundle_fonts(root)
    root.withdraw()
    root.update_idletasks()

    splash = SplashScreen(root, Path(__file__).resolve().parent / "assets" / "logo.png")

    app_holder = {}

    def launch_app():
        splash.destroy()
        root.deiconify()
        app_holder["app"] = AttendanceApp(root)

    root.after(SplashScreen.DURATION_MS, launch_app)
    root.mainloop()
if __name__ == "__main__":
    main()