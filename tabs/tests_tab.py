# tabs/tests_tab.py
import importlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from center_window import safe_grab
from i18n import gettext_ as _, get_language
from tooltip import ToolTip

from services.test_service import (
    list_class_ids,
    list_tests,
    list_session_type_labels_with_ids,
    fetch_tests_for_class,
    fetch_test_for_edit,
    create_tests,
    update_test as service_update_test,
    delete_test as service_delete_test,
    list_test_results,
    update_degree as service_update_degree,
    import_degrees_for_test as service_import_degrees_for_test,
)


ALL_CLASSES_LABEL = _("📋 كل الأقسام")
ALL_TESTS_LABEL = _("📋 كل الاختبارات")
NEW_TEST_LABEL = _("— إنشاء جديد —")


_pd_module = None


def _get_pandas_module():
    global _pd_module
    if _pd_module is None:
        try:
            _pd_module = importlib.import_module("pandas")
        except ImportError:
            _pd_module = None
    return _pd_module


class TestsTabMixin:
    TEST_TYPE_OPTIONS = ("استجواب", "واجب", "تقديم", "امتحان عن بعد")
    TEST_TYPE_RENAMES = {
        "امتحان جزئي": "تقديم",
        "امتحان نهائي": "امتحان عن بعد",
    }

    def _center(self, win, w=480, h=520):
        try:
            win.update_idletasks()
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            x, y = (sw - w) // 2, (sh - h) // 2
            win.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def build_tests_tab(self):
        frame = self.tab_tests

        is_rtl = (get_language() or "ar").lower().startswith("ar")
        side = "right" if is_rtl else "left"

        title_lbl = ttk.Label(frame, text=_(" إدارة الاختبارات"), font=("Tajawal", 16, "bold"))
        title_lbl.pack(pady=8)
        ToolTip(title_lbl, _("شاشة إدارة الاختبارات وعرض نتائج الطلبة"))

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=4)

        def add_spacer(width):
            spacer = ttk.Frame(toolbar, width=width)
            spacer.pack(side=side)
            spacer.pack_propagate(False)

        add_spacer(25)
        manage_btn = ttk.Button(toolbar, text=_("➕ إضافة / ✏️ تعديل"), command=self.open_test_manager_dialog)
        manage_btn.pack(side=side)
        ToolTip(manage_btn, _("فتح نافذة لإضافة اختبار جديد أو تعديل/حذف اختبار موجود"))

        add_spacer(10)
        import_btn = ttk.Button(toolbar, text=_("📥 استيراد درجات (Excel)"), command=self.import_degrees_from_excel)
        import_btn.pack(side=side)
        ToolTip(import_btn, _("استيراد درجات الطلبة لاختبار محدد من ملف Excel مع تعيين الأعمدة"))

        add_spacer(40)

        ttk.Label(toolbar, text=_("القسم")).pack(side=side)
        self.class_filter_var = tk.StringVar()
        self.class_filter_combo = ttk.Combobox(toolbar, textvariable=self.class_filter_var, state="readonly", width=16)
        self.class_filter_combo.pack(side=side)
        self.class_filter_combo.bind("<<ComboboxSelected>>", self._on_class_filter_change)
        ToolTip(self.class_filter_combo, _("اختيار القسم لتصفية قائمة الاختبارات والنتائج"))

        add_spacer(20)
        ttk.Label(toolbar, text=_("الاختبار")).pack(side=side)
        self.test_filter_var = tk.StringVar()
        self.test_filter_combo = ttk.Combobox(toolbar, textvariable=self.test_filter_var, state="readonly", width=28)
        self.test_filter_combo.pack(side=side)
        ToolTip(self.test_filter_combo, _("تصفية النتائج حسب اختبار محدد أو عرض كل الاختبارات"))

        add_spacer(20)
        apply_btn = ttk.Button(toolbar, text=_("✅ تطبيق الفلترة"), command=self.load_tests)
        apply_btn.pack(side=side)
        ToolTip(apply_btn, _("إعادة تحميل النتائج باستخدام القيم المحددة في الفلاتر"))

        # بحث سريع داخل النتائج (رقم/اسم/لقب) بدون تغيير الفلاتر
        add_spacer(20)
        ttk.Label(toolbar, text=_("🔎 بحث (رقم/اسم/لقب)")).pack(side=side)
        self.tests_search_var = tk.StringVar(value="")
        self.tests_search_entry = ttk.Entry(toolbar, textvariable=self.tests_search_var, width=24, justify=("right" if is_rtl else "left"))
        self.tests_search_entry.pack(side=side, padx=(6, 6))
        ToolTip(self.tests_search_entry, _("اكتب لتصفية النتائج حسب الطالب"))

        def _on_search_change(*_args):
            self._refresh_tests_view()

        try:
            self.tests_search_var.trace_add("write", _on_search_change)
        except Exception:
            self.tests_search_entry.bind("<KeyRelease>", lambda _e: self._refresh_tests_view())

        # Include student's class (القسم) as a visible column so that when viewing
        # all classes together, the student's class is still visible.
        visible_cols = ("tname", "ttype", "session", "name_stu", "surname", "class_id", "degree")
        hidden_cols = ("test_id", "student_id")
        all_cols = visible_cols + hidden_cols

        table_frame = ttk.Frame(frame)
        table_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.tree_tests = ttk.Treeview(table_frame, columns=all_cols, show="headings", selectmode="browse", height=14)

        headers = {
            "tname": _("اسم الاختبار"),
            "ttype": _("نوع الاختبار"),
            "session": _("نوع الحصة"),
            "name_stu": _("اللقب"),
            "surname": _("الاسم"),
            "class_id": _("القسم"),
            "degree": _("الدرجة"),
        }

        for col in visible_cols:
            self.tree_tests.heading(col, text=headers[col], command=lambda c=col: self._sort_column(c))
            self.tree_tests.column(col, anchor="center", stretch=True, width=120, minwidth=90)

        for hidden in hidden_cols:
            self.tree_tests.heading(hidden, text="")
            self.tree_tests.column(hidden, width=1, stretch=False, anchor="center")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_tests.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_tests.xview)
        self.tree_tests.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree_tests.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        ToolTip(self.tree_tests, _("جدول نتائج الطلبة. انقر مزدوجًا على الدرجة لتعديلها."))

        self.tree_tests.bind("<Double-1>", self.edit_degree)

        self._tests_sort_state = {}
        self._tests_sort_col = None
        self._tests_sort_reverse = False

        self._tests_all_rows = []

        self._populate_class_filter()
        self._populate_test_filter()
        self.load_tests()

    def _parse_degree_value(self, value):
        if value is None:
            return None
        try:
            pd = _get_pandas_module()
            if pd is not None and pd.isna(value):
                return None
        except Exception:
            pass

        s = str(value).strip()
        if s == "":
            return None
        s = s.replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None

    def _is_absent_marker(self, value) -> bool:
        if value is None:
            return False
        try:
            pd = _get_pandas_module()
            if pd is not None and pd.isna(value):
                return False
        except Exception:
            pass

        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, (int, float)):
            try:
                return float(value) == 1.0
            except Exception:
                return False

        s = str(value).strip().lower()
        if not s:
            return False
        return s in {
            "abs",
            "absent",
            "a",
            "yes",
            "y",
            "true",
            "1",
            "غائب",
            "غياب",
            "غ",
        }

    def _get_selected_test_for_import(self):
        selected_class = (self.class_filter_var.get() or "").strip()
        if not selected_class or selected_class == ALL_CLASSES_LABEL:
            return None, None

        selected_test = (self.test_filter_var.get() or "").strip()
        if not selected_test or selected_test == ALL_TESTS_LABEL:
            return selected_class, None

        test_id = getattr(self, "_test_filter_map", {}).get(selected_test)
        if test_id is None:
            return selected_class, None
        return selected_class, int(test_id)

    def import_degrees_from_excel(self):
        class_id, test_id = self._get_selected_test_for_import()
        if class_id is None:
            messagebox.showerror(_("خطأ"), _("اختر قسمًا محددًا أولًا قبل الاستيراد."))
            return
        if test_id is None:
            messagebox.showerror(_("خطأ"), _("اختر اختبارًا محددًا أولًا قبل الاستيراد."))
            return

        pd_module = _get_pandas_module()
        if pd_module is None:
            messagebox.showerror(_("خطأ"), _("حزمة pandas غير مثبتة في هذه البيئة. ثبتها ثم حاول مجددًا."))
            return

        file_path = filedialog.askopenfilename(filetypes=[(_("ملفات Excel"), "*.xlsx")])
        if not file_path:
            return

        try:
            df = pd_module.read_excel(file_path)
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر قراءة ملف Excel:\n{error}").format(error=exc))
            return

        if df is None or getattr(df, "empty", False):
            messagebox.showwarning(_("تنبيه"), _("ملف Excel فارغ."))
            return

        try:
            cols = list(df.columns)
        except Exception:
            cols = []
        if len(cols) == 0:
            messagebox.showwarning(_("تنبيه"), _("لم يتم العثور على أعمدة في الملف."))
            return

        self._open_import_mapping_dialog(test_id=test_id, df=df)

    def _open_import_mapping_dialog(self, test_id: int, df):
        win = tk.Toplevel(self.root)
        win.title(_("تعيين أعمدة الاستيراد"))
        if hasattr(self, "center_window"):
            self.center_window(win, 430, 260)
        else:
            self._center(win, 430, 260)
        win.transient(self.root)
        safe_grab(win)

        try:
            cols = list(df.columns)
        except Exception:
            cols = []
        required = ["StudentId", "Surname", "Name", "degree"]
        optional = ["absent"]

        widgets = {}
        labels = {
            "StudentId": _("عمود رقم الطالب"),
            "Surname": _("عمود اللقب (Nom)"),
            "Name": _("عمود الاسم (Prénom)"),
            "degree": _("عمود الدرجة"),
            "absent": _("عمود الغياب (اختياري)"),
        }

        for i, key in enumerate(required + optional):
            ttk.Label(win, text=f"{labels[key]}:", width=18).grid(row=i, column=0, padx=8, pady=8, sticky="e")
            values = [""] + cols if key in optional else cols
            combo = ttk.Combobox(win, values=values, state="readonly", width=28)
            combo.grid(row=i, column=1, padx=8, pady=8, sticky="w")
            widgets[key] = combo

        # Best-effort defaults
        try:
            if "StudentId" in cols:
                widgets["StudentId"].set("StudentId")
            else:
                widgets["StudentId"].current(0)
        except Exception:
            pass

        try:
            for candidate in ("Surname", "Nom", "LastName", "FamilyName", "اللقب"):
                if candidate in cols:
                    widgets["Surname"].set(candidate)
                    break
        except Exception:
            pass

        try:
            for candidate in ("Name", "Prenom", "FirstName", "GivenName", "الاسم"):
                if candidate in cols:
                    widgets["Name"].set(candidate)
                    break
        except Exception:
            pass

        try:
            for candidate in ("degree", "Degree", "Note", "Mark", "Score", "الدرجة", "ملاحظة"):
                if candidate in cols:
                    widgets["degree"].set(candidate)
                    break
        except Exception:
            pass

        def apply_mapping():
            col_sid = widgets["StudentId"].get()
            col_surname = widgets["Surname"].get()
            col_name = widgets["Name"].get()
            col_degree = widgets["degree"].get()
            col_absent = widgets["absent"].get() if "absent" in widgets else ""

            if not col_sid or not col_surname or not col_name or not col_degree:
                messagebox.showerror(_("خطأ"), _("اختر أعمدة: رقم الطالب، اللقب، الاسم، والدرجة."), parent=win)
                return

            records = []
            invalid_rows = []
            pd_module = _get_pandas_module()

            not_in_group_details = []

            for idx, row in df.iterrows():
                raw_sid = row.get(col_sid, "")
                if pd_module is not None and pd_module.isna(raw_sid):
                    continue
                sid = str(raw_sid).strip()
                if not sid:
                    continue

                # Collect name fields (requested by UX). We keep them for reporting/helping identify rows.
                raw_surname = row.get(col_surname, "")
                raw_name = row.get(col_name, "")
                if pd_module is not None:
                    if pd_module.isna(raw_surname):
                        raw_surname = ""
                    if pd_module.isna(raw_name):
                        raw_name = ""
                excel_surname = str(raw_surname).strip()
                excel_name = str(raw_name).strip()

                absent = False
                if col_absent:
                    absent = self._is_absent_marker(row.get(col_absent))

                deg_raw = row.get(col_degree)
                deg = self._parse_degree_value(deg_raw)

                # If no absent column, treat empty/NaN degree as absent
                if not col_absent and deg is None:
                    absent = True

                # If the cell isn't empty but still not parsable -> invalid
                try:
                    if not absent and deg is None:
                        if pd_module is not None and not pd_module.isna(deg_raw):
                            if str(deg_raw).strip() != "":
                                invalid_rows.append((idx + 2, sid, deg_raw))  # +2: header + 1-based
                except Exception:
                    pass

                records.append({"StudentId": sid, "degree": deg, "absent": bool(absent)})

            try:
                report = service_import_degrees_for_test(test_id, records)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر استيراد الدرجات:\n{error}").format(error=exc), parent=win)
                return

            # Enrich not-in-group report with names from Excel (best-effort)
            not_in_group_set = set(report.get("not_in_group", []) or [])
            if not_in_group_set:
                for idx, row in df.iterrows():
                    raw_sid = row.get(col_sid, "")
                    if pd_module is not None and pd_module.isna(raw_sid):
                        continue
                    sid = str(raw_sid).strip()
                    if sid and sid in not_in_group_set:
                        rs = row.get(col_surname, "")
                        rn = row.get(col_name, "")
                        if pd_module is not None:
                            if pd_module.isna(rs):
                                rs = ""
                            if pd_module.isna(rn):
                                rn = ""
                        not_in_group_details.append((sid, str(rs).strip(), str(rn).strip()))

            win.destroy()
            self.load_tests()

            not_in_group = report.get("not_in_group", []) or []
            missing_in_file = report.get("missing_in_file", []) or []
            absents = report.get("absents", []) or []
            updated = int(report.get("updated", 0) or 0)

            parts = [
                _("تم الاستيراد بنجاح."),
                _("تم تحديث: {n}").format(n=updated),
                _("الغائبون (بدون درجة): {n}").format(n=len(absents)),
                _("غير منتمين للقسم (موجودين في Excel): {n}").format(n=len(not_in_group)),
                _("في القسم لكن غير موجودين في Excel: {n}").format(n=len(missing_in_file)),
            ]
            if invalid_rows:
                parts.append(_("صفوف بدرجات غير صالحة: {n}").format(n=len(invalid_rows)))

            # Show a short preview of problematic IDs
            preview = ""
            if not_in_group:
                if not_in_group_details:
                    sample = not_in_group_details[:12]
                    sample_txt = "\n".join([f"{s[0]} - {s[1]} {s[2]}".strip() for s in sample])
                    preview += "\n\n" + _("أمثلة (غير منتمين للقسم):\n{lines}").format(lines=sample_txt)
                else:
                    preview_ids = ", ".join(not_in_group[:15])
                    preview += "\n\n" + _("أمثلة (غير منتمين للقسم): {ids}").format(ids=preview_ids)

            if missing_in_file:
                preview_ids = ", ".join(missing_in_file[:15])
                preview += "\n\n" + _("أمثلة (في القسم لكن غير موجودين في Excel): {ids}").format(ids=preview_ids)
            if invalid_rows:
                sample = invalid_rows[:10]
                sample_txt = "\n".join([f"#{r[0]}: {r[1]} -> {r[2]}" for r in sample])
                preview += "\n\n" + _("أمثلة (درجات غير صالحة):\n{lines}").format(lines=sample_txt)

            messagebox.showinfo(_("تم"), "\n".join(parts) + preview)

        ttk.Button(win, text=_("تطبيق"), command=apply_mapping).grid(row=5, column=0, columnspan=2, pady=12)

    def _tests_matches_search(self, row: dict, needle: str) -> bool:
        if not needle:
            return True
        n = str(needle).strip().lower()
        if not n:
            return True
        sid = str(row.get("StudentId", "") or "").lower()
        name = str(row.get("nm", "") or "").lower()
        surname = str(row.get("sur", "") or "").lower()
        return (n in sid) or (n in name) or (n in surname)

    def _render_tests_rows(self, rows: list[dict]):
        for iid in self.tree_tests.get_children():
            self.tree_tests.delete(iid)

        needle = ""
        if hasattr(self, "tests_search_var"):
            try:
                needle = str(self.tests_search_var.get() or "")
            except Exception:
                needle = ""

        for row in rows:
            if needle.strip() and not self._tests_matches_search(row, needle):
                continue
            display_type = self.TEST_TYPE_RENAMES.get(row.get("TestType"), row.get("TestType"))
            self.tree_tests.insert(
                "",
                tk.END,
                values=(
                    row.get("TestName"),
                    display_type,
                    row.get("sessionInfo"),
                    row.get("nm"),
                    row.get("sur"),
                    row.get("classId"),
                    row.get("degree"),
                    row.get("IdTest"),
                    row.get("StudentId"),
                ),
            )

    def _refresh_tests_view(self):
        # Re-render from cached rows then re-apply current sort (best-effort)
        rows = list(getattr(self, "_tests_all_rows", []) or [])
        self._render_tests_rows(rows)
        if getattr(self, "_tests_sort_col", None):
            try:
                self._sort_column(self._tests_sort_col, reverse=self._tests_sort_reverse)
            except Exception:
                pass

    def _refresh_filters_and_reload(self):
        self._populate_class_filter()
        self._populate_test_filter()
        self.load_tests()

    def _populate_class_filter(self):
        try:
            classes = list_class_ids()
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{error}").format(error=exc))
            classes = []

        values = [ALL_CLASSES_LABEL] + classes
        self.class_filter_combo["values"] = values

        active = getattr(self, "active_class", None)
        if active and active in classes:
            self.class_filter_var.set(active)
        else:
            self.class_filter_var.set(values[0] if values else "")

    def _populate_test_filter(self):
        selected_class = self.class_filter_var.get()
        filter_class = selected_class if selected_class and selected_class != ALL_CLASSES_LABEL else None

        try:
            tests = list_tests(filter_class)
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل قائمة الاختبارات:\n{error}").format(error=exc))
            tests = []

        self._test_filter_map = {}
        values = [ALL_TESTS_LABEL]
        for record in tests:
            session_label = record.get("session_label") or "—"
            display = f"{record['TestName']} - {session_label}"
            values.append(display)
            self._test_filter_map[display] = record["IdTest"]

        self.test_filter_combo["values"] = values
        self.test_filter_var.set(values[0] if values else "")

    def _on_class_filter_change(self, _event=None):
        self._populate_test_filter()

    def open_test_manager_dialog(self):
        win = tk.Toplevel(self.root)
        win.title(_("إدارة الاختبارات — إضافة / تعديل / حذف"))
        win.transient(self.root)
        safe_grab(win)

        is_rtl = (get_language() or "ar").lower().startswith("ar")
        label_col = 1 if is_rtl else 0
        field_col = 0 if is_rtl else 1
        label_sticky = "e" if is_rtl else "w"

        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=16, pady=14)
        container.columnconfigure(0, weight=1 if field_col == 0 else 0)
        container.columnconfigure(1, weight=1 if field_col == 1 else 0)

        ttk.Label(container, text=_("القسم / الأقسام المستهدفة")).grid(
            row=0,
            column=label_col,
            sticky=("ne" if is_rtl else "nw"),
            padx=6,
            pady=6,
        )

        class_frame = ttk.Frame(container)
        class_frame.grid(row=0, column=field_col, rowspan=2, sticky="nw", padx=6, pady=6)
        class_frame.columnconfigure(0, weight=1)

        class_list = tk.Listbox(class_frame, selectmode="extended", exportselection=False, height=10)
        class_list.grid(row=0, column=0, sticky="nwe")
        ToolTip(class_list, _("اضغط مع الضغط على Ctrl أو Shift لاختيار عدة أقسام"))

        class_scroll = ttk.Scrollbar(class_frame, orient="vertical", command=class_list.yview)
        class_scroll.grid(row=0, column=1, sticky="ns")
        class_list.configure(yscrollcommand=class_scroll.set)

        ttk.Label(class_frame, text=_("اختر قسمًا واحدًا للتعديل أو عدة أقسام للإنشاء")).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        try:
            classes = list_class_ids()
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{error}").format(error=exc))
            classes = []

        for class_id in classes:
            class_list.insert(tk.END, class_id)

        visible_rows = min(10, max(1, len(classes)))
        class_list.configure(height=visible_rows)

        if classes:
            active = getattr(self, "active_class", None)
            idx = classes.index(active) if active and active in classes else 0
            class_list.selection_set(idx)
            class_list.see(idx)

        ttk.Label(container, text=_("اختبار موجود")).grid(row=2, column=label_col, sticky=label_sticky, padx=6, pady=6)
        var_existing = tk.StringVar(value=NEW_TEST_LABEL)
        combo_existing = ttk.Combobox(container, textvariable=var_existing, state="disabled", width=30)
        combo_existing.grid(row=2, column=field_col, sticky="we", padx=6, pady=6)
        ToolTip(combo_existing, _("اختر اختبارًا موجودًا في القسم المحدد لتعديله أو حذفه"))

        ttk.Label(container, text=_("اسم الاختبار")).grid(row=3, column=label_col, sticky=label_sticky, padx=6, pady=6)
        var_name = tk.StringVar()
        entry_name = ttk.Entry(container, textvariable=var_name, width=34, justify="center")
        entry_name.grid(row=3, column=field_col, sticky="we", padx=6, pady=6)
        ToolTip(entry_name, _("اسم الاختبار كما يظهر في القوائم والتقارير"))

        ttk.Label(container, text=_("نوع الاختبار")).grid(row=4, column=label_col, sticky=label_sticky, padx=6, pady=6)
        var_type = tk.StringVar(value=self.TEST_TYPE_OPTIONS[0])
        combo_type = ttk.Combobox(container, textvariable=var_type, state="readonly", width=30)
        combo_type["values"] = list(self.TEST_TYPE_OPTIONS)
        combo_type.grid(row=4, column=field_col, sticky="we", padx=6, pady=6)
        ToolTip(combo_type, _("حدد تصنيف الاختبار (استجواب، واجب، ... )"))

        ttk.Label(container, text=_("نوع الحصة")).grid(row=5, column=label_col, sticky=label_sticky, padx=6, pady=6)
        var_session = tk.StringVar()
        combo_session = ttk.Combobox(container, textvariable=var_session, state="readonly", width=30)
        combo_session.grid(row=5, column=field_col, sticky="we", padx=6, pady=6)
        ToolTip(combo_session, _("اربط الاختبار بالمادة ونوع الحصة المناسبة"))

        try:
            session_map = list_session_type_labels_with_ids()
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{error}").format(error=exc))
            session_map = {}

        combo_session["values"] = list(session_map.keys())
        if session_map:
            var_session.set(next(iter(session_map)))

        def get_selected_classes():
            selections = class_list.curselection()
            return [classes[idx] for idx in selections] if selections else []

        btn_delete = None

        def configure_existing_controls():
            selected = get_selected_classes()
            allow_edit = len(selected) == 1
            combo_existing.configure(state="readonly" if allow_edit else "disabled")
            if not allow_edit:
                var_existing.set(NEW_TEST_LABEL)
            if btn_delete is not None:
                btn_delete.configure(state="normal" if allow_edit else "disabled")

        def refresh_existing_tests():
            selected = get_selected_classes()
            if len(selected) != 1:
                combo_existing["values"] = [NEW_TEST_LABEL]
                var_existing.set(NEW_TEST_LABEL)
                self._existing_tests_map = {}
                configure_existing_controls()
                return

            try:
                existing = fetch_tests_for_class(selected[0])
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل الاختبارات للقسم المحدد:\n{error}").format(error=exc))
                existing = []

            values = [NEW_TEST_LABEL]
            self._existing_tests_map = {}
            for record in existing:
                label = record.get("session_label") or "—"
                display = f"{record['TestName']} - {label}"
                values.append(display)
                self._existing_tests_map[display] = record["IdTest"]

            combo_existing["values"] = values
            var_existing.set(values[0])
            configure_existing_controls()

        def on_existing_change(_event=None):
            if combo_existing.cget("state") == "disabled":
                return

            chosen = var_existing.get().strip()
            if not chosen or chosen == NEW_TEST_LABEL:
                var_name.set("")
                var_type.set(self.TEST_TYPE_OPTIONS[0])
                if session_map:
                    var_session.set(next(iter(session_map)))
                return

            selected = get_selected_classes()
            if len(selected) != 1:
                return

            test_id = self._existing_tests_map.get(chosen)
            if not test_id:
                return

            try:
                data = fetch_test_for_edit(test_id, selected[0])
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل بيانات الاختبار المحدد:\n{error}").format(error=exc))
                return

            if not data:
                messagebox.showwarning(_("تنبيه"), _("لم يتم العثور على بيانات للاختبار المحدد."))
                return

            var_name.set(data.get("TestName", ""))
            legacy_type = data.get("TestType")
            mapped_type = self.TEST_TYPE_RENAMES.get(legacy_type, legacy_type)
            var_type.set(mapped_type if mapped_type in self.TEST_TYPE_OPTIONS else self.TEST_TYPE_OPTIONS[0])
            session_label = data.get("session_label") or (next(iter(session_map)) if session_map else "")
            if session_label in session_map:
                var_session.set(session_label)

        def on_classes_changed(_event=None):
            refresh_existing_tests()
            on_existing_change()

        class_list.bind("<<ListboxSelect>>", on_classes_changed)
        refresh_existing_tests()
        on_existing_change()

        buttons_row = ttk.Frame(container)
        buttons_row.grid(row=6, column=0, columnspan=2, pady=14, sticky="we")
        buttons_row.columnconfigure(0, weight=1)
        buttons_row.columnconfigure(1, weight=1)
        buttons_row.columnconfigure(2, weight=1)

        def create_or_update():
            selected_classes = get_selected_classes()
            if not selected_classes:
                messagebox.showerror(_("خطأ"), _("اختر قسمًا واحدًا على الأقل."))
                return

            name = var_name.get().strip()
            test_type = var_type.get().strip()
            session_label = var_session.get().strip()
            if not (name and test_type and session_label):
                messagebox.showerror(_("خطأ"), _("كل الحقول مطلوبة."))
                return

            session_id = session_map.get(session_label)
            if not session_id:
                messagebox.showerror(_("خطأ"), _("نوع الحصة غير صالح."))
                return

            existing_label = var_existing.get().strip()
            is_multi = len(selected_classes) > 1
            if is_multi and existing_label and existing_label != NEW_TEST_LABEL:
                messagebox.showwarning(_("تنبيه"), _("لا يمكن تعديل اختبار عند اختيار عدة أقسام."))
                return

            try:
                if existing_label and existing_label != NEW_TEST_LABEL:
                    class_id = selected_classes[0]
                    test_id = self._existing_tests_map.get(existing_label)
                    if not test_id:
                        messagebox.showerror(_("خطأ"), _("تعذر تحديد الاختبار المحدد."))
                        return
                    try:
                        service_update_test(test_id, class_id, name, test_type, session_id)
                    except ValueError as exc:
                        code = str(exc)
                        if code == "RESULTS_ENTERED":
                            messagebox.showwarning(_("تنبيه"), _("لا يمكن تعديل الاختبار بعد إدخال درجات."))
                        elif code == "DUPLICATE_NAME":
                            messagebox.showerror(_("خطأ"), _("يوجد اختبار آخر بنفس الاسم لهذا القسم ونوع الحصة."))
                        else:
                            messagebox.showerror(_("خطأ"), _("تعذر تحديث الاختبار: {error}").format(error=code))
                        return
                    except Exception as exc:
                        messagebox.showerror(_("خطأ"), _("تعذر تحديث بيانات الاختبار:\n{error}").format(error=exc))
                        return
                    else:
                        messagebox.showinfo(_("تم"), _("تم تحديث بيانات الاختبار."))
                else:
                    try:
                        created, duplicates = create_tests(selected_classes, name, test_type, session_id)
                    except Exception as exc:
                        messagebox.showerror(_("خطأ"), _("تعذر إنشاء الاختبار:\n{error}").format(error=exc))
                        return

                    if created:
                        created_str = ", ".join(created)
                        messagebox.showinfo(_("تم"), _("تم إنشاء الاختبار للأقسام: {classes}").format(classes=created_str))
                    if duplicates:
                        duplicates_str = ", ".join(duplicates)
                        messagebox.showwarning(
                            _("تنبيه"),
                            _("لم يتم الإنشاء للأقسام التالية لوجود اختبار بنفس الاسم: {classes}").format(classes=duplicates_str),
                        )
                    if not created and duplicates:
                        return

                self._populate_test_filter()
                self.load_tests()
                refresh_existing_tests()
                on_existing_change()
            except Exception:
                # في حال وقوع خطأ غير متوقع نحاول منع تحطم النافذة
                raise

        def delete_current_test():
            selected_classes = get_selected_classes()
            if len(selected_classes) != 1:
                messagebox.showwarning(_("تنبيه"), _("اختر قسمًا واحدًا لحذف اختبار."))
                return

            existing_label = var_existing.get().strip()
            if not existing_label or existing_label == NEW_TEST_LABEL:
                messagebox.showwarning(_("تنبيه"), _("اختر اختبارًا موجودًا أولًا للحذف."))
                return

            test_id = self._existing_tests_map.get(existing_label)
            if not test_id:
                messagebox.showerror(_("خطأ"), _("تعذر تحديد الاختبار المحدد."))
                return

            if not messagebox.askyesno(
                _("تأكيد"),
                _("سيؤدي الحذف إلى إزالة الاختبار وسجلاته الفارغة. هل تريد المتابعة؟"),
            ):
                return

            try:
                service_delete_test(test_id)
            except ValueError as exc:
                if str(exc) == "RESULTS_ENTERED":
                    messagebox.showwarning(_("تنبيه"), _("لا يمكن حذف الاختبار بعد إدخال درجات."))
                else:
                    messagebox.showerror(_("خطأ"), _("تعذر حذف الاختبار: {error}").format(error=str(exc)))
                return
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر حذف الاختبار:\n{error}").format(error=exc))
                return

            messagebox.showinfo(_("تم"), _("تم حذف الاختبار."))
            refresh_existing_tests()
            on_existing_change()
            self._populate_test_filter()
            self.load_tests()

        btn_save = ttk.Button(buttons_row, text=_("💾 حفظ"), command=create_or_update)
        btn_save.grid(row=0, column=2, sticky="e", padx=8)
        ToolTip(btn_save, _("إنشاء اختبار جديد أو حفظ التعديلات الحالية"))

        btn_delete = ttk.Button(buttons_row, text=_("🗑 حذف"), command=delete_current_test)
        btn_delete.grid(row=0, column=1, padx=8)
        ToolTip(btn_delete, _("حذف الاختبار المحدد للقسم الحالي إذا لم تُسجل درجات"))

        btn_close = ttk.Button(buttons_row, text=_("❌ إغلاق"), command=win.destroy)
        btn_close.grid(row=0, column=0, sticky="w", padx=8)
        ToolTip(btn_close, _("إغلاق نافذة إدارة الاختبارات"))

        configure_existing_controls()

        win.update_idletasks()
        req_w = win.winfo_reqwidth()
        req_h = win.winfo_reqheight()
        win.minsize(req_w, req_h)
        if hasattr(self, "center_window"):
            self.center_window(win, req_w, req_h)
        else:
            self._center(win, req_w, req_h)

    def load_tests(self):
        # preserve scroll and selection for a smoother refresh
        try:
            yview = self.tree_tests.yview()
        except Exception:
            yview = None

        selected_key = None
        try:
            sel = self.tree_tests.selection()
            if sel:
                vals = self.tree_tests.item(sel[0], "values")
                if vals and len(vals) >= 9:
                    selected_key = (str(vals[7]), str(vals[8]))  # (test_id, student_id)
        except Exception:
            selected_key = None

        for iid in self.tree_tests.get_children():
            self.tree_tests.delete(iid)

        selected_class = self.class_filter_var.get().strip()
        class_id = selected_class if selected_class and selected_class != ALL_CLASSES_LABEL else None

        selected_test = self.test_filter_var.get().strip()
        test_id = None
        if selected_test and selected_test != ALL_TESTS_LABEL:
            test_id = getattr(self, "_test_filter_map", {}).get(selected_test)
            if test_id is None:
                return

        try:
            rows = list_test_results(class_id, test_id)
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل نتائج الاختبارات:\n{error}").format(error=exc))
            return

        self._tests_all_rows = rows
        self._render_tests_rows(rows)

        # Re-apply current sort (without toggling) after refresh
        if getattr(self, "_tests_sort_col", None):
            try:
                self._sort_column(self._tests_sort_col, reverse=self._tests_sort_reverse)
            except Exception:
                pass

        # Restore selection (best-effort)
        if selected_key:
            try:
                for iid in self.tree_tests.get_children():
                    vals = self.tree_tests.item(iid, "values")
                    if vals and len(vals) >= 9 and (str(vals[7]), str(vals[8])) == selected_key:
                        self.tree_tests.selection_set(iid)
                        self.tree_tests.see(iid)
                        break
            except Exception:
                pass

        # Restore scroll position
        if yview and len(yview) >= 1:
            try:
                self.tree_tests.yview_moveto(yview[0])
            except Exception:
                pass

    def edit_degree(self, _event=None):
        selection = self.tree_tests.selection()
        if not selection:
            return

        values = self.tree_tests.item(selection[0], "values")
        if not values or len(values) < 9:
            return

        test_name, test_type, session_label, name_stu, surname, class_id, current_deg, test_id, student_id = values

        win = tk.Toplevel(self.root)
        win.title(_("تعديل الدرجة"))
        if hasattr(self, "center_window"):
            self.center_window(win, 360, 170)
        else:
            self._center(win, 360, 170)
        win.transient(self.root)
        safe_grab(win)

        ttk.Label(win, text=_("👤 {student} — {test}").format(student=f"{surname} {name_stu}", test=test_name)).pack(pady=8)
        degree_var = tk.StringVar(value=str(current_deg) if current_deg not in (None, "") else "")
        entry = ttk.Entry(win, textvariable=degree_var, justify="center")
        entry.pack(pady=6)

        def save_degree():
            value = degree_var.get().strip()
            if value == "":
                new_degree = None
            else:
                try:
                    new_degree = float(value)
                except ValueError:
                    messagebox.showerror(_("خطأ"), _("الدرجة يجب أن تكون رقمية أو فارغة."))
                    return

            try:
                service_update_degree(int(test_id), student_id, new_degree)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحديث الدرجة:\n{error}").format(error=exc))
                return

            self.load_tests()
            win.destroy()

        ttk.Button(win, text=_("💾 حفظ"), command=save_degree).pack(pady=6)

        # Focus automatique sur le champ note
        try:
            win.after(0, lambda: (entry.focus_set(), entry.selection_range(0, tk.END)))
        except Exception:
            try:
                entry.focus_set()
            except Exception:
                pass

        # Raccourcis clavier
        win.bind("<Return>", lambda _e: save_degree())
        win.bind("<Escape>", lambda _e: win.destroy())

    def _sort_column(self, col, reverse=None):
        children = list(self.tree_tests.get_children(""))
        data = [(self.tree_tests.set(item, col), item) for item in children]
        if reverse is None:
            reverse = self._tests_sort_state.get(col, False)

        if col == "degree":

            def keyfun(item):
                value = item[0]
                try:
                    return float(value) if value not in ("", None) else float("-inf")
                except Exception:
                    return float("-inf")

        else:

            def keyfun(item):
                value = item[0]
                return (value is None, str(value))

        data.sort(key=keyfun, reverse=reverse)

        for index, (_, item) in enumerate(data):
            self.tree_tests.move(item, "", index)

        self._tests_sort_state[col] = not reverse
        self._tests_sort_col = col
        self._tests_sort_reverse = reverse
