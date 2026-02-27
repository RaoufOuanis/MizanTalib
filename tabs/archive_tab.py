# tabs/archive_tab.py
import importlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, timedelta
from db import get_conn
from services.archive_data_service import (
    fetch_archive_classes,
    fetch_sessions,
    fetch_session_details,
    fetch_session_attendance,
    fetch_students_for_class,
    search_student_sessions,
    fetch_class_statistics,
    fetch_student_summary,
    fetch_session_type_id,
)
from center_window import safe_grab
from tooltip import ToolTip
from i18n import gettext_ as _, get_language

class ArchiveTabMixin:
    def build_archive_tab(self):
        f = self.tab_archive
        is_rtl = (get_language() or "ar").lower().startswith("ar")
        side = "right" if is_rtl else "left"
        title_lbl = ttk.Label(f, text=_("📂 أرشيف الحصص"), font=("Tajawal", 16, "bold"))
        title_lbl.pack(pady=8)
        ToolTip(title_lbl, _("استعرض الحصص السابقة وبيانات المشاركة"))

        # ================== شريط الفلترة ==================
        filter_frame = ttk.Frame(f)
        filter_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(filter_frame, text=_("القسم")).pack(side=side, padx=4)
        self.archive_class_var = tk.StringVar()
        self.archive_class_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.archive_class_var,
            state="readonly",
            width=18,
        )
        self.archive_class_combo.pack(side=side)
        ToolTip(self.archive_class_combo, _("اختر القسم لعرض حصصه المؤرشفة"))

        btn_view = ttk.Button(filter_frame, text=_("🔍 عرض"), command=self.load_sessions_list)
        btn_view.pack(side=side, padx=6)
        ToolTip(btn_view, _("تطبيق الفلترة وعرض قائمة الحصص"))

        spacer = tk.Frame(filter_frame, width=100)
        spacer.pack(side=side)
        spacer.pack_propagate(False)

        # فلاتر بحث عن طالب
        self.search_id_var = tk.StringVar()
        self.search_surname_var = tk.StringVar()
        self.search_name_var = tk.StringVar()

        ttk.Label(filter_frame, text=_("الرقم")).pack(side=side, padx=2)
        entry_id = ttk.Entry(filter_frame, textvariable=self.search_id_var, width=12, justify=("right" if is_rtl else "left"))
        entry_id.pack(side=side)
        ToolTip(entry_id, _("اكتب رقم الطالب للبحث السريع"))

        ttk.Label(filter_frame, text=_("اللقب")).pack(side=side, padx=2)
        entry_surname = ttk.Entry(filter_frame, textvariable=self.search_name_var, width=14, justify=("right" if is_rtl else "left"))
        entry_surname.pack(side=side)
        ToolTip(entry_surname, _("فلترة الحصص حسب لقب الطالب"))

        ttk.Label(filter_frame, text=_("الإسم")).pack(side=side, padx=2)
        entry_name = ttk.Entry(filter_frame, textvariable=self.search_surname_var, width=14, justify=("right" if is_rtl else "left"))
        entry_name.pack(side=side)
        ToolTip(entry_name, _("فلترة الحصص حسب اسم الطالب"))

        btn_search = ttk.Button(filter_frame, text=_("✅ البحث عن الطالب"), command=self.apply_student_filter)
        btn_search.pack(side=side, padx=6)
        ToolTip(btn_search, _("تطبيق معايير البحث المحددة لتصفية النتائج"))

        # ================== جدول الحصص ==================
        paned = ttk.Panedwindow(f, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        sessions_frame = ttk.Frame(paned)
        sessions_frame.columnconfigure(0, weight=1)
        paned.add(sessions_frame, weight=1)

        self.tree_sessions = ttk.Treeview(
            sessions_frame,
            columns=("index", "token", "date", "class", "stype", "count"),
            show="headings",
            height=7,
        )
        headers = [
            ("index", "#"),
            ("token", _("رمز الحصة")),
            ("date", _("التاريخ")),
            ("class", _("القسم")),
            ("stype", _("نوع الحصة")),
            ("count", _("عدد الطلبة")),
        ]
        for col, text in headers:
            self.tree_sessions.heading(col, text=text, command=lambda c=col: self._on_sessions_header_click(c))

        self.tree_sessions.column("index", width=60, anchor="center")
        self.tree_sessions.column("token", width=140, anchor="center")
        self.tree_sessions.column("date", width=160, anchor="center")
        self.tree_sessions.column("class", width=120, anchor="center")
        self.tree_sessions.column("stype", width=160, anchor="center")
        self.tree_sessions.column("count", width=100, anchor="center")

        self._sessions_col_index = {
            "token": 0,
            "date": 1,
            "class": 2,
            "stype": 3,
            "count": 4,
        }
        self._sessions_sort_col = "date"
        self._sessions_sort_reverse = True  # افتراضيًا حسب التاريخ تنازليًا كما في الاستعلام
        self._sessions_rows = []

        sessions_scroll = ttk.Scrollbar(sessions_frame, orient="vertical", command=self.tree_sessions.yview)
        self.tree_sessions.configure(yscrollcommand=sessions_scroll.set)

        self.tree_sessions.grid(row=0, column=0, sticky="nsew")
        sessions_scroll.grid(row=0, column=1, sticky="ns")
        sessions_frame.rowconfigure(0, weight=1)
        ToolTip(self.tree_sessions, _("انقر على حصة لعرض تفاصيلها الكاملة"))
        self.tree_sessions.bind("<<TreeviewSelect>>", self.show_session_details)

        # ================== جدول تفاصيل الجلسة ==================
        details_frame = ttk.Frame(paned)
        paned.add(details_frame, weight=2)

        self.tree_details = ttk.Treeview(
            details_frame,
            columns=("row", "id", "name", "surname", "class", "stype", "part"),
            show="headings",
            selectmode="browse",
        )
        headers2 = [
            ("row", "#"),
            ("id", _("الرقم")),
            ("name", _("اللقب")),
            ("surname", _("الإسم")),
            ("class", _("القسم")),
            ("stype", _("نوع الحصة")),
            ("part", _("المشاركة")),
        ]
        for col, text in headers2:
            if col == "row":
                self.tree_details.heading(col, text=text)
            else:
                self.tree_details.heading(col, text=text, command=lambda c=col: self._on_details_header_click(c))

        self.tree_details.column("row", width=60, anchor="center")
        self.tree_details.column("id", width=100, anchor="center")
        self.tree_details.column("name", width=150, anchor="center")
        self.tree_details.column("surname", width=150, anchor="center")
        self.tree_details.column("class", width=120, anchor="center")
        self.tree_details.column("stype", width=160, anchor="center")
        self.tree_details.column("part", width=100, anchor="center")

        self._details_col_index = {
            "id": 0,
            "name": 1,
            "surname": 2,
            "class": 3,
            "stype": 4,
            "part": 5,
        }
        self._details_sort_col = "name"
        self._details_sort_reverse = False
        self._details_rows = []

        details_scroll = ttk.Scrollbar(details_frame, orient="vertical", command=self.tree_details.yview)
        self.tree_details.configure(yscrollcommand=details_scroll.set)

        self.tree_details.grid(row=0, column=0, sticky="nsew")
        details_scroll.grid(row=0, column=1, sticky="ns")
        details_frame.rowconfigure(0, weight=1)
        details_frame.columnconfigure(0, weight=1)
        ToolTip(self.tree_details, _("قائمة الطلبة المشاركين وتقييماتهم في الحصة المحددة"))

        # دبل كليك → إحصائيات طالب
        self.tree_details.bind("<Double-1>", lambda e: self.show_student_statistics())

        # ================== أزرار الإجراءات ==================
        actions = ttk.Frame(f)
        actions.pack(fill="x", padx=8, pady=6)
        btn_export = ttk.Button(actions, text=_("⬇️ تصدير إلى Excel"), command=self.export_archive_to_excel)
        btn_export.pack(side="right", padx=4)
        ToolTip(btn_export, _("حفظ نتائج الحصة الحالية في ملف Excel"))

        btn_stats = ttk.Button(actions, text=_("📊 إحصائيات الأقسام"), command=self.show_statistics)
        btn_stats.pack(side="right", padx=4)
        ToolTip(btn_stats, _("عرض مخطط يوضح توزيع الحضور حسب الأقسام"))

        btn_student_stats = ttk.Button(actions, text=_("👤 إحصائيات طالب"), command=self.show_student_statistics)
        btn_student_stats.pack(side="right", padx=4)
        ToolTip(btn_student_stats, _("إظهار أداء طالب محدد عبر الجلسات"))

        btn_edit_stype = ttk.Button(actions, text=_("✏️ تصحيح نوع الحصة"), command=self.edit_session_type)
        btn_edit_stype.pack(side="right", padx=4)
        ToolTip(btn_edit_stype, _("إذا تم حفظ الحصة بمعلومات خاطئة يمكن التصحيح من هنا (تحتاج كلمة السر الإدارية)"))

        # زر تعديل الحضور والمشاركة للجلسة المؤرشفة
        btn_edit_att = ttk.Button(actions, text=_("🛠 تعديل الحضور و المشاركة"), command=self.edit_session_attendance)
        btn_edit_att.pack(side="right", padx=4)
        ToolTip(btn_edit_att, _("تعديل قائمة الطلبة ودرجات المشاركة للحصة المحددة (يتطلب كلمة السر الإدارية)"))

        # تحميل الأقسام
        self.load_classes_archive()

    # ---------------- تحميل الأقسام ----------------
    def load_classes_archive(self):
        try:
            classes = fetch_archive_classes()
            all_option = _("الكل")
            self.archive_class_combo["values"] = [all_option] + classes
            self.archive_class_combo.current(0)
            self.load_sessions_list()
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{error}").format(error=e))

    # ---------------- تحميل قائمة الحصص ----------------
    def load_sessions_list(self):
        class_id = self.archive_class_var.get()
        try:
            all_option = _("الكل")
            effective_class = None if not class_id or class_id == all_option else class_id
            rows = fetch_sessions(effective_class)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الحصص:\n{error}").format(error=e))
            return

        self._sessions_rows = rows
        self._sessions_sort_col = "date"
        self._sessions_sort_reverse = True
        # ترتيب افتراضي حسب التاريخ (تنازلي كما في الاستعلام)
        self._sort_sessions("date", toggle=False)
        self._details_rows = []
        self.tree_details.delete(*self.tree_details.get_children())

    # ---------------- عرض تفاصيل الجلسة ----------------
    def show_session_details(self, event=None):
        sel = self.tree_sessions.selection()
        if not sel: return
        values = self.tree_sessions.item(sel[0], "values")
        if not values or len(values) < 6:
            return
        _, token, _, class_id, stype, _ = values
        try:
            rows = fetch_session_details(token, class_id, stype)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل تفاصيل الحصة:\n{error}").format(error=e))
            return

        self._details_rows = rows
        self._details_sort_col = "name"
        self._details_sort_reverse = False
        self._sort_details("name", toggle=False)

    # ---------------- تعديل نوع الحصة لجلسة مؤرشفة ----------------
    def edit_session_type(self):
        if not hasattr(self, "require_admin_password") or not self.require_admin_password():
            return
        sel = self.tree_sessions.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "اختر حصة من القائمة أولًا.")
            return
        values = self.tree_sessions.item(sel[0], "values")
        if not values or len(values) < 6:
            messagebox.showwarning(_("تنبيه"), _("تعذر قراءة بيانات الحصة المحددة."))
            return
        _, token, _, class_id, stype_label, _ = values

        # Charger les types de séance
        try:
            conn = get_conn(); cur = conn.cursor()
            cur.execute("SELECT id, subject_code || '-' || type AS label FROM session_types ORDER BY subject_code, type")
            types = cur.fetchall(); conn.close()
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{error}").format(error=e))
            return
        if not types:
            messagebox.showinfo(_("لا يوجد"), _("لا توجد أنواع حصص معرفة في النظام."))
            return

        # Charger les classes
        try:
            classes = fetch_archive_classes()
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{error}").format(error=e))
            return
        if not classes:
            messagebox.showinfo(_("لا يوجد"), _("لا توجد أقسام معرفة في النظام."))
            return

        win = tk.Toplevel(self.root)
        win.title("تعديل نوع الحصة/القسم — أرشيف")
        self.center_window(win, 480, 200)
        win.transient(self.root); safe_grab(win)

        ttk.Label(win, text="رمز الحصة: {token}".format(token=token)).pack(pady=(8, 4))

        # Combobox pour le type de séance
        stype_map = {str(r['id']): r['label'] for r in types}
        combo_type = ttk.Combobox(win, values=[v for v in stype_map.values()], state='readonly', width=40)
        try:
            combo_type.set(stype_label)
        except Exception:
            combo_type.current(0)
        combo_type.pack(pady=6)

        # Combobox pour la classe
        ttk.Label(win, text="القسم الجديد:").pack(pady=(4, 0))
        combo_class = ttk.Combobox(win, values=classes, state='readonly', width=30)
        try:
            combo_class.set(class_id)
        except Exception:
            combo_class.current(0)
        combo_class.pack(pady=6)

        def do_update():
            new_label = combo_type.get().strip()
            new_class = combo_class.get().strip()
            if not new_label:
                messagebox.showwarning(_("تنبيه"), _("اختر نوع الحصة.")); return
            if not new_class:
                messagebox.showwarning(_("تنبيه"), _("اختر القسم الجديد.")); return
            # find id for label
            new_id = None
            for r in types:
                if r['label'] == new_label:
                    new_id = r['id']; break
            if new_id is None:
                messagebox.showerror(_("خطأ"), _("نوع الحصة غير موجود.")); return

            try:
                conn = get_conn(); cur = conn.cursor()
                # Update all sessions rows that match the sessionToken and classId
                cur.execute("UPDATE sessions SET sessionTypeId=?, classId=? WHERE sessionToken=? AND classId=?",
                            (new_id, new_class, token, class_id))
                conn.commit(); conn.close()
            except Exception as e:
                try:
                    conn.rollback(); conn.close()
                except Exception:
                    pass
                messagebox.showerror("خطأ", "تعذر حفظ التعديل:\n{error}").format(error=e)
                return

            win.destroy()
            messagebox.showinfo("تم", "تم تعديل نوع الحصة/القسم بنجاح.")
            # refresh view
            try:
                self.load_sessions_list();
                # re-select the updated token if present
                for iid in self.tree_sessions.get_children():
                    vals = self.tree_sessions.item(iid, 'values')
                    if vals and len(vals) >= 5 and vals[1] == token and vals[3] == new_class:
                        self.tree_sessions.selection_set(iid); self.tree_sessions.see(iid); break
            except Exception:
                pass

        btn = ttk.Button(win, text="💾 حفظ التعديل", command=do_update)
        btn.pack(pady=(6, 8))

    # ---------------- تعديل حضور جلسة مؤرشفة ----------------
    def edit_session_attendance(self):
        if not hasattr(self, "require_admin_password") or not self.require_admin_password():
            return
        sel = self.tree_sessions.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "اختر حصة من القائمة أولًا.")
            return
        values = self.tree_sessions.item(sel[0], "values")
        if not values or len(values) < 6:
            messagebox.showwarning("تنبيه", _("تعذر قراءة بيانات الحصة المحددة."))
            return
        _, token, _, class_id, stype_label, _ = values

        # جلب sessionTypeId الأصلي (قد نحتاجه عند الإضافة)
        try:
            stype_id = fetch_session_type_id(token, class_id)
        except Exception:
            stype_id = None

        import gettext
        _ = gettext.gettext

        win = tk.Toplevel(self.root)
        ts = gettext.gettext
        win.title(ts("تعديل الحضور - حصة سابقة"))
        self.center_window(win, 860, 520)
        win.transient(self.root); safe_grab(win)

        header = ttk.Frame(win); header.pack(fill="x", padx=8, pady=6)
        ttk.Label(header, text=_("رمز الحصة: {token}").format(token=token), font=("Tajawal", 11, "bold")).pack(side="right", padx=6)
        ttk.Label(header, text=_("القسم: {class_id}").format(class_id=class_id)).pack(side="right", padx=6)
        ttk.Label(header, text=_("نوع الحصة: {stype_label}").format(stype_label=stype_label)).pack(side="right", padx=6)

        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=8, pady=4)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        tree = ttk.Treeview(
            container,
            columns=("id", "name", "surname", "part"),
            show="headings",
            selectmode="browse",
        )
        for col, text in [("id", _("الرقم")), ("name", _("اللقب")), ("surname", _("الإسم")), ("part", _("المشاركة"))]:
            tree.heading(col, text=text)
            tree.column(col, anchor="center", width=140 if col != "part" else 90)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")
        ToolTip(tree, _("انقر مرتين على خانة المشاركة لتعديل القيمة"))

        # تحميل الحضور الحالي
        try:
            rows = fetch_session_attendance(token, class_id, stype_label)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الحضور:\n{error}").format(error=e))
            win.destroy(); return

        original_dates = {}
        original_presence = {}
        default_session_date = None

        for r in rows:
            sid = str(r["StudentId"])
            session_date = r.get("session_date")
            if session_date and default_session_date is None:
                default_session_date = session_date
            original_dates[sid] = session_date
            original_presence[sid] = r.get("presence", 1) if r.get("presence") is not None else 1
            tree.insert("", "end", values=(sid, r["nm"], r["sur"], r.get("participation")))

        if default_session_date is None:
            default_session_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # أدوات إضافة / حذف
        tools = ttk.Frame(win)
        tools.pack(fill="x", padx=8, pady=6)

        def add_student_dialog():
            try:
                candidates = fetch_students_for_class(class_id)
            except Exception as e:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل قائمة الطلاب:\n{error}").format(error=e))
                return

            current_ids = {str(tree.item(iid, "values")[0]) for iid in tree.get_children()}
            available = [row for row in candidates if str(row["sid"]) not in current_ids]

            if not available:
                messagebox.showinfo(_("تنبيه"), _("كل الطلاب مسجلون بالفعل في هذه الحصة."))
                return

            choices = [f"{row['sid']} - {row['nm']} {row['sur']}" for row in available]
            mapping = {choice: row for choice, row in zip(choices, available)}

            dlg = tk.Toplevel(win); dlg.title(_("إضافة طالب"))
            self.center_window(dlg, 420, 200); dlg.transient(win); safe_grab(dlg); dlg.resizable(False, False)

            ttk.Label(dlg, text=_("اختر الطالب")).pack(pady=(10, 4))
            choice_var = tk.StringVar()
            combo = ttk.Combobox(dlg, textvariable=choice_var, values=choices, state="readonly")
            combo.pack(fill="x", padx=16)
            combo.current(0)

            ttk.Label(dlg, text=_("قيمة المشاركة (اختياري)")).pack(pady=(12, 4))
            part_var = tk.StringVar()
            part_entry = ttk.Entry(dlg, textvariable=part_var, justify="center")
            part_entry.pack(pady=(0, 12))

            def do_add():
                choice = choice_var.get()
                if not choice:
                    messagebox.showwarning(_("تنبيه"), _("اختر الطالب أولًا."), parent=dlg)
                    return
                student = mapping.get(choice)
                if not student:
                    messagebox.showerror(_("خطأ"), _("تعذر قراءة بيانات الطالب المحدد."), parent=dlg)
                    return
                sid = str(student["sid"])
                nm = student["nm"]
                sur = student["sur"]
                if any(str(tree.item(iid, "values")[0]) == sid for iid in tree.get_children()):
                    messagebox.showwarning(_("تنبيه"), _("الطالب موجود مسبقًا في هذه الحصة."), parent=dlg)
                    return
                try:
                    part_val = float(part_var.get().strip()) if part_var.get().strip() else 0.0
                except ValueError:
                    messagebox.showerror(_("خطأ"), _("قيمة المشاركة يجب أن تكون رقمية."), parent=dlg)
                    return
                tree.insert("", "end", values=(sid, nm, sur, part_val))
                dlg.destroy()

            ttk.Button(dlg, text=_("➕ إضافة"), command=do_add).pack(pady=(0, 10))
            combo.focus_set()
            dlg.bind("<Return>", lambda _=None: do_add())

        def delete_selected():
            sel_iid = tree.selection()
            if not sel_iid:
                messagebox.showwarning(_("تنبيه"), _("اختر سطرًا"))
                return
            if messagebox.askyesno(_("تأكيد"), _("حذف الطالب من هذه الحصة")):
                tree.delete(sel_iid[0])

        def edit_participation(event=None):
            sel_iid = tree.selection()
            if not sel_iid:
                return
            vals = list(tree.item(sel_iid[0], "values"))
            try:
                new_val = simpledialog.askstring(_("تعديل المشاركة"), _("القيمة الحالية: {value}").format(value=vals[3]), parent=win)
            except Exception:
                new_val = None
            if new_val is None:
                return
            try:
                fval = float(new_val.strip())
            except ValueError:
                messagebox.showerror(_("خطأ"), _("قيمة غير صالحة"))
                return
            vals[3] = fval
            tree.item(sel_iid[0], values=vals)

        tree.bind("<Double-1>", edit_participation)

        ttk.Button(tools, text=_("➕ إضافة طالب"), command=add_student_dialog).pack(side="right", padx=4)
        ttk.Button(tools, text=_("🗑 حذف المحدد"), command=delete_selected).pack(side="right", padx=4)
        ttk.Button(tools, text=_("✏️ تعديل المشاركة"), command=edit_participation).pack(side="right", padx=4)

        # حفظ التعديلات
        base_stype_id = stype_id

        def save_changes():
            # إعادة كتابة صفوف الجلسة (نفس token + class + نفس نوع الحصة)
            try:
                conn = get_conn(); cur = conn.cursor()
                # احصل على sessionTypeId مرة أخرى إذا مفقود
                stype_for_insert = base_stype_id
                if stype_for_insert is None:
                    cur.execute("""SELECT st.id FROM sessions s LEFT JOIN session_types st ON s.sessionTypeId=st.id
                                   WHERE s.sessionToken=? AND s.classId=? LIMIT 1""", (token, class_id))
                    rtt = cur.fetchone(); stype_for_insert = rtt["id"] if rtt else None
                # حذف الحالي
                cur.execute("DELETE FROM sessions WHERE sessionToken=? AND classId=?", (token, class_id))
                # إدخال جديد
                for iid in tree.get_children():
                    sid, nm, sur, part = tree.item(iid, "values")
                    sid_str = str(sid)
                    try:
                        part_val = float(part) if str(part).strip() else 0.0
                    except ValueError:
                        part_val = 0.0
                    session_date = original_dates.get(sid_str) or default_session_date
                    if not session_date:
                        session_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    presence_val = original_presence.get(sid_str, 1)
                    cur.execute("""
                        INSERT INTO sessions (sessionToken, StudentId, presence, participation, SessionDate, classId, sessionTypeId)
                        VALUES (?,?,?,?, ?, ?, ?)
                    """, (token, sid_str, presence_val, part_val, session_date, class_id, stype_for_insert))
                conn.commit(); conn.close()
            except Exception as e:
                try:
                    conn.rollback(); conn.close()
                except Exception:
                    pass
                messagebox.showerror(_("خطأ"), _("تعذر حفظ التعديلات:\n{error}").format(error=e))
                return
            messagebox.showinfo(_("تم"), _("تم حفظ التعديلات."))
            win.destroy()
            # تحديث العرض
            try:
                self.load_sessions_list()
            except Exception:
                pass

        ttk.Button(tools, text=_("💾 حفظ التعديلات"), command=save_changes).pack(side="left", padx=4)
        ttk.Button(tools, text=_("✖ إغلاق"), command=win.destroy).pack(side="left", padx=4)

    # ---------------- ترتيب جدول الحصص ----------------
    def _on_sessions_header_click(self, col):
        if col == "index":
            return
        self._sort_sessions(col)

    def _sort_sessions(self, col, toggle=True):
        if not hasattr(self, "_sessions_rows") or not self._sessions_rows:
            return

        if toggle:
            if self._sessions_sort_col == col:
                self._sessions_sort_reverse = not self._sessions_sort_reverse
            else:
                self._sessions_sort_col = col
                self._sessions_sort_reverse = False
        else:
            self._sessions_sort_col = col

        idx = self._sessions_col_index.get(self._sessions_sort_col, 1)

        def sort_key(row):
            val = row[idx]
            try:
                num = float(val)
                return (0, num)
            except (TypeError, ValueError):
                return (1, str(val).lower())

        sorted_rows = sorted(self._sessions_rows, key=sort_key, reverse=self._sessions_sort_reverse)
        self._render_sessions_rows(sorted_rows)

    def _render_sessions_rows(self, rows):
        self.tree_sessions.delete(*self.tree_sessions.get_children())
        for idx, row in enumerate(rows, start=1):
            display = list(row)
            if len(display) > 1:
                display[1] = self._format_session_datetime(display[1])
            self.tree_sessions.insert("", "end", values=[idx] + display)

    # ---------------- ترتيب جدول تفاصيل الجلسة ----------------
    def _on_details_header_click(self, col):
        if col == "row":
            return
        self._sort_details(col)

    def _sort_details(self, col, toggle=True):
        if not hasattr(self, "_details_rows") or not self._details_rows:
            return

        if toggle:
            if self._details_sort_col == col:
                self._details_sort_reverse = not self._details_sort_reverse
            else:
                self._details_sort_col = col
                self._details_sort_reverse = False
        else:
            self._details_sort_col = col
            self._details_sort_reverse = False
        idx = self._details_col_index.get(self._details_sort_col, 0)

        def sort_key(row):
            if idx >= len(row):
                return ""
            val = row[idx]
            if isinstance(val, (int, float)):
                return val
            try:
                if self._details_sort_col in {"part"}:
                    return float(val)
            except (TypeError, ValueError):
                pass
            return str(val).lower()

        sorted_rows = sorted(self._details_rows, key=sort_key, reverse=self._details_sort_reverse)
        self._render_details_rows(sorted_rows)
        sorted_rows = sorted(self._details_rows, key=sort_key, reverse=self._details_sort_reverse)
        self._render_details_rows(sorted_rows)

    def _render_details_rows(self, rows):
        self.tree_details.delete(*self.tree_details.get_children())
        for idx, row in enumerate(rows, start=1):
            self.tree_details.insert("", "end", values=(idx,) + tuple(row))

    # ---------------- فلترة عامة للطلاب ----------------
    def apply_student_filter(self):
        needle_id = self.search_id_var.get().strip()
        needle_name = self.search_name_var.get().strip()
        needle_surname = self.search_surname_var.get().strip()

        if not (needle_id or needle_name or needle_surname):
            messagebox.showwarning(_("تنبيه"), _("أدخل رقم أو اسم أو لقب للبحث."))
            return

        try:
            rows = search_student_sessions(needle_id, needle_name, needle_surname)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تنفيذ البحث:\n{error}").format(error=e))
            return

        self._details_rows = rows
        if self._details_rows:
            self._details_sort_col = "name"
            self._details_sort_reverse = False
            self._sort_details("name", toggle=False)
        else:
            self._details_rows = []
            self._render_details_rows([])

    # ---------------- إحصائيات الأقسام ----------------
    def show_statistics(self):
        try:
            rows, session_dates = fetch_class_statistics()
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر حساب الإحصائيات:\n{error}").format(error=e))
            return

        win = tk.Toplevel(self.root)
        win.title(_("إحصائيات الأقسام"))
        self.center_window(win, 860, 420)
        ttk.Label(
            win,
            text=_("📊 ملخص الإحصائيات حسب القسم ونوع الحصة"),
            font=("Tajawal", 14, "bold"),
        ).pack(pady=6)
        tree = ttk.Treeview(
            win,
            columns=("class", "stype", "sessions", "students", "total_part"),
            show="headings",
            height=12,
        )
        headers = [
            ("class", _("القسم")),
            ("stype", _("نوع الحصة")),
            ("sessions", _("عدد الجلسات")),
            ("students", _("عدد الطلبة")),
            ("total_part", _("إجمالي المشاركة")),
        ]
        for col, text in headers:
            tree.heading(col, text=text)
            tree.column(col, anchor="center", width=160)
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        for r in rows:
            tree.insert(
                "",
                "end",
                values=(
                    r["classId"],
                    r["session_label"],
                    r["sessions"],
                    r["students"],
                    r["total_part"] or 0,
                ),
            )

        total_sessions = sum((r["sessions"] or 0) for r in rows)
        week_starts = set()

        def _parse_session_datetime(value):
            if not value:
                return None
            if isinstance(value, datetime):
                return value
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
                try:
                    return datetime.strptime(str(value), fmt)
                except ValueError:
                    continue
            return None

        for row in session_dates:
            dt = _parse_session_datetime(row["session_date"])
            if not dt:
                continue
            d = dt.date()
            offset = (d.weekday() - 5) % 7
            week_starts.add(d - timedelta(days=offset))

        total_weeks = len(week_starts)
        sessions_per_week = total_sessions / total_weeks if total_weeks else 0.0

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=8, pady=(6, 4))
        summary_frame = ttk.Frame(win, padding=(12, 6))
        summary_frame.pack(fill="x", padx=8, pady=(0, 8))
        summary_text = _(
            "إجمالي الحصص: {total_sessions}  —  عدد الأسابيع: {total_weeks}  —  معدل الحصص لكل أسبوع: {sessions_per_week:.2f}"
        ).format(
            total_sessions=total_sessions,
            total_weeks=total_weeks,
            sessions_per_week=sessions_per_week,
        )
        ttk.Label(summary_frame, text=summary_text, font=("Segoe UI", 11, "bold"), anchor="center").pack()

    # ---------------- إحصائيات طالب ----------------
    def show_student_statistics(self):
        sel = self.tree_details.selection()
        if not sel:
            messagebox.showwarning(_("تنبيه"), _("اختر طالبًا أولاً من الجدول."))
            return
        vals = self.tree_details.item(sel[0], "values")
        if not vals or len(vals) < 2:
            messagebox.showerror(_("خطأ"), _("تعذر قراءة بيانات الطالب المحدد."))
            return
        student_id = str(vals[1])

        try:
            summary, details = fetch_student_summary(student_id)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر جلب الإحصائيات:\n{error}").format(error=e))
            return

        if not summary:
            messagebox.showinfo(_("لا يوجد"), _("لا توجد سجلات لهذا الطالب."))
            return

        win = tk.Toplevel(self.root)
        win.title(_("إحصائيات الطالب"))
        self.center_window(win, 900, 520)
        ttk.Label(
            win,
            text=_("👤 {name} {surname} ({student_id})").format(
                name=summary[0]["Name"],
                surname=summary[0]["Surname"],
                student_id=summary[0]["StudentId"],
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
            first_fmt = self._format_session_datetime(r["first_session"])
            last_fmt = self._format_session_datetime(r["last_session"])
            tree_summary.insert(
                "",
                "end",
                values=(
                    r["session_label"],
                    r["total_sessions"],
                    r["total_part"],
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
            date_fmt = self._format_session_datetime(r["SessionDate"])
            tree_details.insert(
                "",
                "end",
                values=(
                    date_fmt,
                    r["sessionToken"],
                    r["classId"],
                    r["session_label"],
                    r["participation"],
                ),
            )

    # ---------------- تصدير Excel ----------------
    def export_archive_to_excel(self):
        sel = self.tree_sessions.selection()
        if not sel:
            messagebox.showwarning("تنبيه", "يرجى اختيار حصة من القائمة أولاً.")
            return
        values = self.tree_sessions.item(sel[0], "values")
        if not values or len(values) < 6:
            messagebox.showwarning("تنبيه", "تعذر قراءة بيانات الحصة المحددة.")
            return
        _, token, _, class_id, stype_label, _ = values

        if not messagebox.askyesno("تأكيد", "ستقوم بتصدير قائمة الحضور للحصة المختارة، هل ترغب في المواصلة؟"):
            return

        try:
            openpyxl = importlib.import_module("openpyxl")
            Workbook = openpyxl.Workbook
        except ImportError:
            messagebox.showerror(_("خطأ"), _("المكتبة openpyxl غير مثبتة في هذه البيئة.\nثبت الحزمة ثم حاول مجددًا."))
            return
        except AttributeError:
            messagebox.showerror(_("خطأ"), _("تعذر الوصول إلى Workbook داخل openpyxl."))
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                 filetypes=[("Excel files","*.xlsx")])
        if not file_path:
            return
        try:
            wb = Workbook(); ws = wb.active
            ws.title = "Archive"
            ws.append(["StudentId","Surname","Name","Class","SessionType","Participation"])
            conn = get_conn(); cur = conn.cursor()
            cur.execute("""
                SELECT st.StudentId AS sid, st.Surname AS sur, st.Name AS nm, st.classId AS cls,
                       stypes.subject_code || '-' || stypes.type AS session_label,
                       s.participation AS participation
                FROM sessions s
                LEFT JOIN students st ON s.StudentId=st.StudentId
                LEFT JOIN session_types stypes ON s.sessionTypeId=stypes.id
                WHERE s.sessionToken=? AND s.classId=?
                ORDER BY st.StudentId
            """, (token, class_id))
            rows = cur.fetchall(); conn.close()
            for r in rows:
                ws.append([r["sid"], r["sur"], r["nm"], r["cls"],
                           r["session_label"], r["participation"] or 0])
            wb.save(file_path)
            messagebox.showinfo("تم", "تم تصدير البيانات بنجاح")
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذر التصدير:\n{e}")

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
                except ValueError:
                    continue
            if dt is None:
                return str(value)
        return dt.strftime("%d/%m/%Y %H:%M")

    # ---------------- دالة مساعدة لسنترة النوافذ ----------------
    def center_window(self, win, w, h):
        win.update_idletasks()
        sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
        x = (sw // 2) - (w // 2); y = (sh // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
