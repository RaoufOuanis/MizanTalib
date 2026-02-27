# tooltip.py - ToolTip class
import tkinter as tk

# Module-level defaults - can be changed at runtime via set_default_tooltip_colors
_DEFAULT_TIP_BG = "#ffffe0"
_DEFAULT_TIP_FG = "#000000"


def set_default_tooltip_colors(bg: str, fg: str) -> None:
    """Set module defaults for tooltip background and foreground.

    Call this from the application when the theme changes so existing and
    future ToolTip instances use colors appropriate for the theme.
    """
    global _DEFAULT_TIP_BG, _DEFAULT_TIP_FG
    _DEFAULT_TIP_BG = bg
    _DEFAULT_TIP_FG = fg


class ToolTip:
    def __init__(self, widget, text='', bg=None, fg=None, delay=500):
        self.widget = widget
        self.text = text
        self.bg = bg
        self.fg = fg
        self.delay = delay
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.showtip)

    def unschedule(self):
        if self.id:
            try:
                self.widget.after_cancel(self.id)
            except Exception:
                pass
            self.id = None

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 1
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        bg = self.bg or _DEFAULT_TIP_BG
        fg = self.fg or _DEFAULT_TIP_FG
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background=bg,
            foreground=fg,
            relief=tk.SOLID,
            borderwidth=1,
            font=("tahoma", "8", "normal"),
        )
        label.pack(ipadx=4)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            try:
                tw.destroy()
            except Exception:
                pass
