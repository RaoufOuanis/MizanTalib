# tabs/classes_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
from admin import store_active_class
from tooltip import ToolTip
from tabs.classes_create_dialog import open_class_dialog
from i18n import gettext_ as _

from services.class_service import delete_class, list_classes


class ClassesTabMixin:
    def build_classes_tab(self):
        f = self.tab_classes
        ttk.Label(f, text=_("إدارة الأقسام"), font=("Tajawal", 16, "bold")).pack(pady=8)
        topf = ttk.Frame(f)
        topf.pack(fill='x', padx=8, pady=6)

        # ---------------- القسم النشط ----------------
        left = ttk.Frame(topf)
        left.pack(side='left', padx=6)
        ttk.Label(left, text=_("القسم النشط الحالي")).pack(anchor='w')
        self.lbl_active = ttk.Label(
            left,
            text=self.active_class if self.active_class else _("(غير مفعل)"),
            font=("Arial", 11, "bold"),
            foreground="blue"
        )
        self.lbl_active.pack(anchor='w', pady=2)

        self.btn_toggle = tk.Button(left, text="", width=18, command=self.toggle_active_class)
        self.btn_toggle.pack(side='left', padx=8)
        ToolTip(self.btn_toggle, _("تنشيط أو إلغاء تنشيط القسم المحدد في الجدول"))
        self.update_toggle_button_look()

        # ---------------- أزرار التحكم ----------------
        right = ttk.Frame(topf)
        right.pack(side='right', padx=6)

        self.btn_create_class = ttk.Button(right, text=_("➕ إنشاء قسم جديد"), command=lambda: open_class_dialog(self))


        self.btn_create_class.pack(side='left', padx=6)
        ToolTip(self.btn_create_class, _("إنشاء قسم جديد (طور/سنة/فوج/فصيلة/تخصص)"))

        self.btn_delete_class = ttk.Button(right, text=_("🗑 حذف قسم"), command=self.delete_selected_class_with_auth)
        self.btn_delete_class.pack(side='left', padx=6)
        ToolTip(self.btn_delete_class, _("حذف القسم المحدد (يتطلب كلمة السر الإدارية)"))

        self.btn_reload = ttk.Button(right, text=_("🔄 إعادة تحميل"), command=self.load_classes)
        self.btn_reload.pack(side='left', padx=6)
        ToolTip(self.btn_reload, _("إعادة تحميل قائمة الأقسام من قاعدة البيانات"))

        # ---------------- جدول عرض الأقسام ----------------
        columns = ("id", "cycle", "year", "group", "section", "spec")
        self.tree_classes = ttk.Treeview(f, columns=columns, show="headings", height=12)

        headers = {
            "id": _("رمز القسم"),
            "cycle": _("الطور"),
            "year": _("السنة"),
            "group": _("الفوج"),
            "section": _("الفصيلة"),
            "spec": _("التخصص")
        }
        for col in columns:
            self.tree_classes.heading(col, text=headers[col])
            self.tree_classes.column(col, width=110 if col == "id" else 80, anchor="center")

        self.tree_classes.pack(fill="both", expand=True, padx=12, pady=6)
        self.tree_classes.bind("<<TreeviewSelect>>", self.on_select_class)

        # ---------------- سطر إضافي لعرض القسم المحدد ----------------
        selected_frame = ttk.Frame(f)
        selected_frame.pack(fill='x', padx=12, pady=4)
        selected_frame.columnconfigure(0, weight=1)
        self.lbl_selected_id = ttk.Label(
            selected_frame,
            text=self.active_class if self.active_class else _("(غير مفعل)"),
            font=("Arial", 11, "bold"),
            foreground="blue",
            anchor='w'
        )
        self.lbl_selected_id.grid(row=0, column=0, sticky='w')
        self.lbl_selected_prefix = ttk.Label(selected_frame, text=_(":القسم المحدد"), anchor='e')
        self.lbl_selected_prefix.grid(row=0, column=1, sticky='e', padx=(6,0))

        # تحميل الأقسام
        self.load_classes()

    

    def update_toggle_button_look(self):
        if self.active_class:
            self.btn_toggle.config(text=_("🟢 إلغاء تنشيط"), bg="#99ff99", activebackground="#55ff55")
        else:
            self.btn_toggle.config(text=_("🔴 تنشيط القسم"), bg="#ff9999", activebackground="#ff5555")

    # ---------------- حذف قسم ----------------
    def delete_selected_class_with_auth(self):
        if not self.require_admin_password():
            return
        sel = self.tree_classes.selection()
        if not sel:
            messagebox.showerror(_("خطأ"), _("اختر قسماً لحذفه"))
            return

        cid = self.tree_classes.item(sel[0], "values")[0]
        if messagebox.askyesno(_("تأكيد"), _("هل أنت متأكد من حذف القسم {cid}؟ سيتم حذف كل البيانات المرتبطة به تلقائيًا.").format(cid=cid)):
            try:
                removed = delete_class(cid)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر حذف القسم:\n{exc}").format(exc=exc))
                return
            if not removed:
                messagebox.showwarning(_("تنبيه"), _("لم يتم العثور على القسم المطلوب حذفه."))
                return

            # إذا كان هو النشط → إلغاء التنشيط
            if self.active_class == cid:
                self.active_class = None
                store_active_class(None)
                self.lbl_active.config(text=_("(غير مفعل)"))
                self.update_toggle_button_look()
                self.lbl_selected_id.config(text=_("(غير مفعل)"))

            messagebox.showinfo(_("تم"), _("تم حذف القسم {cid} وجميع بياناته المرتبطة").format(cid=cid))
            self.load_classes()

    # ---------------- تحميل الأقسام ----------------
    def load_classes(self):
        selected_id = self.active_class
        self.tree_classes.delete(*self.tree_classes.get_children())

        try:
            rows = list_classes()
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{exc}").format(exc=exc))
            rows = []

        for r in rows:
            self.tree_classes.insert(
                "", tk.END,
                values=(
                    r["id"],
                    r["cycle"],
                    r["year"],
                    r["groupNbr"] or "-",
                    r["section"] or "-",
                    r["specialty"] or "-"
                )
            )

        if not selected_id:
            self.lbl_selected_id.config(text=_("(غير مفعل)"))

        if selected_id:
            for item in self.tree_classes.get_children():
                if self.tree_classes.item(item, "values")[0] == selected_id:
                    self.tree_classes.selection_set(item)
                    break

    # ---------------- عند اختيار قسم ----------------
    def on_select_class(self, event):
        sel = self.tree_classes.selection()
        if not sel:
            return
        vals = self.tree_classes.item(sel[0], "values")
        self.lbl_selected_id.config(text=vals[0])

    # ---------------- تفعيل/إلغاء تفعيل ----------------
    def toggle_active_class(self):
        sel = self.tree_classes.selection()
        if self.active_class:
            self.active_class = None
            store_active_class(None)
            self.lbl_active.config(text=_("(غير مفعل)"))
            self.set_status(_("تم إلغاء تنشيط القسم"))
            self.lbl_selected_id.config(text=_("(غير مفعل)"))
            # Notify other tabs to refresh their active-class displays
            try:
                if hasattr(self, 'update_active_class_label'):
                    self.update_active_class_label()
            except Exception:
                pass
        elif sel:
            vals = self.tree_classes.item(sel[0], "values")
            cid = vals[0]
            self.active_class = cid
            store_active_class(cid)
            self.lbl_active.config(text=cid)
            self.set_status(_("تم تنشيط القسم {cid}").format(cid=cid))
            self.lbl_selected_id.config(text=cid)
            # Notify other tabs to refresh their active-class displays
            try:
                if hasattr(self, 'update_active_class_label'):
                    self.update_active_class_label()
            except Exception:
                pass
        else:
            messagebox.showerror(_("خطأ"), _("اختر قسماً من الجدول"))
        self.update_toggle_button_look()
