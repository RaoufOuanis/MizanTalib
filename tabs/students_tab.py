# tabs/students_tab.py
import importlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from center_window import safe_grab
from tooltip import ToolTip
from i18n import gettext_ as _, get_language

from services.student_service import (
    add_student,
    bulk_insert_students,
    fetch_class_filter_metadata,
    fetch_class_ids,
    fetch_students,
    remove_student,
    update_student,
)

from services.archive_data_service import fetch_student_summary

_pd_module = None


def _get_pandas_module():
    global _pd_module
    if _pd_module is None:
        try:
            _pd_module = importlib.import_module("pandas")
        except ImportError:
            _pd_module = None
    return _pd_module


class StudentsTabMixin:
    # ---------------- أدوات مساعدة ----------------
    def center_window(self, win, width=960, height=600):
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x, y = (sw - width) // 2, (sh - height) // 2
        win.geometry(f"{width}x{height}+{x}+{y}")

    def _safe_status(self, text):
        if hasattr(self, "set_status") and callable(getattr(self, "set_status")):
            self.set_status(text, timeout=4000)

    def _show_students_notice(self, title, text, kind="info", parent=None):
        if parent is None:
            parent = self.root
            try:
                parent = self.tree_students.winfo_toplevel()
            except Exception:
                parent = self.root

        try:
            dialog = tk.Toplevel(parent)
            dialog.title(title)
            self.center_window(dialog, 520, 180)
            dialog.transient(parent)
            safe_grab(dialog)
            dialog.resizable(False, False)

            icon_map = {
                "info": "✅",
                "warning": "⚠️",
                "error": "❌",
            }
            icon = icon_map.get(kind, "ℹ️")

            body = ttk.Frame(dialog, padding=14)
            body.pack(fill="both", expand=True)
            ttk.Label(body, text=f"{icon} {text}", justify="right", wraplength=470).pack(fill="both", expand=True)
            ttk.Button(body, text=_("موافق"), command=dialog.destroy).pack(pady=(8, 0))

            try:
                dialog.lift()
                dialog.focus_force()
            except Exception:
                pass
            return
        except Exception:
            pass

        if kind == "warning":
            messagebox.showwarning(title, text, parent=parent)
        elif kind == "error":
            messagebox.showerror(title, text, parent=parent)
        else:
            messagebox.showinfo(title, text, parent=parent)

    def _format_session_datetime(self, value):
        if not value:
            return ""
        if isinstance(value, datetime):
            dt = value
        else:
            dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
                try:
                    dt = datetime.strptime(str(value), fmt)
                    break
                except Exception:
                    dt = None
            if dt is None:
                return str(value)
        return dt.strftime("%d/%m/%Y %H:%M")

    def _students_matches_search(self, row: dict, needle: str) -> bool:
        if not needle:
            return True
        n = needle.strip().lower()
        if not n:
            return True
        sid = str(row.get("StudentId", "") or "").lower()
        name = str(row.get("Name", "") or "").lower()
        surname = str(row.get("Surname", "") or "").lower()
        return (n in sid) or (n in name) or (n in surname)

    def open_selected_student_statistics(self, _event=None):
        sel = self.tree_students.selection()
        if not sel:
            return
        vals = self.tree_students.item(sel[0], "values")
        if not vals or len(vals) < 2:
            return
        student_id = str(vals[1])
        self._open_student_statistics_window(student_id)

    def _open_student_statistics_window(self, student_id: str):
        try:
            summary, details = fetch_student_summary(student_id)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر جلب الإحصائيات:\n{error}").format(error=e))
            return

        if not summary:
            messagebox.showinfo(_("لا يوجد"), _("لا توجد سجلات لهذا الطالب."))
            return

        # Important: if the students management window is opened modally with a grab,
        # creating this stats window as a child of that toplevel helps avoid
        # unresponsive behavior caused by the grab redirecting events.
        owner = None
        try:
            owner = self.tree_students.winfo_toplevel()
        except Exception:
            owner = None
        if owner is None:
            owner = getattr(self, "root", None)
        if owner is None:
            owner = self.root

        # Keep a single stats window instance (avoids stacking multiple windows on double-click)
        try:
            existing = getattr(self, "_student_stats_window", None)
            if existing is not None and existing.winfo_exists():
                existing.destroy()
        except Exception:
            pass

        win = tk.Toplevel(owner)
        win.title(_("إحصائيات الطالب"))
        self.center_window(win, 900, 520)
        try:
            win.transient(owner)
        except Exception:
            pass
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        try:
            win.bind("<Escape>", lambda _e: win.destroy())
        except Exception:
            pass
        try:
            win.lift()
            win.focus_force()
        except Exception:
            pass
        self._student_stats_window = win
        ttk.Label(
            win,
            text=_("👤 {name} {surname} ({student_id})").format(
                name=summary[0].get("Name", ""),
                surname=summary[0].get("Surname", ""),
                student_id=summary[0].get("StudentId", student_id),
            ),
            font=("Arial", 14, "bold"),
        ).pack(pady=(8, 2))

        tree_summary = ttk.Treeview(
            win,
            columns=("stype", "sessions", "total_part", "first", "last"),
            show="headings",
            height=6,
        )
        headers = [
            ("stype", _("نوع الحصة")),
            ("sessions", _("عدد الجلسات")),
            ("total_part", _("إجمالي المشاركة")),
            ("first", _("أول حضور")),
            ("last", _("آخر حضور")),
        ]
        for col, text in headers:
            tree_summary.heading(col, text=text)
            tree_summary.column(col, anchor="center", width=170)
        tree_summary.pack(fill="x", padx=8, pady=6)
        for r in summary:
            first_fmt = self._format_session_datetime(r.get("first_session"))
            last_fmt = self._format_session_datetime(r.get("last_session"))
            tree_summary.insert(
                "",
                "end",
                values=(
                    r.get("session_label", ""),
                    r.get("total_sessions", 0),
                    r.get("total_part", 0) or 0,
                    first_fmt,
                    last_fmt,
                ),
            )

        tree_details = ttk.Treeview(
            win,
            columns=("date", "token", "class", "stype", "part"),
            show="headings",
            height=12,
        )
        headers2 = [
            ("date", _("التاريخ")),
            ("token", _("رمز الحصة")),
            ("class", _("القسم")),
            ("stype", _("نوع الحصة")),
            ("part", _("المشاركة")),
        ]
        for col, text in headers2:
            tree_details.heading(col, text=text)
            tree_details.column(col, anchor="center", width=170)
        tree_details.pack(fill="both", expand=True, padx=8, pady=8)
        for r in details:
            date_fmt = self._format_session_datetime(r.get("SessionDate"))
            tree_details.insert(
                "",
                "end",
                values=(
                    date_fmt,
                    r.get("sessionToken", ""),
                    r.get("classId", ""),
                    r.get("session_label", ""),
                    r.get("participation", 0) or 0,
                ),
            )

    # ---------------- بناء الواجهة ----------------
    def build_students_tab(self, parent=None):
        f = parent if parent else self.tab_students
        is_rtl = (get_language() or "ar").lower().startswith("ar")
        side = "right" if is_rtl else "left"
        opposite_side = "left" if is_rtl else "right"
        try:
            if isinstance(f.master, tk.Toplevel) or isinstance(f, tk.Toplevel):
                self.center_window(f.master if hasattr(f, "master") else f, 1000, 600)
        except Exception:
            pass

        ttk.Label(f, text=_("إدارة الطلبة"), font=("Tajawal", 16, "bold")).pack(pady=8)

        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=4)

        # Split toolbar into rows so all controls fit in EN/AR
        filters_row = ttk.Frame(top)
        filters_row.pack(fill="x")
        buttons_row = ttk.Frame(top)
        buttons_row.pack(fill="x", pady=(2, 0))

        # Row 1: filter + search
        filters = ttk.Frame(filters_row)
        filters.pack(side=side, fill="x", expand=True)

        class_frame = ttk.Frame(filters)
        class_frame.pack(side=side)

        self.class_filter = ttk.Combobox(class_frame, state="readonly", width=32)
        self.class_filter.pack(side=side, padx=(0, 6))
        ToolTip(self.class_filter, _("اختر: كل الطلبة، سنة معيّنة، أو قسم معيّن"))
        self.populate_class_filter()
        self.class_filter.bind("<<ComboboxSelected>>", lambda e: self.load_students())

        self.students_search_var = tk.StringVar(value="")
        search_frame = ttk.Frame(filters)
        search_frame.pack(side=side)

        search_label = ttk.Label(search_frame, text=_("🔎 بحث"))
        search_hint = ttk.Label(search_frame, text=_("(لقب/اسم/رقم)"), font=("TkDefaultFont", 8))
        self.students_search_entry = ttk.Entry(
            search_frame,
            textvariable=self.students_search_var,
            width=22,
            justify=("right" if is_rtl else "left"),
        )

        # LTR: label on the left of the field. RTL: label on the right.
        search_label.pack(side=side)
        search_hint.pack(side=side, padx=(2, 8))
        self.students_search_entry.pack(side=side, padx=(0, 4))
        ToolTip(self.students_search_entry, _("ابحث باللقب أو الاسم أو الرقم"))

        def _on_search_change(*_args):
            self.load_students()

        try:
            self.students_search_var.trace_add("write", _on_search_change)
        except Exception:
            self.students_search_entry.bind("<KeyRelease>", lambda e: self.load_students())

        # Row 2: action buttons (split into groups to avoid clipping)
        btn_side = side
        btn_group_main = ttk.Frame(buttons_row)
        btn_group_io = ttk.Frame(buttons_row)
        btn_group_main.pack(side=btn_side)
        btn_group_io.pack(side=btn_side)

        ttk.Button(btn_group_main, text=_("➕ إضافة"), command=self.add_student_dialog).pack(side=btn_side, padx=4)
        ttk.Button(btn_group_main, text=_("✏️ تحرير"), command=self.edit_selected_student).pack(side=btn_side, padx=4)
        ttk.Button(btn_group_main, text=_("🗑 حذف"), command=self.delete_selected_student).pack(side=btn_side, padx=4)
        ttk.Button(btn_group_main, text=_("🗑 حذف الكل"), command=self.delete_all_displayed_students).pack(side=btn_side, padx=4)
        ttk.Button(
            btn_group_main,
            text=_("📊 إحصائيات"),
            command=self.open_selected_student_statistics,
        ).pack(side=btn_side, padx=4)

        ttk.Button(
            btn_group_io,
            text=_("🔄 إعادة تحميل"),
            command=lambda: (self.populate_class_filter(), self.load_students()),
        ).pack(side=btn_side, padx=4)
        ttk.Button(btn_group_io, text=_("📥 استيراد"), command=self.import_from_excel).pack(side=btn_side, padx=4)
        ttk.Button(btn_group_io, text=_("📤 تصدير"), command=self.export_to_excel).pack(side=btn_side, padx=4)

        # جدول
        table_frame = ttk.Frame(f); table_frame.pack(fill='both', expand=True, padx=10, pady=6)

        self.tree_students = ttk.Treeview(
            table_frame, columns=("row", "id", "name", "surname", "class"), show="headings"
        )
        headers = [
            ("row", _("#")),
            ("id", _("الرقم")),
            ("name", _("اللقب")),
            ("surname", _("الاسم")),
            ("class", _("القسم")),
        ]
        for col, text in headers:
            if col == "row":
                self.tree_students.heading(col, text=text)
            else:
                self.tree_students.heading(col, text=text, command=lambda c=col: self.sort_students(c))

        self.tree_students.column("row", width=60, anchor="center")
        self.tree_students.column("id", width=100, anchor="center")
        self.tree_students.column("name", width=180, anchor="center")
        self.tree_students.column("surname", width=180, anchor="center")
        self.tree_students.column("class", width=360, anchor="center")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_students.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_students.xview)
        self.tree_students.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree_students.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1); table_frame.columnconfigure(0, weight=1)
        ToolTip(self.tree_students, _("دابل كليك على طالب لعرض الإحصائيات"))
        self.tree_students.bind("<Double-1>", self.open_selected_student_statistics)

        self.students_status = tk.StringVar(value="")
        ttk.Label(f, textvariable=self.students_status, anchor="w").pack(fill="x", padx=10, pady=(0,6))

        self.load_students()

    # ---------------- الفلترة ----------------
    def populate_class_filter(self):
        metadata = fetch_class_filter_metadata()
        years = metadata.get("years", [])
        classes = metadata.get("classes", [])

        items: list[str] = []
        value_map: dict[str, tuple[str, object]] = {}

        label_all = _("📋 كل الطلبة")
        items.append(label_all)
        value_map[label_all] = ("all", None)

        for cycle, year in years:
            label = _("📚 {cycle} {year}").format(cycle=cycle, year=year)
            items.append(label)
            value_map[label] = ("year", (cycle, year))

        for class_id, cycle, year in classes:
            label = _("{class_id} ({cycle} {year})").format(class_id=class_id, cycle=cycle, year=year)
            items.append(label)
            value_map[label] = ("class", class_id)

        self._students_class_filter_map = value_map
        self.class_filter["values"] = items
        if items:
            self.class_filter.current(0)

    def get_selected_filter(self):
        val = self.class_filter.get()
        mapping = getattr(self, "_students_class_filter_map", {})
        if val in mapping:
            ftype, v = mapping[val]
            return (ftype, v)
        return ("all", None)

    # ---------------- إضافة / تحرير / حذف ----------------
    def add_student_dialog(self):
        self._student_dialog(_("إضافة طالب"))

    def edit_selected_student(self):
        sel = self.tree_students.selection()
        if not sel:
            messagebox.showerror(_("خطأ"), _("اختر طالباً للتحرير"))
            return
        vals = self.tree_students.item(sel[0], "values")
        if not vals or len(vals) < 5:
            messagebox.showerror(_("خطأ"), _("تعذر قراءة بيانات الطالب المحدد"))
            return
        _, sid, name, surname, class_id = vals
        self._student_dialog("تحرير طالب", sid, name, surname, class_id)

    def _student_dialog(self, title, sid="", name="", surname="", class_id=""):
        win = tk.Toplevel(self.root)
        win.title(title)
        self.center_window(win, 420, 250)
        win.transient(self.root)
        safe_grab(win)
        rows = [
            (_("الرقم"), "id", sid),
            (_("اللقب"), "name", name),
            (_("الاسم"), "surname", surname),
            (_("القسم"), "class", class_id),
        ]
        widgets = {}
        for i, (label, key, val) in enumerate(rows):
            ttk.Label(win, text=label, width=16).grid(row=i, column=1, padx=6, pady=6, sticky="e")
            if key == "class":
                classes = fetch_class_ids()
                combo = ttk.Combobox(win, state="readonly", width=36, values=classes)
                if val and val in classes:
                    combo.set(val)
                elif classes:
                    combo.current(0)
                combo.grid(row=i, column=0, padx=6, pady=6, sticky="w")
                widgets[key] = combo
            else:
                entry = ttk.Entry(win, width=38, justify="center")
                if key == "id" and sid:
                    entry.insert(0, val)
                    entry.config(state="disabled")
                elif val:
                    entry.insert(0, val)
                entry.grid(row=i, column=0, padx=6, pady=6, sticky="w")
                widgets[key] = entry

        def save():
            vals = {k: widgets[k].get().strip() for k in widgets}
            if not vals["id"] or not vals["surname"] or not vals["name"] or not vals["class"]:
                messagebox.showerror(_("خطأ"), _("كل الحقول مطلوبة"))
                return
            try:
                if sid:
                    updated = update_student(sid, vals["surname"], vals["name"], vals["class"])
                    if not updated:
                        messagebox.showwarning(_("تنبيه"), _("لم يتم تعديل بيانات الطالب (ربما لم تتغير)."))
                else:
                    created = add_student(vals["id"], vals["surname"], vals["name"], vals["class"])
                    if not created:
                        messagebox.showwarning(_("تنبيه"), _("الطالب موجود مسبقًا أو تعذر الإضافة."))
            except Exception as e:
                messagebox.showerror(_("خطأ"), _("تعذر حفظ الطالب:\n{error}").format(error=e))
                return
            win.destroy()
            self.load_students()

        ttk.Button(win, text=_("💾 حفظ"), command=save).grid(row=len(rows), column=0, columnspan=2, pady=8)

    def delete_selected_student(self):
        sel = self.tree_students.selection()
        if not sel:
            messagebox.showerror(_("خطأ"), _("اختر طالباً للحذف"))
            return
        vals = self.tree_students.item(sel[0], "values")
        if not vals or len(vals) < 2:
            messagebox.showerror(_("خطأ"), _("تعذر تحديد الطالب المطلوب"))
            return
        sid = vals[1]
        if not hasattr(self, "require_admin_password") or not self.require_admin_password():
            return
        if messagebox.askyesno(_("تأكيد"), _("حذف {sid}؟").format(sid=sid)):
            try:
                removed = remove_student(sid)
                if not removed:
                    messagebox.showwarning(_("تنبيه"), _("لم يتم العثور على الطالب المحدد لحذفه."))
            except Exception as e:
                messagebox.showerror(_("خطأ"), _("تعذر حذف الطالب:\n{error}").format(error=e))
            self.load_students()

    def delete_all_displayed_students(self):
        """حذف جميع الطلبة المعروضين حالياً في الجدول."""
        children = self.tree_students.get_children()
        if not children:
            messagebox.showwarning(_("تنبيه"), _("لا يوجد طلبة معروضون للحذف."))
            return

        count = len(children)
        if not hasattr(self, "require_admin_password") or not self.require_admin_password():
            return
        if not messagebox.askyesno(
            _("تأكيد"),
            _("هل أنت متأكد من حذف جميع الطلبة المعروضين ({count} طالب)؟\nهذا الإجراء لا يمكن التراجع عنه.").format(count=count),
        ):
            return

        deleted = 0
        errors = 0
        for iid in children:
            vals = self.tree_students.item(iid, "values")
            if not vals or len(vals) < 2:
                continue
            sid = vals[1]
            try:
                if remove_student(str(sid)):
                    deleted += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        self.load_students()

        if errors == 0:
            msg = _("✅ تم حذف {deleted} طالب بنجاح.").format(deleted=deleted)
            messagebox.showinfo(_("تم"), msg)
        else:
            msg = _("✅ تم حذف {deleted} طالب.\n⚠️ تعذر حذف {errors} طالب.").format(deleted=deleted, errors=errors)
            messagebox.showwarning(_("تنبيه"), msg)
        self._safe_status(msg)

    # ---------------- استيراد ----------------
    def import_from_excel(self):
        owner = self.root
        try:
            owner = self.tree_students.winfo_toplevel()
        except Exception:
            owner = self.root

        pd_module = _get_pandas_module()
        if pd_module is None:
            messagebox.showerror(
                _("خطأ"),
                _("حزمة pandas غير مثبتة في هذه البيئة. ثبتها ثم حاول مجددًا."),
                parent=owner,
            )
            return
        classes = fetch_class_ids()
        if not classes:
            messagebox.showerror(
                _("خطأ"),
                _("لم يتم إنشاء أقسام للطلبة في قاعدة البيانات، يجب إنشاء أقسام أولا"),
                parent=owner,
            )
            return

        win = tk.Toplevel(owner); win.title(_("اختر القسم للاستيراد"))
        self.center_window(win, 350, 120); win.transient(owner); safe_grab(win)
        ttk.Label(win, text=_("اختر القسم:"), width=12).pack(pady=8)
        combo = ttk.Combobox(win, values=classes, state="readonly", width=30); combo.pack(pady=4); combo.current(0)

        def proceed():
            class_id = combo.get()
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()
            file = filedialog.askopenfilename(parent=owner, filetypes=[(_("ملفات Excel"), "*.xlsx *.xls")])
            if not file: return
            try:
                df = pd_module.read_excel(file)
                cols = set(df.columns)
                if {"StudentId", "Surname", "Name"}.issubset(cols):
                    df["classId"] = class_id
                    self._insert_students(df, "StudentId", "Surname", "Name", "classId", class_id, owner=owner)
                else:
                    self._map_columns_dialog(df, class_id, owner=owner)
            except Exception as e:
                messagebox.showerror(_("خطأ"), str(e), parent=owner)

        ttk.Button(win, text=_("متابعة"), command=proceed).pack(pady=8)

    def _map_columns_dialog(self, df, class_id, owner=None):
        if owner is None:
            owner = self.root
            try:
                owner = self.tree_students.winfo_toplevel()
            except Exception:
                owner = self.root

        win = tk.Toplevel(owner); win.title(_("تعيين الأعمدة"))
        self.center_window(win, 400, 220); win.transient(owner); safe_grab(win)
        widgets = {}; required = ["StudentId", "Surname", "Name"]
        for i, key in enumerate(required):
            ttk.Label(win, text=_("عمود {key}:").format(key=key), width=14).grid(row=i, column=0, padx=6, pady=6, sticky="e")
            combo = ttk.Combobox(win, values=list(df.columns), state="readonly", width=30)
            combo.grid(row=i, column=1, padx=6, pady=6, sticky="w"); widgets[key] = combo

        def apply():
            mapping = {k: widgets[k].get() for k in required}
            if not all(mapping.values()):
                messagebox.showerror(_("خطأ"), _("اختر كل الأعمدة"), parent=win)
                return
            df["classId"] = class_id
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()
            self._insert_students(
                df,
                mapping["StudentId"],
                mapping["Surname"],
                mapping["Name"],
                "classId",
                class_id,
                owner=owner,
            )

        ttk.Button(win, text=_("تطبيق"), command=apply).grid(row=len(required), column=0, columnspan=2, pady=10)

    def _insert_students(self, df, col_id, col_surname, col_name, col_class, class_id, owner=None):
        if owner is None:
            owner = self.root
            try:
                owner = self.tree_students.winfo_toplevel()
            except Exception:
                owner = self.root

        try:
            def _defer_notice(title, text, kind="info"):
                try:
                    owner.after(30, lambda: self._show_students_notice(title, text, kind=kind, parent=owner))
                except Exception:
                    self._show_students_notice(title, text, kind=kind, parent=owner)

            pd_module = _get_pandas_module()
            payload = []
            for _idx, row in df.iterrows():
                student_id = row.get(col_id, "")
                surname = row.get(col_surname, "")
                name_val = row.get(col_name, "")
                class_val = row.get(col_class, class_id)
                if pd_module is not None:
                    if pd_module.isna(student_id):
                        student_id = ""
                    if pd_module.isna(surname):
                        surname = ""
                    if pd_module.isna(name_val):
                        name_val = ""
                    if pd_module.isna(class_val):
                        class_val = class_id
                payload.append(
                    {
                        "StudentId": student_id,
                        "Surname": surname,
                        "Name": name_val,
                        "classId": class_val,
                    }
                )
            total_payload = len(payload)
            inserted = bulk_insert_students(payload, class_id)
            self.load_students()
            skipped = total_payload - inserted
            if inserted > 0 and skipped > 0:
                info_msg = _("✅ تم استيراد {inserted} طالب إلى القسم {class_id}.\n⚠️ تم تجاهل {skipped} (موجودون مسبقًا أو بيانات ناقصة).").format(
                    inserted=inserted, class_id=class_id, skipped=skipped
                )
                _defer_notice(_("تم"), info_msg, kind="info")
            elif inserted > 0:
                info_msg = _("✅ تم استيراد {inserted} طالب إلى القسم {class_id}.").format(
                    inserted=inserted, class_id=class_id
                )
                _defer_notice(_("تم"), info_msg, kind="info")
            else:
                info_msg = _("⚠️ لم يتم استيراد أي طالب جديد — جميعهم موجودون مسبقًا أو بيانات ناقصة ({total} سطر في الملف).").format(
                    total=total_payload
                )
                _defer_notice(_("تنبيه"), info_msg, kind="warning")
            if hasattr(self, "students_status"):
                try:
                    self.students_status.set(info_msg)
                except Exception:
                    pass
            self._safe_status(info_msg)
        except Exception as e:
            fail_msg = _("❌ فشل استيراد الطلبة:\n{error}").format(error=e)
            try:
                owner.after(30, lambda: self._show_students_notice(_("خطأ"), fail_msg, kind="error", parent=owner))
            except Exception:
                self._show_students_notice(_("خطأ"), fail_msg, kind="error", parent=owner)
            if hasattr(self, "students_status"):
                try:
                    self.students_status.set(_("فشل الاستيراد"))
                except Exception:
                    pass
            self._safe_status(_("فشل الاستيراد"))

    # ---------------- تصدير ----------------
    def export_to_excel(self):
        pd_module = _get_pandas_module()
        if pd_module is None:
            messagebox.showerror(_("خطأ"), _("حزمة pandas غير مثبتة في هذه البيئة. ثبتها ثم حاول مجددًا."))
            return
        file = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[(_("ملفات Excel"), "*.xlsx")])
        if not file: return
        try:
            ftype,value=self.get_selected_filter()
            rows = fetch_students(ftype, value)
            dataset = [
                {
                    "StudentId": r["StudentId"],
                    "Surname": r["Surname"],
                    "Name": r["Name"],
                    "classId": r["classId"],
                }
                for r in rows
            ]
            pd_module.DataFrame(dataset,columns=["StudentId","Surname","Name","classId"]).to_excel(file,index=False)
            self._safe_status(_("تم التصدير"))
        except Exception as e:
            messagebox.showerror(_("خطأ"), str(e))

    # ---------------- تحميل وفرز ----------------
    def load_students(self):
        for i in self.tree_students.get_children():
            self.tree_students.delete(i)
        ftype,value=self.get_selected_filter()
        rows = fetch_students(ftype, value)
        needle = ""
        if hasattr(self, "students_search_var"):
            try:
                needle = str(self.students_search_var.get() or "")
            except Exception:
                needle = ""
        filtered = [r for r in rows if self._students_matches_search(r, needle)]

        for idx, r in enumerate(filtered, start=1):
            self.tree_students.insert(
                "",
                tk.END,
                values=(idx, r["StudentId"], r["Name"], r["Surname"], r["classId"]),
            )
        if needle.strip():
            self.students_status.set(
                _("المعروض: {shown} / {total}").format(shown=len(filtered), total=len(rows))
            )
        else:
            self.students_status.set(_("المعروض: {count}").format(count=len(filtered)))

    def sort_students(self,col):
        if col == "row":
            self.load_students()
            if hasattr(self, "_sort_reverse"):
                self._sort_reverse[col] = False
            return
        data=[(self.tree_students.set(k,col),k) for k in self.tree_students.get_children("")]
        reverse=getattr(self,"_sort_reverse",{}).get(col,False)
        if col=="id":
            try: data=[(int(v),k) for v,k in data]
            except: pass
        data.sort(reverse=reverse)
        for i,(v,k) in enumerate(data):
            self.tree_students.move(k,"",i)
            vals = list(self.tree_students.item(k, "values"))
            if vals:
                vals[0] = i + 1
                self.tree_students.item(k, values=vals)
        if not hasattr(self,"_sort_reverse"): self._sort_reverse={}
        self._sort_reverse[col]=not reverse
