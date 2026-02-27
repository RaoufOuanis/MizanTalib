import ctypes
import tkinter as tk


def safe_grab(win):
    """Set a modal grab on *win* that survives minimize/restore on Windows.

    When a Toplevel has ``grab_set()`` active and the user minimises it,
    the grab prevents any interaction (including restoring the window from the
    taskbar).  This helper releases the grab on ``<Unmap>`` (minimise) and
    re-acquires it on ``<Map>`` (restore), solving the problem.
    """
    try:
        win.grab_set()
    except Exception:
        pass

    def _on_map(event):
        if event.widget is win:
            try:
                win.grab_set()
            except Exception:
                pass

    def _on_unmap(event):
        if event.widget is win:
            try:
                win.grab_release()
            except Exception:
                pass

    win.bind("<Map>", _on_map)
    win.bind("<Unmap>", _on_unmap)


def get_work_area():
    # Returns (left, top, right, bottom) of the Windows work area (excluding taskbar)
    SPI_GETWORKAREA = 0x0030
    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]
    rect = RECT()
    ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom

def center_window_avoid_taskbar(root, width, height):
    left, top, right, bottom = get_work_area()
    work_width = right - left
    work_height = bottom - top
    x = left + (work_width - width) // 2
    y = top + (work_height - height) // 2
    root.geometry(f"{width}x{height}+{x}+{y}")

# Example usage:
if __name__ == "__main__":
    root = tk.Tk()
    center_window_avoid_taskbar(root, 900, 600)
    root.mainloop()
