# tabs/excusedAbsence_tab.py
import importlib
import tkinter as tk
from tkinter import ttk, messagebox
from tracemalloc import start
from center_window import safe_grab
from tooltip import ToolTip
from i18n import gettext_ as _, get_language

from services.excused_absence_service import (
    list_classes,
    list_students_for_class,
    list_session_types_for_class,
    list_session_types_any,
    list_excused_absences,
    list_sessions_for_excuse,
    add_excused_absences,
    delete_excused_absence,
)

DateEntry = None
try:
    DateEntry = importlib.import_module("tkcalendar").DateEntry  # 📅 مكتبة الكالندر
except ImportError:
    DateEntry = None

class ExcusedAbsenceTabMixin:
    def build_excused_tab(self):
        f = self.tab_excused
        is_rtl = (get_language() or "ar").lower().startswith("ar")
        side = "right" if is_rtl else "left"
        title_lbl = ttk.Label(f, text=_("📄 إدارة الغيابات المبررة"), font=("Tajawal", 16, "bold"))
        title_lbl.pack(pady=8)
        ToolTip(title_lbl, _("إدارة التبريرات وإضافة غيابات مبررة للطلبة"))

        scope_options = [
            ("student", _("طالب محدد")),
            ("class", _("قسم كامل")),
            ("all", _("كل الأقسام")),
        ]
        self._exc_scope_display = {key: display for key, display in scope_options}
        self._exc_scope_map = {display: key for key, display in scope_options}
        self._exc_all_label = _("الكل")

        # ===== شريط الفلترة =====
        top = ttk.Frame(f)
        top.pack(fill='x', padx=8, pady=4)

        ttk.Label(top, text=_("نطاق العرض")).pack(side=side, padx=(4, 2))
        self.exc_scope_var = tk.StringVar(value=scope_options[0][1])
        self.exc_scope_combo = ttk.Combobox(
            top,
            textvariable=self.exc_scope_var,
            state="readonly",
            width=16,
            values=[display for _, display in scope_options]
        )
        self.exc_scope_combo.pack(side=side, padx=(40, 2))
        self.exc_scope_combo.bind("<<ComboboxSelected>>", lambda e: self._on_exc_scope_change())
        ToolTip(self.exc_scope_combo, _("حدد نطاق العرض بين طالب واحد، قسم كامل أو جميع الأقسام"))

        ttk.Label(top, text=_("القسم")).pack(side=side, padx=(4, 2))
        self.exc_class_var = tk.StringVar()
        self.exc_class_combo = ttk.Combobox(top, textvariable=self.exc_class_var, state="readonly", width=15)
        self.exc_class_combo.pack(side=side, padx=(40, 2))
        self.exc_class_combo.bind("<<ComboboxSelected>>", lambda e: self._populate_exc_students())
        ToolTip(self.exc_class_combo, _("اختر القسم الذي تود مراجعة تبريراته"))

        ttk.Label(top, text=_("الطالب")).pack(side=side, padx=(4, 2))
        self.exc_student_var = tk.StringVar()
        self.exc_student_combo = ttk.Combobox(top, textvariable=self.exc_student_var, state="readonly", width=45)
        self.exc_student_combo.pack(side=side, padx=(40, 2))
        self.exc_student_combo.bind("<<ComboboxSelected>>", lambda e: self.load_excused())
        ToolTip(self.exc_student_combo, _("اختر الطالب الذي ترغب في مراجعة تبريراته"))

        ttk.Label(top, text=_("نوع الحصة")).pack(side=side, padx=(4, 2))
        self.exc_stype_var = tk.StringVar()
        self.exc_stype_combo = ttk.Combobox(top, textvariable=self.exc_stype_var, state="readonly", width=25)
        self.exc_stype_combo.pack(side=side, padx=(40, 2))
        self.exc_stype_combo.bind("<<ComboboxSelected>>", lambda e: self.load_excused())
        ToolTip(self.exc_stype_combo, _("حدد نوع الحصة لتصفية التبريرات"))

        # ===== جدول التبريرات =====
        cols = ("sid", "name", "surname", "class", "stype", "justification", "date", "stype_id")
        display_cols = ("sid", "name", "surname", "class", "stype", "justification", "date")
        self.tree_exc = ttk.Treeview(
            f,
            columns=cols,
            show="headings",
            height=12,
            displaycolumns=display_cols
        )

        headers = {
            "sid": _("رقم الطالب"),
            "name": _("اللقب"),
            "surname": _("الاسم"),
            "class": _("القسم"),
            "stype": _("نوع الحصة"),
            "justification": _("سبب التبرير"),
            "date": _("التاريخ"),
        }
        for c in display_cols:
            self.tree_exc.heading(c, text=headers[c])
            if c == "date":
                width = 130
            elif c == "stype":
                width = 180
            elif c == "justification":
                width = 220
            elif c == "class":
                width = 120
            else:
                width = 140
            self.tree_exc.column(c, anchor="center", width=width)

        self.tree_exc.heading("stype_id", text="")
        self.tree_exc.column("stype_id", width=0, stretch=False)

        self.tree_exc.pack(fill="both", expand=True, padx=8, pady=6)
        ToolTip(self.tree_exc, _("قائمة الغيابات المبررة مع عرض سبب التبرير إن وُجد"))

        # ===== أزرار الإجراءات =====
        actions = ttk.Frame(f)
        actions.pack(fill="x", padx=8, pady=6)

        btn_add = ttk.Button(actions, text=_("➕ إضافة"), command=self.add_excused)
        btn_add.pack(side="right", padx=4)
        ToolTip(btn_add, _("إضافة تبريرات جديدة للفترة المحددة"))

        btn_delete = ttk.Button(actions, text=_("🗑️ حذف"), command=self.delete_excused)
        btn_delete.pack(side="right", padx=4)
        ToolTip(btn_delete, _("إزالة التبرير المحدد من القائمة"))

        # تحميل الأقسام
        self._populate_exc_classes()

    # ---------------- تحميل الأقسام ----------------
    def _populate_exc_classes(self):
        try:
            rows = list_classes()
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{exc}").format(exc=exc))
            rows = []
        self.exc_class_combo["values"] = rows
        if rows:
            if getattr(self, "exc_scope_var", None) and self._get_exc_scope_key() == "all":
                self.exc_class_combo.set("")
            else:
                self.exc_class_combo.current(0)
            self._populate_exc_students()

    def _get_exc_scope_key(self):
        try:
            return self._exc_scope_map.get(self.exc_scope_var.get(), "student")
        except Exception:
            return "student"

    def _on_exc_scope_change(self):
        scope = self._get_exc_scope_key()

        if scope == "student":
            self.exc_class_combo.configure(state="readonly")
            if not self.exc_class_var.get().strip():
                values = self.exc_class_combo["values"]
                if values:
                    self.exc_class_combo.set(values[0])
            self.exc_student_combo.configure(state="readonly")
        elif scope == "class":
            self.exc_class_combo.configure(state="readonly")
            if not self.exc_class_var.get().strip():
                values = self.exc_class_combo["values"]
                if values:
                    self.exc_class_combo.set(values[0])
            self.exc_student_combo.set("")
            self.exc_student_combo.configure(state="disabled")
        else:  # all
            self.exc_class_combo.set("")
            self.exc_class_combo.configure(state="disabled")
            self.exc_student_combo.set("")
            self.exc_student_combo.configure(state="disabled")

        self._populate_exc_students()

    # ---------------- تحميل الطلبة + أنواع الحصص ----------------
    def _populate_exc_students(self):
        scope = self._get_exc_scope_key()

        # إعادة تعيين القوائم
        self.exc_student_combo.set('')
        self.exc_student_combo["values"] = []
        self.exc_stype_combo.set('')
        self.exc_stype_combo["values"] = []

        if scope == "all":
            try:
                stype_rows = list_session_types_any()
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{exc}").format(exc=exc))
                stype_rows = []
            stypes = [f"{r['id']} - {r['label']}" for r in stype_rows]
            all_label = self._exc_all_label
            values = [all_label] + stypes if stypes else [all_label]
            self.exc_stype_combo["values"] = values
            self.exc_stype_combo.current(0)
            self.load_excused()
            return

        cid = self.exc_class_var.get().strip()
        if not cid:
            self.tree_exc.delete(*self.tree_exc.get_children())
            return

        if scope == "student":
            try:
                rows = list_students_for_class(cid)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل الطلبة:\n{exc}").format(exc=exc))
                rows = []
            self.exc_student_combo["values"] = rows
            if rows:
                self.exc_student_combo.current(0)
        else:
            # قسم كامل → لا حاجة لقائمة الطلبة
            self.exc_student_combo.set("")

        # أنواع الحصص للقسم المختار
        try:
            stype_rows = list_session_types_for_class(cid)
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{exc}").format(exc=exc))
            stype_rows = []
        stype_rows_fmt = [f"{r['id']} - {r['label']}" for r in stype_rows]
        all_label = self._exc_all_label
        values = [all_label] + stype_rows_fmt if stype_rows_fmt else [all_label]
        self.exc_stype_combo["values"] = values
        if stype_rows and scope == "student":
            self.exc_stype_combo.current(1)
        else:
            self.exc_stype_combo.current(0)

        self.load_excused()

    # ---------------- عرض التبريرات ----------------
    def load_excused(self):
        self.tree_exc.delete(*self.tree_exc.get_children())
        scope = self._get_exc_scope_key()
        cid = (self.exc_class_var.get() or "").strip()
        stu = (self.exc_student_var.get() or "").strip()
        stype_val = (self.exc_stype_var.get() or "").strip()

        stype_id = None
        if stype_val and stype_val != self._exc_all_label:
            try:
                stype_id = int(stype_val.split(" - ")[0])
            except ValueError:
                stype_id = None

        where_clauses = []
        params = []

        if scope == "student":
            if not (cid and stu):
                return
            sid = (stu.split(" - ")[0] or "").strip()
            if not sid:
                return
            where_clauses.extend(["e.StudentId=?", "e.classId=?"])
            params.extend([sid, cid])
        elif scope == "class":
            if not cid:
                return
            where_clauses.append("e.classId=?")
            params.append(cid)
        else:  # كل الأقسام
            pass

        if stype_id:
            where_clauses.append("e.sessionTypeId=?")
            params.append(stype_id)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            WITH session_dates AS (
                SELECT sessionToken, date(MIN(SessionDate)) AS d
                FROM sessions
                GROUP BY sessionToken
            )
            SELECT
                st.StudentId AS sid,
                st.Name,
                st.Surname,
                st.classId AS classId,
                sd.d,
                e.sessionTypeId,
                COALESCE(e.justification_path, '') AS justification,
                COALESCE(stype.subject_code || '-' || stype.type, '') AS stype_label
            FROM excused_absences e
            JOIN students st ON st.StudentId = e.StudentId
            LEFT JOIN session_dates sd ON sd.sessionToken = e.sessionToken
            LEFT JOIN session_types stype ON stype.id = e.sessionTypeId
            {where_sql}
            ORDER BY sd.d, st.Name, st.Surname
        """

        try:
            rows = list_excused_absences(scope, cid or None, (stu.split(" - ")[0] if stu else None), stype_id)
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل التبريرات:\n{exc}").format(exc=exc))
            rows = []

        for r in rows:
            self.tree_exc.insert(
                "",
                tk.END,
                values=(
                    r["sid"],
                    r["Name"],
                    r["Surname"],
                    r["classId"],
                    r["stype_label"],
                    r["justification"],
                    r["d"],
                    str(r["sessionTypeId"] or "")
                )
            )
    # ---------------- إضافة تبريرات من فترة ----------------
    def add_excused(self):
        if DateEntry is None:
            messagebox.showerror(_("خطأ"), _("المكتبة tkcalendar غير مثبتة في هذه البيئة. ثبتها ثم حاول مجددًا."))
            return
        cid = self.exc_class_var.get().strip()
        stu = self.exc_student_var.get().strip()
        stype = self.exc_stype_var.get().strip()
        if not (cid and stu and stype):
            messagebox.showerror(_("خطأ"), _("اختر القسم والطالب ونوع الحصة أولا"))
            return

        sid = stu.split(" - ")[0]
        stype_id = int(stype.split(" - ")[0])

        win = tk.Toplevel(self.root)
        win.title(_("إضافة غياب مبرر"))
        win.transient(self.root)
        safe_grab(win)
        win.update_idletasks()
        W, H = 800, 500
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x, y = (sw // 2 - W // 2), (sh // 2 - H // 2)
        win.geometry(f"{W}x{H}+{x}+{y}")
   
        frm_dates = ttk.Frame(win)
        frm_dates.pack(pady=8)

        ttk.Label(frm_dates, text=_("من تاريخ")).grid(row=0, column=4, padx=1, sticky="e")
        start_var = tk.StringVar()
        start_cal = DateEntry(frm_dates, textvariable=start_var, date_pattern="yyyy-mm-dd")
        start_cal.grid(row=0, column=3, padx=1)
        ToolTip(start_cal, _("حدد تاريخ بداية الفترة المراد تبريرها"))

        ttk.Label(frm_dates, text="").grid(row=0, column=2, padx=20)

        ttk.Label(frm_dates, text=_("إلى تاريخ")).grid(row=0, column=1, padx=1, sticky="e")
        end_var = tk.StringVar()
        end_cal = DateEntry(frm_dates, textvariable=end_var, date_pattern="yyyy-mm-dd")
        end_cal.grid(row=0, column=0, padx=1)
        ToolTip(end_cal, _("حدد تاريخ نهاية الفترة المراد تبريرها"))

        cols = ("token", "date")
        tree = ttk.Treeview(win, columns=cols, show="headings", selectmode="extended", height=14)
        tree.heading("token", text=_("رمز الحصة"))
        tree.heading("date", text=_("التاريخ"))
        tree.pack(fill="both", expand=True, padx=10, pady=6)
        ToolTip(tree, _("اختَر الحصص المطلوب تبريرها من القائمة"))

        note_var = tk.StringVar()
        frm_note = ttk.Frame(win)
        frm_note.pack(fill="x", padx=10, pady=(0, 6))
        note_entry = ttk.Entry(frm_note, textvariable=note_var, width=72, justify="right")
        note_entry.pack(side="right", padx=6)
        ttk.Label(frm_note, text=_("سبب التبرير (اختياري)")).pack(side="right")
        ToolTip(note_entry, _("أدخل وصفًا مختصرًا مثل: غياب لسبب طبي (اتركه فارغًا إن لم يلزم)"))

        def search_sessions():
            tree.delete(*tree.get_children())
            start = start_var.get()
            end = end_var.get()
            if not (start and end):
                messagebox.showerror(_("خطأ"), _("حدد تاريخ البداية والنهاية"))
                return
            try:
                rows = list_sessions_for_excuse(cid, sid, stype_id, start, end)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر البحث عن الحصص:\n{exc}").format(exc=exc))
                rows = []
            for item in rows:
                tree.insert("", "end", values=(item["sessionToken"], item["date"]))

        btn_width = 9
        btn_search = ttk.Button(win, text=_("🔍 بحث"), command=search_sessions, width=btn_width)
        btn_search.pack(pady=4)
        ToolTip(btn_search, _("جلب الحصص المتاحة ضمن الفترة والتخصص المحددين"))

        def save_excuses():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning(_("تنبيه"), _("اختر حصة أو أكثر"))
                return
            if not messagebox.askyesno(_("تأكيد"), _("هل أنت متأكد من قبول التبريرات المحددة؟")):
                return
            note_text = note_var.get().strip()
            tokens = [tree.item(s, "values")[0] for s in sel]
            try:
                add_excused_absences(sid, stype_id, cid, note_text, tokens)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر حفظ التبريرات:\n{exc}").format(exc=exc))
                return
            messagebox.showinfo(_("تم"), _("تم حفظ التبريرات المحددة"))
            win.destroy()
            self.load_excused()

        ttk.Button(win, text=_("💾 حفظ"), command=save_excuses, width=btn_width).pack(pady=4)

        win.mainloop()

    # ---------------- حذف ----------------
    def delete_excused(self):
        sel = self.tree_exc.selection()
        if not sel:
            messagebox.showwarning(_("تنبيه"), _("اختر تبريراً من الجدول"))
            return
        vals = self.tree_exc.item(sel[0], "values")
        sid, name_val, surname_val, class_id, stype_label, justification, date, stype_id = vals
        sid = str(sid).strip()
        class_id = str(class_id).strip()
        stype_id = str(stype_id).strip()
        date = str(date).strip()

        if not sid:
            messagebox.showerror(_("خطأ"), _("تعذر تحديد الطالب لحذف التبرير."))
            return

        stype_id_int = None
        if stype_id:
            try:
                stype_id_int = int(stype_id)
            except ValueError:
                stype_id_int = None
        if stype_id_int is None:
            stype_sel = (self.exc_stype_var.get() or "")
            if stype_sel and stype_sel != self._exc_all_label:
                try:
                    stype_id_int = int(stype_sel.split(" - ")[0])
                except ValueError:
                    stype_id_int = None

        if not date:
            messagebox.showerror(_("خطأ"), _("تعذر تحديد تاريخ الجلسة للحذف."))
            return

        if messagebox.askyesno(_("تأكيد"), _("هل أنت متأكد من الحذف؟")):
            try:
                delete_excused_absence(sid, class_id or None, stype_id_int, date)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر الحذف:\n{exc}").format(exc=exc))
                return
            self.load_excused()
