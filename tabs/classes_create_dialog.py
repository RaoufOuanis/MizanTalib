# tabs/classes_create_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from center_window import safe_grab
from db import get_conn
from i18n import gettext_ as _

def open_class_dialog(app_ctx):
    """نافذة إنشاء قسم جديد"""
    win = tk.Toplevel(app_ctx.root)
    win.title(_("إنشاء قسم جديد"))
    win.transient(app_ctx.root)
    safe_grab(win)
    win.resizable(False, False)

    win.columnconfigure(0, weight=1)
    win.rowconfigure(0, weight=1)

    content = ttk.Frame(win, padding=(14, 12))
    content.grid(row=0, column=0, sticky="nsew")
    content.columnconfigure(1, weight=1)

    # --- الطور ---
    ttk.Label(content, text=_("الطور")).grid(row=0, column=0, padx=(0, 8), pady=4, sticky="e")
    cycle_var = tk.StringVar()
    cycle_options = [("ليسانس", _("ليسانس")), ("ماستر", _("ماستر"))]
    cycle_display_map = {display: value for value, display in cycle_options}
    combo_cycle = ttk.Combobox(
        content,
        textvariable=cycle_var,
        values=[display for _, display in cycle_options],
        state="readonly"
    )
    combo_cycle.grid(row=0, column=1, padx=0, pady=4, sticky="ew")

    # --- السنة ---
    ttk.Label(content, text=_("السنة")).grid(row=1, column=0, padx=(0, 8), pady=4, sticky="e")
    year_var = tk.StringVar()
    combo_year = ttk.Combobox(content, textvariable=year_var, state="readonly")
    combo_year.grid(row=1, column=1, padx=0, pady=4, sticky="ew")

    def update_years(event=None):
        selected_cycle = cycle_display_map.get(cycle_var.get())
        if selected_cycle == "ليسانس":
            combo_year["values"] = ["1", "2", "3"]
        elif selected_cycle == "ماستر":
            combo_year["values"] = ["1", "2"]
        else:
            combo_year["values"] = []
        year_var.set("")
    combo_cycle.bind("<<ComboboxSelected>>", update_years)

    # --- الفوج ---
    ttk.Label(content, text=_("الفوج")).grid(row=2, column=0, padx=(0, 8), pady=4, sticky="e")
    group_var = tk.StringVar()
    group_options = [("بدون تفويج", _("بدون تفويج"))] + [(str(i), str(i)) for i in range(1, 11)]
    group_display_map = {display: value for value, display in group_options}
    combo_group = ttk.Combobox(
        content,
        textvariable=group_var,
        values=[display for _, display in group_options],
        state="readonly"
    )
    combo_group.grid(row=2, column=1, padx=0, pady=4, sticky="ew")
    combo_group.current(0)

    # --- الفصيلة ---
    ttk.Label(content, text=_("الفصيلة (A-D، اختياري)")).grid(row=3, column=0, padx=(0, 8), pady=4, sticky="e")
    section_var = tk.StringVar()
    section_options = [("بدون فصيلة", _("بدون فصيلة")), ("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]
    section_display_map = {display: value for value, display in section_options}
    combo_section = ttk.Combobox(
        content,
        textvariable=section_var,
        values=[display for _, display in section_options],
        state="readonly"
    )
    combo_section.grid(row=3, column=1, padx=0, pady=4, sticky="ew")
    combo_section.current(0)

    # --- التخصص ---
    ttk.Label(content, text=_("التخصص (اختياري، 3-6 أحرف لاتينية)")).grid(row=4, column=0, padx=(0, 8), pady=4, sticky="e")
    spec_entry = ttk.Entry(content)
    spec_entry.grid(row=4, column=1, padx=0, pady=4, sticky="ew")

    # --- زر الإنشاء ---
    def create():
        cycle = cycle_display_map.get(cycle_var.get())
        year = year_var.get()
        group = group_display_map.get(group_var.get())
        section = section_display_map.get(section_var.get())
        spec = spec_entry.get().strip().upper()

        if not cycle or not year:
            messagebox.showerror(_("خطأ"), _("يجب اختيار الطور والسنة"))
            return

        cycle_code = "L" if cycle == "ليسانس" else "M"

        # تحقق من التخصص
        if spec:
            if not (3 <= len(spec) <= 6 and spec.isalpha()):
                messagebox.showerror(_("خطأ"), _("التخصص يجب أن يكون 3 إلى 6 أحرف لاتينية"))
                return
        else:
            spec = None

        group_val = None if group == "بدون تفويج" else group
        section_val = None if section == "بدون فصيلة" else section

        # بناء id
        cid = f"{cycle_code}{year}"
        if spec:
            cid += f"-{spec}"
        if group_val:
            cid += f"-grp{group_val}{section_val if section_val else ''}"

        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO classes (id, cycle, year, groupNbr, section, specialty) VALUES (?,?,?,?,?,?)",
                (cid, cycle, int(year), int(group_val) if group_val else None, section_val, spec)
            )
            conn.commit()
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            if "UNIQUE constraint" in str(e) or "UNIQUE constraint failed" in str(e):
                messagebox.showwarning(
                    _("تنبيه"),
                    _("يوجد قسم بنفس المعرف أو المواصفات بالفعل. يرجى اختيار قيم مختلفة.")
                )
            else:
                messagebox.showerror(_("خطأ"), _("تعذر إنشاء القسم:\n{e}").format(e=e))
            return
        finally:
            if conn:
                conn.close()

        messagebox.showinfo(_("تم"), _("تم إنشاء القسم {cid}").format(cid=cid))
        win.destroy()
        app_ctx.load_classes()

    ttk.Label(
        content,
        text=_("ملاحظة: بعد الانتهاء من إضافة الأقسام الجديدة يجب إعادة تشغيل البرنامج قبل العمل بها"),
        wraplength=360,
        foreground="#b36b00",
        justify="center"
    ).grid(row=5, column=0, columnspan=2, pady=(12, 4), sticky="ew")

    btns = ttk.Frame(content)
    btns.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(4, 0))
    btns.columnconfigure(0, weight=1)
    btns.columnconfigure(1, weight=1)

    ttk.Button(btns, text=_("❌ إغلاق"), command=win.destroy).grid(row=0, column=0, padx=(0, 6), sticky="w")
    ttk.Button(btns, text=_("✅ إنشاء"), command=create).grid(row=0, column=1, padx=(6, 0), sticky="e")

    win.update_idletasks()
    req_w = win.winfo_reqwidth()
    req_h = win.winfo_reqheight()
    parent_x = app_ctx.root.winfo_rootx()
    parent_y = app_ctx.root.winfo_rooty()
    parent_w = app_ctx.root.winfo_width()
    parent_h = app_ctx.root.winfo_height()
    x = parent_x + (parent_w - req_w) // 2
    y = parent_y + (parent_h - req_h) // 2
    win.geometry(f"{req_w}x{req_h}+{x}+{y}")
    win.minsize(req_w, req_h)

    