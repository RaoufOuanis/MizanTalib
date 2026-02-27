# tabs/final_tab.py
import importlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tooltip import ToolTip
from i18n import gettext_ as _, get_language

from services.final_report_service import (
    list_classes,
    list_session_types_for_class,
    get_subgroup_mode as service_get_subgroup_mode,
    set_subgroup_mode as service_set_subgroup_mode,
    compute_final_scores,
    list_interrogation_tests,
    fetch_degrees_for_tests,
)

openpyxl = None
try:
    openpyxl = importlib.import_module("openpyxl")
except ImportError:
    openpyxl = None


class FinalTabMixin:
    def build_final_tab(self):
        f = self.tab_final

        is_rtl = (get_language() or "ar").lower().startswith("ar")

        title_lbl = ttk.Label(
            f,
            text=_("تفصيل نقطة التقويم المستمر 🖊️"),
            font=("Tajawal", 16, "bold"),
        )
        title_lbl.pack(pady=8)
        ToolTip(title_lbl, _("عرض تفصيلي لنقاط المتابعة المستمرة لكل طالب"))

        # ===== شريط علوي: اختيار القسم + نوع الحصة + أزرار + بحث =====
        # ملاحظة: في الإنجليزية قد تصبح النصوص أطول، مما يؤدي إلى اختفاء زر "عرض".
        # الحل: تقسيم الشريط العلوي إلى سطرين حتى يبقى زر العرض مرئيًا دائمًا.
        top = ttk.Frame(f)
        top.pack(fill="x", padx=8, pady=4)

        filter_row = ttk.Frame(top)
        filter_row.pack(fill="x")

        actions_row = ttk.Frame(top)
        actions_row.pack(fill="x", pady=(6, 0))

        filter_side = "right" if is_rtl else "left"
        actions_side = "right" if is_rtl else "left"

        class_lbl = ttk.Label(filter_row, text=_("القسم"))
        class_lbl.pack(side=filter_side, padx=(0, 4))
        ToolTip(class_lbl, _("اختر القسم الذي تود مراجعة درجاته"))

        self.final_class_var = tk.StringVar()
        self.final_class_combo = ttk.Combobox(
            filter_row,
            textvariable=self.final_class_var,
            state="readonly",
            width=14,
        )
        self.final_class_combo.pack(side=filter_side, padx=(10, 10))
        self.final_class_combo.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._populate_final_session_types(trigger_load=False),
        )
        ToolTip(self.final_class_combo, _("اختر القسم لعرض نتائجه النهائية"))

        stype_lbl = ttk.Label(filter_row, text=_("نوع الحصة"))
        stype_lbl.pack(side=filter_side, padx=(0, 4))
        ToolTip(stype_lbl, _("حدد نوع الحصة أو المادة المراد تقييمها"))

        self.final_stype_var = tk.StringVar()
        self.final_stype_combo = ttk.Combobox(
            filter_row,
            textvariable=self.final_stype_var,
            state="readonly",
            width=30,
        )
        self.final_stype_combo.pack(side=filter_side, padx=(0, 10))
        self.final_stype_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_final())
        ToolTip(self.final_stype_combo, _("اختر نوع الحصة ثم اضغط عرض لإظهار النتائج"))

        btn_view = ttk.Button(filter_row, text=_("🔍 عرض"), command=self.load_final)
        btn_view.pack(side=filter_side, padx=(12, 0))
        ToolTip(btn_view, _("تحميل وعرض النتائج النهائية للطلاب"))

        btn_export = ttk.Button(actions_row, text=_("📤 تصدير Excel"), command=self.export_final_excel)
        btn_export.pack(side=actions_side, padx=6)
        ToolTip(btn_export, _("تصدير النتائج الحالية إلى ملف Excel"))

        # خيار الوضع: تقسيم الجلسات على 2 عند وجود Sous-groups
        self.subgroup_mode_var = tk.IntVar(value=0)
        self.subgroup_mode_chk = ttk.Checkbutton(
            actions_row,
            text=_("تفعيل وضع التقسيم إلى فوجين فرعيين"),
            variable=self.subgroup_mode_var,
            command=self._on_toggle_subgroup_mode,
        )
        self.subgroup_mode_chk.pack(side=actions_side, padx=(8, 10))
        ToolTip(
            self.subgroup_mode_chk,
            _("فعل هذا الخيار بشكل إجباري إذا كان هذا القسم مقسم على فوجين فرعيين يتابعان دروس نفس نوع الحصة"),
        )

        # بحث داخل النتائج (بدون إعادة الحساب)
        self.final_search_var = tk.StringVar(value="")
        ttk.Label(actions_row, text=_("🔎 بحث (لقب/اسم/رقم)")).pack(side=actions_side, padx=(0, 6))
        search_entry = ttk.Entry(
            actions_row,
            textvariable=self.final_search_var,
            width=24,
            justify=("right" if is_rtl else "left"),
        )
        search_entry.pack(side=actions_side, padx=(6, 4))
        ToolTip(search_entry, _("ابحث باللقب أو الاسم أو الرقم"))

        def _on_search_change(*_args):
            self._refresh_final_view()

        try:
            self.final_search_var.trace_add("write", _on_search_change)
        except Exception:
            search_entry.bind("<KeyRelease>", lambda _e: self._refresh_final_view())

        # ===== جدول النتائج =====
        table_frame = ttk.Frame(f)
        table_frame.pack(fill="both", expand=True, padx=10, pady=6)

        cols = ("id", "name", "surname", "att", "part", "quiz", "homework", "total")
        self._final_columns = cols
        self.tree_final = ttk.Treeview(table_frame, columns=cols, show="headings", height=16)

        headers = {
            "id": _("📌 الرقم"),
            "name": _("👤 اللقب"),
            "surname": _("👥 الاسم"),
            "att": _("📖 الحضور"),
            "part": _("💬 المشاركة"),
            "quiz": _("📝 إستجوابات"),
            "homework": _("📚 الواجب"),
            "total": _("⚖️ المجموع"),
        }

        for col in cols:
            self.tree_final.heading(col, text=headers[col], command=lambda c=col: self._on_final_header_click(c))
            self.tree_final.column(col, anchor="center", stretch=True, width=120, minwidth=90)

        ToolTip(self.tree_final, _("جدول النقاط النهائية لكل طالب حسب مكونات التقييم"))

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_final.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_final.xview)
        self.tree_final.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree_final.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self._final_headers = headers
        self._final_col_index = {c: idx for idx, c in enumerate(cols)}
        self._final_sort_col = "name"
        self._final_sort_reverse = False
        self._final_all_rows = []

        self._populate_final_classes()

    # ---------------- تعبئة قائمة الأقسام ----------------
    def _populate_final_classes(self):
        try:
            rows = list_classes()
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{exc}").format(exc=exc))
            rows = []

        self.final_class_combo["values"] = rows
        if not rows:
            self.final_class_var.set("")
            self.final_stype_combo["values"] = []
            self.final_stype_var.set("")
            self._refresh_final_view()
            return

        if getattr(self, "active_class", None) in rows:
            self.final_class_var.set(self.active_class)
        else:
            self.final_class_combo.current(0)
            self.final_class_var.set(self.final_class_combo.get())

        self._populate_final_session_types(trigger_load=False)

    # ---------------- تعبئة أنواع الحصص ----------------
    def _populate_final_session_types(self, trigger_load=True):
        class_id = (self.final_class_var.get() or "").strip()
        if not class_id:
            self.final_stype_combo["values"] = []
            self.final_stype_var.set("")
            # No valid class selected -> disable subgroup checkbox and clear
            try:
                self.subgroup_mode_var.set(0)
                self.subgroup_mode_chk.config(state='disabled')
            except Exception:
                pass
            self._refresh_final_view()
            return

        try:
            rows = list_session_types_for_class(class_id)
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{exc}").format(exc=exc))
            rows = []

        values = [f"{row['id']} - {row['label']}" for row in rows]
        self.final_stype_combo["values"] = values

        current = self.final_stype_var.get()
        if current in values:
            selected = current
        elif values:
            self.final_stype_combo.current(0)
            selected = self.final_stype_combo.get()
        else:
            selected = ""

        self.final_stype_var.set(selected)

        # Update subgroup checkbox to reflect the persisted setting for the
        # currently selected class + sessionType. If nothing is selected, disable it.
        try:
            if selected:
                sid = None
                if " - " in selected:
                    sid_str, _ = selected.split(" - ", 1)
                    try:
                        sid = int(sid_str)
                    except Exception:
                        sid = None

                if sid is not None:
                    try:
                        mode = service_get_subgroup_mode(class_id, sid)
                    except Exception:
                        mode = False
                    self.subgroup_mode_var.set(1 if mode else 0)
                    self.subgroup_mode_chk.config(state='normal')
                else:
                    self.subgroup_mode_var.set(0)
                    self.subgroup_mode_chk.config(state='disabled')
            else:
                self.subgroup_mode_var.set(0)
                self.subgroup_mode_chk.config(state='disabled')
        except Exception:
            # non-fatal; ensure checkbox is at least disabled
            try:
                self.subgroup_mode_var.set(0)
                self.subgroup_mode_chk.config(state='disabled')
            except Exception:
                pass

        if trigger_load and selected:
            self.load_final()
        else:
            self._refresh_final_view()

    def _get_selected_stype_id(self):
        raw = (self.final_stype_var.get() or "").strip()
        if " - " not in raw:
            return None, None
        sid_str, label = raw.split(" - ", 1)
        try:
            return int(sid_str), label
        except ValueError:
            return None, None

    def _on_toggle_subgroup_mode(self):
        """Persist the subgroup-mode setting for the currently selected class and session type."""
        class_id = (self.final_class_var.get() or "").strip()
        stype_id, _ = self._get_selected_stype_id()
        if not class_id or not stype_id:
            return
        enabled = bool(self.subgroup_mode_var.get())
        try:
            service_set_subgroup_mode(class_id, stype_id, bool(enabled))
        except Exception:
            # non-fatal: keep the UI state but notify user
            messagebox.showwarning(_("تنبيه"), _("تعذر حفظ إعداد وضع التقسيم في قاعدة البيانات."))

    # ---------------- تحميل الحساب النهائي ----------------
    def load_final(self):
        for child in self.tree_final.get_children():
            self.tree_final.delete(child)
        self._final_all_rows = []

        class_id = (self.final_class_var.get() or "").strip()
        stype_id, _stype_label = self._get_selected_stype_id()
        if not class_id or not stype_id:
            self._refresh_final_view()
            return

        try:
            mode = service_get_subgroup_mode(class_id, stype_id)
        except Exception:
            mode = False
        self.subgroup_mode_var.set(1 if mode else 0)

        try:
            weights = self.get_weights()
        except Exception:
            messagebox.showerror(_("خطأ"), _("تعذر قراءة الأوزان."))
            return

        try:
            rows_data = compute_final_scores(
                class_id,
                stype_id,
                weights,
                bool(self.subgroup_mode_var.get()),
            )
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر حساب النتائج:\n{exc}").format(exc=exc))
            return

        self._final_all_rows = rows_data
        self._sort_final("name", toggle=False)

    # ---------------- تحديث الجدول ----------------
    def _refresh_final_view(self):
        self._render_final_rows(self._final_all_rows)

    def _final_matches_search(self, row: tuple, needle: str) -> bool:
        if not needle:
            return True
        n = str(needle).strip().lower()
        if not n:
            return True
        try:
            sid = str(row[0] or "").lower()
            name = str(row[1] or "").lower()
            surname = str(row[2] or "").lower()
        except Exception:
            return True
        return (n in sid) or (n in name) or (n in surname)

    def _get_final_filtered_rows(self, rows: list[tuple]) -> list[tuple]:
        needle = ""
        if hasattr(self, "final_search_var"):
            try:
                needle = str(self.final_search_var.get() or "")
            except Exception:
                needle = ""
        if not needle.strip():
            return rows
        return [r for r in rows if self._final_matches_search(r, needle)]

    def _on_final_header_click(self, col):
        self._sort_final(col)

    def _sort_final(self, col, toggle=True):
        if not self._final_all_rows:
            return

        if toggle:
            if self._final_sort_col == col:
                self._final_sort_reverse = not self._final_sort_reverse
            else:
                self._final_sort_col = col
                self._final_sort_reverse = False
        else:
            self._final_sort_col = col
            self._final_sort_reverse = False

        idx = self._final_col_index.get(self._final_sort_col, 1)

        def sort_key(row):
            value = row[idx]
            if isinstance(value, (int, float)):
                return value
            try:
                return float(value)
            except (TypeError, ValueError):
                return str(value).lower()

        self._final_all_rows.sort(key=sort_key, reverse=self._final_sort_reverse)
        self._render_final_rows(self._final_all_rows)

    def _render_final_rows(self, rows):
        rows = self._get_final_filtered_rows(list(rows) if rows else [])
        for child in self.tree_final.get_children():
            self.tree_final.delete(child)
        for row in rows:
            self.tree_final.insert("", tk.END, values=row)

    # ---------------- تصدير Excel ----------------
    def export_final_excel(self):
        class_id = (self.final_class_var.get() or "").strip()
        if not class_id:
            messagebox.showerror(_("خطأ"), _("يجب اختيار قسم أولاً"))
            return

        stype_id, _stype_label = self._get_selected_stype_id()
        if not stype_id:
            messagebox.showerror(_("خطأ"), _("يجب اختيار نوع الحصة أولاً"))
            return

        if not self.tree_final.get_children():
            messagebox.showwarning(_("تنبيه"), _("لا توجد بيانات لتصديرها."))
            return

        if openpyxl is None:
            messagebox.showerror(_("خطأ"), _("حزمة openpyxl غير مثبتة في هذه البيئة. ثبتها ثم حاول مجددًا."))
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not filename:
            return

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = _("النتائج النهائية")

            # Add one column per interrogation (استجواب) test.
            interrogations = []
            try:
                interrogations = list_interrogation_tests(class_id, int(stype_id))
            except Exception:
                interrogations = []

            inter_test_ids = [int(t["IdTest"]) for t in interrogations]
            deg_map = {}
            try:
                deg_map = fetch_degrees_for_tests(inter_test_ids) if inter_test_ids else {}
            except Exception:
                deg_map = {}

            base_headers = [self._final_headers[c] for c in self._final_columns]
            detail_headers = []
            for t in interrogations:
                tname = str(t.get("TestName") or "").strip()
                if tname:
                    detail_headers.append(_("استجواب") + " - " + tname)
                else:
                    detail_headers.append(_("استجواب"))

            ws.append(base_headers + detail_headers)

            for child in self.tree_final.get_children():
                values = list(self.tree_final.item(child, "values") or [])
                sid = str(values[0]) if values else ""
                details = []
                for tid in inter_test_ids:
                    deg = deg_map.get((sid, int(tid)))
                    details.append("" if deg is None else deg)
                ws.append(values + details)

            wb.save(filename)
            messagebox.showinfo(_("تم"), _("تم تصدير الحساب النهائي إلى Excel"))
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر التصدير:\n{exc}").format(exc=exc))
