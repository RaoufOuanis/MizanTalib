# tabs/session_type_tab.py
import tkinter as tk
from tkinter import ttk, messagebox

from center_window import safe_grab
from tooltip import ToolTip
from i18n import gettext_ as _, get_language

from services.session_type_service import (
    fetch_session_types,
    add_session_type as service_add_session_type,
    delete_session_type as service_delete_session_type,
)

class SessionTypeMixin:
    def open_session_types_window(self, refresh_callback=None):
        """فتح نافذة مستقلة لإدارة أنواع الحصص"""
        self._refresh_callback = refresh_callback
        win = tk.Toplevel(self.root)
        win.title(_("📚 إدارة أنواع الحصص"))
        W, H = 560, 460

        # --- تمركز النافذة ---
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - (W // 2)
        y = (win.winfo_screenheight() // 2) - (H // 2)
        win.geometry(f"{W}x{H}+{x}+{y}")
        win.minsize(W, H)

        win.transient(self.root)
        safe_grab(win)

        is_rtl = (get_language() or "ar").lower().startswith("ar")
        label_col = 1 if is_rtl else 0
        field_col = 0 if is_rtl else 1
        label_sticky = "e" if is_rtl else "w"
        field_sticky = "e" if is_rtl else "w"

        # ====== إدخال البيانات ======
        form = ttk.Frame(win)
        form.pack(fill="x", padx=8, pady=8)
        form.columnconfigure(0, weight=1 if field_col == 0 else 0)
        form.columnconfigure(1, weight=1 if field_col == 1 else 0)

        ttk.Label(form, text=_("رمز المادة")).grid(row=0, column=label_col, padx=4, pady=4, sticky=label_sticky)
        self.var_subject = tk.StringVar()

        def _validate_subject(new_value: str) -> bool:
            if len(new_value) > 8:
                return False
            if not new_value:
                return True
            return all(ch.isascii() and ch.isalnum() for ch in new_value)

        validate_subject = win.register(_validate_subject)
        entry_subject = ttk.Entry(
            form,
            textvariable=self.var_subject,
            width=15,
            justify="center",
            validate="key",
            validatecommand=(validate_subject, "%P"),
        )
        entry_subject.grid(row=0, column=field_col, padx=4, pady=4, sticky=field_sticky)
        ToolTip(entry_subject, _("رمز المادة هو الإسم المختصر للمادة: 8 أحرف لاتينية أو أرقام على أقصى تقدير"))

        ttk.Label(form, text=_("نوع الحصة")).grid(row=1, column=label_col, padx=4, pady=4, sticky=label_sticky)
        self.var_type = tk.StringVar()
        combo = ttk.Combobox(
            form,
            textvariable=self.var_type,
            values=["Cours", "TP", "TD"],
            state="readonly",
            width=15,
        )
        combo.grid(row=1, column=field_col, padx=4, pady=4, sticky=field_sticky)
        combo.current(0)
        ToolTip(combo, _("اختر نوع الحصة (Cours/TP/TD)"))

        btn_add = ttk.Button(form, text=_("➕ إضافة"), command=self.add_session_type)
        btn_add.grid(row=2, column=field_col, padx=4, pady=(6, 2), sticky=field_sticky)
        ToolTip(btn_add, _("إضافة نوع حصة جديد باستخدام القيم أعلاه"))

        # ====== جدول الأنواع ======
        self.tree_session_types = ttk.Treeview(win, columns=("id","subject","type"), show="headings", height=12)
        self.tree_session_types.heading("id", text="ID")
        self.tree_session_types.heading("subject", text=_("رمز المادة"))
        self.tree_session_types.heading("type", text=_("نوع الحصة"))

        self.tree_session_types.column("id", width=60, anchor="center")
        self.tree_session_types.column("subject", width=150, anchor="center")
        self.tree_session_types.column("type", width=120, anchor="center")

        self.tree_session_types.pack(fill="both", expand=True, padx=8, pady=6)
        ToolTip(self.tree_session_types, _("قائمة أنواع الحصص المسجلة حاليًا"))

        # أزرار تحت الجدول
        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=8, pady=6)

        btn_close = ttk.Button(btns, text=_("❌ إغلاق"), command=win.destroy)
        btn_close.pack(side="left", padx=4)
        ToolTip(btn_close, _("إغلاق النافذة والرجوع للشاشة الرئيسية"))

        btn_edit = ttk.Button(btns, text=_("✏️ تعديل"), command=self.edit_session_type)
        btn_edit.pack(side="right", padx=4)
        ToolTip(btn_edit, _("حدد سطرًا ثم عدل القيم في الحقول أعلاه"))

        btn_delete = ttk.Button(btns, text=_("🗑 حذف"), command=self.delete_session_type)
        btn_delete.pack(side="right", padx=4)
        ToolTip(btn_delete, _("حذف نوع الحصة المحدد من القائمة"))

        self.load_session_types()

    def load_session_types(self):
        for iid in self.tree_session_types.get_children():
            self.tree_session_types.delete(iid)

        try:
            rows = fetch_session_types()
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{exc}").format(exc=exc))
            rows = []

        for r in rows:
            self.tree_session_types.insert("", "end", values=(r["id"], r["subject_code"], r["type"]))

    def add_session_type(self):
        subj = self.var_subject.get().strip().upper()
        t = self.var_type.get().strip()
        if not subj:
            messagebox.showerror(_("خطأ"), _("أدخل رمز المادة أولاً"))
            return

        try:
            service_add_session_type(subj, t)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر الإضافة: {e}").format(e=e))
            return

        self.load_session_types()
        self.var_subject.set("")
        messagebox.showinfo(_("تم"), _("تمت إضافة {subject}-{stype}").format(subject=subj, stype=t))
        if hasattr(self, "_refresh_callback") and self._refresh_callback:
            self._refresh_callback()

    def edit_session_type(self):
        sel = self.tree_session_types.selection()
        if not sel:
            messagebox.showwarning(_("تنبيه"), _("اختر سطرًا أولاً"))
            return
        iid, subj, t = self.tree_session_types.item(sel[0], "values")

        # وضع القيم في الحقول لتعديلها
        self.var_subject.set(subj)
        self.var_type.set(t)

        # حذف القديم
        try:
            service_delete_session_type(int(iid))
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر التعديل:\n{exc}").format(exc=exc))
            return

        self.load_session_types()
        if hasattr(self, "_refresh_callback") and self._refresh_callback:
            self._refresh_callback()

    def delete_session_type(self):
        sel = self.tree_session_types.selection()
        if not sel:
            messagebox.showwarning(_("تنبيه"), _("اختر سطرًا لحذفه"))
            return
        iid, subj, t = self.tree_session_types.item(sel[0], "values")

        if not messagebox.askyesno(_("تأكيد"), _("هل تريد حذف {subject}-{stype}؟").format(subject=subj, stype=t)):
            return

        try:
            service_delete_session_type(int(iid))
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر الحذف:\n{exc}").format(exc=exc))
            return

        self.load_session_types()
        messagebox.showinfo(_("تم"), _("تم حذف {subject}-{stype}").format(subject=subj, stype=t))
        if hasattr(self, "_refresh_callback") and self._refresh_callback:
            self._refresh_callback()
