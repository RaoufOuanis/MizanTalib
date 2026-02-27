# tabs/attendance_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import time
import re
from camera import CameraScanner
from center_window import safe_grab
from tooltip import ToolTip
from i18n import gettext_ as _, get_language

from services.attendance_service import (
    list_session_types,
    list_students_for_manual_add,
    resolve_student_class,
    fetch_student_by_id,
    ensure_unique_session_token,
    get_session_type_id,
    save_session_records,
    count_students_in_class,
)
from services.student_service import fetch_class_ids


class AttendanceTabMixin:
    def build_att_tab(self):
        f = self.tab_att
        title_lbl = ttk.Label(f, text=_("📝 تسجيل الـحضور"), font=("Tajawal", 16, "bold"))
        title_lbl.pack(pady=8)
        ToolTip(title_lbl, _("واجهة تسجيل حضور الطلبة أثناء الحصة"))

        # ===== حالة الحفظ للجلسة =====
        self.session_saved = True
        self.current_token = None  # رمز الجلسة الحالي

        # شريط علوي
        top = ttk.Frame(f)
        top.pack(fill='x', pady=4)

        self.btn_start = ttk.Button(top, text=_("▶️ id QR scan"), command=self.start_camera)
        self.btn_start.pack(side='left', padx=4)
        ToolTip(self.btn_start, _("ابدأ تشغيل الكاميرا لمسح رمز الطالب"))

        ttk.Frame(top, width=40).pack(side='left')

        self.btn_stop = ttk.Button(top, text=_("⏹ إيقاف"), command=self.stop_camera)
        self.btn_stop.pack(side='left', padx=4)
        ToolTip(self.btn_stop, _("إيقاف الكاميرا الحالية"))

        controls_right = ttk.Frame(top)
        controls_right.pack(side="right", fill="y")
        
        save_spacer = tk.Frame(controls_right, width=5)
        save_spacer.pack(side="right")

        self.btn_manual = ttk.Button(controls_right, text=_("➕ إضافة طلبة من القائمة"), command=self.add_student_manual)
        self.btn_manual.pack(side="right", padx=(4, 4))
        ToolTip(self.btn_manual, _("فتح نافذة لاختيار طلبة يدويًا"))

        save_spacer = tk.Frame(controls_right, width=20)
        save_spacer.pack(side="right")
        
            # اختيار نوع الحصة  

        type_group = ttk.Frame(controls_right)
        type_group.pack(side="right", padx=(4, 0))

        # Label showing the currently active class (helpful reminder)
        self.lbl_active_class = ttk.Label(
            type_group,
            text=_("{active}  :القسم النشط").format(active=getattr(self, 'active_class', None) or _("(غير مفعل)")),
            font=("tahoma", 8, "bold"),
            foreground="blue",
        )
        # place the active-class label to the left of the session-type controls for better ergonomics
        self.lbl_active_class.pack(side="left", padx=(0, 8))
        ToolTip(self.lbl_active_class, _("لتغيير القسم النشط، انتقل إلى تبويب الأقسام"))

        self.session_type_var = tk.StringVar()
        # place the combo to the right of the active-class label, and the label to its right
        self.session_type_combo = ttk.Combobox(type_group, textvariable=self.session_type_var, state="readonly", width=20)
        self.session_type_combo.pack(side="left", padx=(0, 4))
        ttk.Label(type_group, text=_("نوع الحصة")).pack(side="left", padx=(4, 0))
        ToolTip(self.session_type_combo, _("اختر المادة ونوع الحصة المرتبط بها"))

        save_spacer = tk.Frame(controls_right, width=20)
        save_spacer.pack(side="right")
        save_spacer.pack_propagate(False)

        self.btn_save = ttk.Button(controls_right, text=_("💾 حفظ الحصة"), command=self.save_session)
        self.btn_save.pack(side="right", padx=(4, 8))
        ToolTip(self.btn_save, _("حفظ الحضور الحالي في قاعدة البيانات"))

        self.btn_delete_selected = ttk.Button(
            controls_right,
            text=_("🗑 حذف المحدد"),
            command=self.delete_selected_attendee,
        )
        self.btn_delete_selected.pack(side="right", padx=(4, 4))
        ToolTip(self.btn_delete_selected, _("إزالة الطالب المحدد من القائمة المؤقتة"))

        self.btn_clear_preview = ttk.Button(
            controls_right,
            text=_("♻️ تفريغ القائمة"),
            command=self.clear_preview_without_save,
        )
        self.btn_clear_preview.pack(side="right", padx=(4, 4))
        ToolTip(self.btn_clear_preview, _("حذف جميع الطلبة من القائمة دون حفظ"))

        try:
            values = list_session_types()
            self.session_type_combo["values"] = values
            if values:
                self.session_type_combo.current(0)
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{error}").format(error=e))

        # تقسيم الكاميرا والجدول
        paned = ttk.Panedwindow(f, orient="horizontal"); paned.pack(fill="both", expand=True, padx=8, pady=6)
        left = ttk.Frame(paned); right = ttk.Frame(paned)
        paned.add(left, weight=1); paned.add(right, weight=2)

        self.lbl_cam = ttk.Label(left, text=_("📷 الكاميرا متوقفة"), anchor="center")
        self.lbl_cam.pack(fill="both", expand=True, padx=4, pady=4)

        # جدول الطلبة الحاضرين
        table_frame = ttk.Frame(right); table_frame.pack(fill='both', expand=True)
        self.tree_preview = ttk.Treeview(
            table_frame, columns=("rownum", "id", "name", "surname", "class", "part"),
            show='headings', selectmode="browse"
        )
        headers = [("rownum", _("#")), ("id", _("الرقم")), ("name", _("اللقب")), ("surname", _("الاسم")),
                   ("class", _("القسم")), ("part", _("المشاركة"))]
        for col, text in headers:
            self.tree_preview.heading(col, text=text, command=lambda c=col: self._sort_preview_tree(c))

        self.tree_preview.column("rownum", width=50, anchor="center")
        self.tree_preview.column("id", width=80, anchor="center")
        self.tree_preview.column("name", width=120, anchor="center")
        self.tree_preview.column("surname", width=120, anchor="center")
        self.tree_preview.column("class", width=150, anchor="center")
        self.tree_preview.column("part", width=70, anchor="center")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_preview.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree_preview.xview)
        self.tree_preview.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.tree_preview.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1); table_frame.columnconfigure(0, weight=1)
        ToolTip(self.tree_preview, _("قائمة مؤقتة للطلبة الممسوحة في هذه الجلسة"))
        self._preview_sort_col = None
        self._preview_sort_reverse = False
        self._preview_col_index = {name: idx for idx, (name, _) in enumerate(headers)}

        # عداد
        self.counter_var = tk.StringVar(value="0 / 0")
        counter_frame = ttk.Frame(right)
        counter_frame.pack(fill="x", padx=4, pady=(4, 0))
        counter_lbl = ttk.Label(counter_frame, textvariable=self.counter_var, font=("Arial", 10, "bold"), anchor="e")
        counter_lbl.pack(side="right")
        ToolTip(counter_lbl, _("عدد الطلبة الحاليين مقارنة بإجمالي القسم"))

        # روابط
        self.tree_preview.bind("<Delete>", self._on_delete_att_key)
        self.tree_preview.bind("<Double-1>", self.on_double_click_part)

        self._recent_scans = {}
        self._duplicate_alerts = {}

        if hasattr(self, "root") and callable(getattr(self.root, "protocol", None)):
            try: self.root.protocol("WM_DELETE_WINDOW", self.on_close_app)
            except Exception: pass

        self.update_counter()
        self.scanned_preview = []

    def update_active_class_label(self):
        """Refresh the small active-class label shown above the session-type combo."""
        try:
            active = getattr(self, "active_class", None) or _("(غير مفعل)")
            text = _("{active}  :القسم النشط").format(active=active)
            self.lbl_active_class.config(text=text)
        except Exception:
            pass



    def add_student_manual(self):
        """نافذة اختيار قسم + وضع علامات على الطلبة المراد إضافتهم دفعة واحدة."""
        if not self.active_class:
            messagebox.showerror(_("خطأ"), _("يجب تنشيط قسم أولاً"))
            return

        is_rtl = (get_language() or "ar").lower().startswith("ar")
        side = "right" if is_rtl else "left"

        win = tk.Toplevel(self.root)
        win.title(_("إضافة يدويًا — اختيار طلبة"))
        if hasattr(self, "center_window"):
            self.center_window(win, 720, 520)
        win.transient(self.root)
        safe_grab(win)

        # أعلى النافذة: اختيار القسم + بحث
        top = ttk.Frame(win)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text=_("القسم")).pack(side=side, padx=(6, 2))
        class_combo = ttk.Combobox(top, state="readonly", width=36)
        class_combo.pack(side=side, padx=4)
        ToolTip(class_combo, _("اختر القسم لعرض طلبته"))

        # تعبئة الأقسام
        try:
            classes = fetch_class_ids()
        except Exception:
            classes = []
        class_combo["values"] = classes
        if self.active_class in classes:
            class_combo.set(self.active_class)
        elif classes:
            class_combo.current(0)

        # مربع بحث
        search_var = tk.StringVar()
        search_label = ttk.Label(top, text=_("🔎 بحث (رقم/اسم/لقب)"))
        search_entry = ttk.Entry(top, textvariable=search_var, width=28, justify=("right" if is_rtl else "left"))

        # في LTR: اللابل يسار الحقل. في RTL: اللابل يمين الحقل.
        search_label.pack(side=side)
        search_entry.pack(side=side, padx=4)
        ToolTip(search_entry, _("ابحث عن الطالب بالرقم أو الاسم أو اللقب"))
        ToolTip(search_label, _("استخدم البحث لتصفية قائمة الطلبة"))

        # وسط النافذة: جدول الطلبة مع عمود اختيار
        mid = ttk.Frame(win)
        mid.pack(fill="both", expand=True, padx=8, pady=4)

        tree = ttk.Treeview(
            mid,
            columns=("chk", "id", "name", "surname"),
            show="headings", selectmode="none"
        )
        tree.heading("chk", text=_("✔"))
        tree.heading("id", text=_("الرقم"))
        tree.heading("name", text=_("اللقب"))
        tree.heading("surname", text=_("الاسم"))

        tree.column("chk", width=40, anchor="center")
        tree.column("id", width=110, anchor="center")
        tree.column("name", width=190, anchor="center")
        tree.column("surname", width=190, anchor="center")

        yscroll2 = ttk.Scrollbar(mid, orient="vertical", command=tree.yview)
        xscroll2 = ttk.Scrollbar(mid, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll2.set, xscrollcommand=xscroll2.set)

        tree.grid(row=0, column=0, sticky="nsew")
        yscroll2.grid(row=0, column=1, sticky="ns")
        xscroll2.grid(row=1, column=0, sticky="ew")
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)
        ToolTip(tree, _("حدد الطلبة الذين تريد إضافتهم للحضور"))

        # مجموعة أزرار: تحديد الكل، إلغاء
        tool = ttk.Frame(win)
        tool.pack(fill="x", padx=8, pady=(0, 6))

        def select_all():
            for iid in tree.get_children():
                vals = list(tree.item(iid, "values"))
                if vals and vals[0] != "✓":
                    vals[0] = "✓"
                    tree.item(iid, values=vals)

        def unselect_all():
            for iid in tree.get_children():
                vals = list(tree.item(iid, "values"))
                if vals and vals[0] != "":
                    vals[0] = ""
                    tree.item(iid, values=vals)

        btn_select_all = ttk.Button(tool, text=_("تحديد الكل"), command=select_all)
        btn_select_all.pack(side="right", padx=4)
        ToolTip(btn_select_all, _("تفعيل العلامة لكل الطلبة في القائمة"))

        btn_unselect_all = ttk.Button(tool, text=_("إلغاء التحديد"), command=unselect_all)
        btn_unselect_all.pack(side="right", padx=4)
        ToolTip(btn_unselect_all, _("إزالة العلامة عن كل الطلبة"))

        # قسم اللصق
        paste_frame = ttk.LabelFrame(win, text=_("إضافة باللصق"))
        paste_frame.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(
            paste_frame,
            text=_("الصق الأرقام هنا (Ctrl+V) — سطر لكل رقم أو مفصولة بمسافة"),
            anchor="e",
        ).pack(fill="x", padx=8, pady=(6, 2))

        paste_box = tk.Text(paste_frame, height=4, wrap="word")
        paste_box.pack(fill="x", padx=8, pady=(0, 6))

        paste_menu = tk.Menu(paste_box, tearoff=0)
        paste_menu.add_command(label=_("لصق"), command=lambda: paste_box.event_generate("<<Paste>>"))
        paste_menu.add_command(label=_("تحديد الكل"), command=lambda: paste_box.event_generate("<<SelectAll>>"))
        paste_menu.add_command(label=_("مسح"), command=lambda: paste_box.delete("1.0", tk.END))

        def show_paste_menu(event):
            try:
                paste_menu.tk_popup(event.x_root, event.y_root)
            finally:
                paste_menu.grab_release()

        paste_box.bind("<Button-3>", show_paste_menu)

        # تحميل الطلبة حسب القسم المختار + البحث
        def load_students_for(class_id, needle=""):
            for iid in tree.get_children():
                tree.delete(iid)
            if not class_id:
                return
            try:
                rows = list_students_for_manual_add(class_id, needle.strip() or None)
            except Exception as exc:
                messagebox.showerror(
                    _("خطأ"),
                    _("تعذر تحميل الطلبة للقسم {class_id}:\n{error}").format(class_id=class_id, error=exc),
                )
                return
            for r in rows:
                tree.insert("", "end", values=("", r["StudentId"], r["Name"], r["Surname"]))

        if class_combo.get():
            load_students_for(class_combo.get())

        def on_class_change(event=None):
            load_students_for(class_combo.get(), search_var.get().strip())

        class_combo.bind("<<ComboboxSelected>>", on_class_change)

        def on_search_change(*_):
            load_students_for(class_combo.get(), search_var.get().strip())

        search_var.trace_add("write", lambda *a: on_search_change())

        def toggle_check(event):
            region = tree.identify("region", event.x, event.y)
            if region != "cell":
                return
            row_id = tree.identify_row(event.y)
            col_id = tree.identify_column(event.x)
            if not row_id:
                return
            vals = list(tree.item(row_id, "values"))
            if col_id in ("#1", "#2", "#3", "#4"):
                vals[0] = "" if vals[0] == "✓" else "✓"
                tree.item(row_id, values=vals)

        tree.bind("<Button-1>", toggle_check)

        # أزرار أسفل النافذة
        bottom = ttk.Frame(win)
        bottom.pack(fill="x", padx=8, pady=8)

        def confirm_add():
            class_id = class_combo.get().strip()
            if not class_id:
                messagebox.showerror(_("خطأ"), _("اختر قسمًا أولًا"))
                return
            selected = []
            for iid in tree.get_children():
                vals = tree.item(iid, "values")
                if vals and vals[0] == "✓":
                    sid = str(vals[1]).strip()
                    name_val = str(vals[2]).strip()
                    surname_val = str(vals[3]).strip()
                    selected.append((sid, name_val, surname_val))
            if not selected:
                messagebox.showwarning(_("تنبيه"), _("لم تُحدد أي طالب."))
                return

            added_count = 0
            skipped = []
            for sid, name, surname in selected:
                try:
                    stu_class = resolve_student_class(sid, fallback_class=class_id)
                except Exception:
                    stu_class = class_id

                if self._add_student_to_preview(sid, name, surname, stu_class, part=None, force=False):
                    added_count += 1
                else:
                    skipped.append(sid)

            self.update_counter()

            if skipped and added_count:
                msg = _(
                    "✅ تمت إضافة {added} طالب جديد.\n⚠️ لم يتم إضافة {skipped} لأنهم موجودون مسبقًا."
                ).format(added=added_count, skipped=len(skipped))
                messagebox.showwarning(_("تنبيه"), msg)
                if hasattr(self, "set_status"):
                    self.set_status(msg)
            elif skipped and not added_count:
                msg = _("⚠️ جميع الطلبة المحددين موجودون مسبقًا في القائمة.")
                messagebox.showwarning(_("تنبيه"), msg)
                if hasattr(self, "set_status"):
                    self.set_status(msg)
            elif added_count:
                if added_count == 1:
                    msg = _("✅ تمت إضافة طالب واحد.")
                else:
                    msg = _("✅ تمت إضافة {count} طالب.").format(count=added_count)
                messagebox.showinfo(_("تم"), msg)
                if hasattr(self, "set_status"):
                    self.set_status(msg)
            else:
                msg = _("لم يتم إضافة أي طالب.")
                messagebox.showwarning(_("تنبيه"), msg)
                if hasattr(self, "set_status"):
                    self.set_status(msg)

            if added_count:
                win.destroy()

        def confirm_paste_add():
            raw = paste_box.get("1.0", tk.END).strip()
            if not raw:
                messagebox.showwarning(_("تنبيه"), _("لا توجد أرقام في خانة اللصق."))
                return

            tokens = [t.strip() for t in re.split(r"\s+", raw) if t.strip()]
            if not tokens:
                messagebox.showwarning(_("تنبيه"), _("لم يتم العثور على أرقام صالحة."))
                return

            ids = []
            seen = set()
            for token in tokens:
                if token in seen:
                    continue
                seen.add(token)
                ids.append(token)

            added_count = 0
            missing = []
            duplicates = 0

            for sid in ids:
                try:
                    student = fetch_student_by_id(sid)
                except Exception as exc:
                    messagebox.showerror(_("قاعدة البيانات"), _("تعذر الوصول:\n{error}").format(error=exc))
                    return

                if not student:
                    missing.append(sid)
                    continue

                if self._add_student_to_preview(
                    student["StudentId"],
                    student["Name"],
                    student["Surname"],
                    student["classId"],
                    part=None,
                    force=False,
                ):
                    added_count += 1
                else:
                    duplicates += 1

            self.update_counter()

            if missing:
                if len(missing) <= 10:
                    missing_text = ", ".join(missing)
                    msg = _("⚠️ لم يتم العثور على: {ids}").format(ids=missing_text)
                else:
                    msg = _("⚠️ لم يتم العثور على {count} رقم/أرقام.").format(count=len(missing))
                if added_count:
                    msg += _("\n✅ تمت إضافة {added} طالب.").format(added=added_count)
                messagebox.showwarning(_("تنبيه"), msg)
                if hasattr(self, "set_status"):
                    self.set_status(msg)
            elif added_count:
                msg = _("✅ تمت إضافة {count} طالب.").format(count=added_count)
                messagebox.showinfo(_("تم"), msg)
                if hasattr(self, "set_status"):
                    self.set_status(msg)
            else:
                if duplicates:
                    msg = _("⚠️ جميع الأرقام موجودة مسبقًا في القائمة.")
                else:
                    msg = _("لم يتم إضافة أي طالب.")
                messagebox.showwarning(_("تنبيه"), msg)
                if hasattr(self, "set_status"):
                    self.set_status(msg)

        btn_confirm = ttk.Button(bottom, text=_("✅ إضافة المحددين"), command=confirm_add)
        btn_confirm.pack(side="right", padx=4)
        ToolTip(btn_confirm, _("أضف الطلبة المحددين إلى قائمة الحضور"))

        btn_confirm_paste = ttk.Button(bottom, text=_("📋 إضافة من اللصق"), command=confirm_paste_add)
        btn_confirm_paste.pack(side="right", padx=4)
        ToolTip(btn_confirm_paste, _("إضافة الأرقام الملصوقة إلى قائمة الحضور"))

        btn_cancel = ttk.Button(bottom, text=_("❌ إلغاء"), command=win.destroy)
        btn_cancel.pack(side="left", padx=4)
        ToolTip(btn_cancel, _("إغلاق النافذة بدون إضافة أحد"))


    def _add_student_to_preview(self, sid, name, surname, class_id, part=None, force=False):
        """إضافة طالب إلى قائمة الحضور المؤقتة"""
        # تفادي التكرار إلا لو force=True
        for s in self.scanned_preview:
            if s["id"] == sid:
                if not force:
                    return False
                else:
                    self.scanned_preview.remove(s)
                    break
        self.scanned_preview.append({
            "id": sid,
            "name": name,
            "surname": surname,
            "class": class_id,
            "part": part
        })
        self.session_saved = False
        try:
            self.refresh_attendance_table()
        except Exception:
            pass
        return True

    def _clean_token_fragment(self, value, *, upper=True):
        if not value:
            return ""
        cleaned = "".join(ch for ch in str(value) if ch.isalnum())
        return cleaned.upper() if upper else cleaned

    def _generate_session_token(self):
        now = datetime.now()
        month = f"{now.month:02d}"
        day = f"{now.day:02d}"

        session_info = getattr(self, "session_type_var", None)
        if session_info and hasattr(session_info, "get"):
            session_value = session_info.get().strip()
        else:
            session_value = ""
        subject_code = ""
        type_code = ""
        if session_value:
            parts = session_value.split("-", 1)
            subject_code = self._clean_token_fragment(parts[0])
            if len(parts) > 1:
                type_code = self._clean_token_fragment(parts[1])

        session_code = f"{subject_code}{type_code}" or "UNK"
        class_code = self._clean_token_fragment(getattr(self, "active_class", ""), upper=False) or "CLS"
        base_token = f"{month}{day}{session_code}{class_code}"
        candidate = base_token or f"{month}{day}SESSION{class_code}"

        candidate = base_token or f"{month}{day}SESSION{class_code}"
        try:
            return ensure_unique_session_token(candidate, base_token or candidate)
        except Exception:
            return candidate

    def refresh_attendance_table(self):
        # تنظيف الجدول
        for i in self.tree_preview.get_children():
            self.tree_preview.delete(i)
        # لا تفرز – احتفظ بالترتيب حسب وقت الإضافة (FIFO)
        for idx, s in enumerate(self.scanned_preview, start=1):
            self.tree_preview.insert("", "end", values=(idx, s["id"], s["name"], s["surname"], s["class"], s["part"]))
        # تمرير تلقائي لآخر عنصر
        children = self.tree_preview.get_children()
        if children:
            self.tree_preview.see(children[-1])
        self._apply_preview_sort()

    def _sort_preview_tree(self, column):
        if not hasattr(self, "tree_preview"):
            return
        if column == "rownum":
            self._preview_sort_col = None
            self._preview_sort_reverse = False
            # إعادة العرض إلى ترتيب الإدخال الأصلي
            self.refresh_attendance_table()
            return
        if getattr(self, "_preview_sort_col", None) == column:
            self._preview_sort_reverse = not getattr(self, "_preview_sort_reverse", False)
        else:
            self._preview_sort_col = column
            self._preview_sort_reverse = False
        self._apply_preview_sort()

    def _apply_preview_sort(self):
        if not hasattr(self, "tree_preview"):
            return
        children = self.tree_preview.get_children()
        if not children:
            return
        if not hasattr(self, "_preview_col_index"):
            return
        selected_student = None
        sel = self.tree_preview.selection()
        if sel:
            vals_sel = self.tree_preview.item(sel[0], "values")
            if vals_sel and len(vals_sel) > 1:
                selected_student = str(vals_sel[1])

        sort_col = getattr(self, "_preview_sort_col", None)
        if not sort_col:
            for pos, iid in enumerate(children, start=1):
                vals = list(self.tree_preview.item(iid, "values"))
                if vals:
                    vals[0] = pos
                    self.tree_preview.item(iid, values=vals)
            return

        idx = self._preview_col_index.get(sort_col)
        if idx is None:
            return

        rows = [list(self.tree_preview.item(iid, "values")) for iid in children]

        def sort_key(values):
            val = values[idx] if idx < len(values) else ""
            if sort_col == "part":
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return 0.0
            if sort_col == "id":
                try:
                    return int(str(val))
                except (TypeError, ValueError):
                    return str(val).casefold()
            return str(val).casefold()

        rows.sort(key=sort_key, reverse=getattr(self, "_preview_sort_reverse", False))
        self.tree_preview.delete(*children)

        reselect_iid = None
        for pos, vals in enumerate(rows, start=1):
            if vals:
                vals[0] = pos
            iid = self.tree_preview.insert("", "end", values=vals)
            if selected_student is not None and len(vals) > 1 and str(vals[1]) == selected_student:
                reselect_iid = iid

        if reselect_iid:
            self.tree_preview.selection_set(reselect_iid)
            self.tree_preview.see(reselect_iid)
        else:
            self.tree_preview.selection_remove(self.tree_preview.selection())


    # ===== الكاميرا =====
    def start_camera(self):
        if not self.active_class:
            messagebox.showerror(_("خطأ"), _("يجب تنشيط قسم أولاً")); return
        if getattr(self, "scanner", None) and getattr(self.scanner, "running", False):
            return
        self._recent_scans = {}
        self._duplicate_alerts = {}
        self.scanner = CameraScanner(self.lbl_cam, self)
        if not self.current_token:
            self.current_token = self._generate_session_token()
        self.scanner.current_token = self.current_token
        success = self.scanner.start()
        if success:
            if hasattr(self, "set_status"): self.set_status(_("بدأ المسح..."))
        else:
            error_msg = getattr(self.scanner, "last_error", _("تعذر تشغيل الكاميرا."))
            messagebox.showerror(_("الكاميرا"), error_msg)
            if hasattr(self, "set_status"): self.set_status(_("تعذر تشغيل الكاميرا"))

    def stop_camera(self):
        if getattr(self, "scanner", None):
            try: self.scanner.stop()
            finally: self.scanner = None
        try:
            self.lbl_cam.config(image=None)
            if hasattr(self.lbl_cam, "image"): self.lbl_cam.image = None
        except: pass
        self.lbl_cam.config(text=_("📷 الكاميرا متوقفة"))
        if hasattr(self, "set_status"): self.set_status(_("تم إيقاف الكاميرا"))

    # ===== إضافة من QR =====
    def add_scanned_preview(self, sid, name=None, sur=None, part=None):
        sid = str(sid).strip(); now = time.time()
        last = self._recent_scans.get(sid, 0)
        if (now - last) < 1.2:
            return "recent"
        self._recent_scans[sid] = now

        try:
            student = fetch_student_by_id(sid)
        except Exception as e:
            messagebox.showerror(_("قاعدة البيانات"), _("تعذر الوصول:\n{error}").format(error=e))
            if hasattr(self, "set_status"):
                self.set_status(_("تعذر قراءة قاعدة البيانات"))
            return "error"

        if not student:
            msg = _("الطالب {sid} غير موجود في قائمة الطلبة.").format(sid=sid)
            messagebox.showwarning(_("تنبيه"), msg)
            if hasattr(self, "set_status"):
                self.set_status(_("⚠️ {message}").format(message=msg))
            return "missing"

        added = self._add_student_to_preview(
            student["StudentId"],
            student["Name"],
            student["Surname"],
            student["classId"],
            part,
        )
        if not added:
            # Silent duplicate: update internal timestamp tracking, but do not show any UI notification.
            alerts = getattr(self, "_duplicate_alerts", None)
            if isinstance(alerts, dict):
                alerts[sid] = now
            else:
                self._duplicate_alerts = {sid: now}
            return "duplicate"

        self.update_counter()
        if hasattr(self, "set_status"):
            self.set_status(_("✅ تم تسجيل {surname} {name}").format(surname=student['Surname'], name=student['Name']))
        return "added"

    # ===== الحفظ =====
    def save_session(self):
        session_info = self.session_type_var.get().strip()
        if not session_info:
            messagebox.showerror(_("خطأ"), _("اختر نوع الحصة قبل الحفظ.")); return
        try:
            subj, t = session_info.split("-")
        except ValueError:
            messagebox.showerror(_("خطأ"), _("تنسيق غير صحيح: {value}").format(value=session_info)); return

        # Before performing DB operations, ask for a confirmation with styled warning
        def ask_confirm():
            win = tk.Toplevel(self.root)
            win.title(_("تأكيد حفظ الحصة"))
            if hasattr(self, "center_window"):
                self.center_window(win, 460, 180)
            win.transient(self.root); safe_grab(win)

            ttk.Label(win, text=_(":أنت على وشك حفظ حصة من النوع"), font=("Arial", 11)).pack(pady=(10, 2))
            # session type in red
            ttk.Label(win, text=session_info, foreground="red", font=("Arial", 12, "bold")).pack()
            ttk.Label(win, text=_(":للقسم"), font=("Arial", 11)).pack(pady=(8, 2))
            cls_text = str(getattr(self, 'active_class', '') or _("غير محدد"))
            ttk.Label(win, text=cls_text, foreground="red", font=("Arial", 12, "bold")).pack()

            frm = ttk.Frame(win)
            frm.pack(pady=10)

            confirmed = {'ok': False}

            def on_ok():
                confirmed['ok'] = True
                win.destroy()

            def on_cancel():
                win.destroy()

            ttk.Button(frm, text=_("💾 تأكيد الحفظ"), command=on_ok).pack(side="right", padx=8)
            ttk.Button(frm, text=_("إلغاء"), command=on_cancel).pack(side="left", padx=8)

            win.wait_window()
            return confirmed['ok']

        proceed = ask_confirm()
        if not proceed:
            # user cancelled
            if hasattr(self, "set_status"):
                try: self.set_status(_("تم إلغاء حفظ الحصة"))
                except Exception: pass
            return

        try:
            stype_id = get_session_type_id(subj, t)
        except Exception as exc:
            messagebox.showerror(_("خطأ"), _("تعذر قراءة أنواع الحصص:\n{error}").format(error=exc))
            return
        if stype_id is None:
            messagebox.showerror(_("خطأ"), _("نوع الحصة {value} غير موجود.").format(value=session_info))
            return

        rows = self.tree_preview.get_children()
        if not rows:
            messagebox.showinfo(_("لا يوجد شيء"), _("القائمة فارغة.")); return
        if not self.current_token:
            self.current_token = self._generate_session_token()

        now_dt = datetime.now().replace(second=0, microsecond=0)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M")
        entries = []
        for iid in rows:
            rownum, sid, name, sur, class_id, part = self.tree_preview.item(iid, "values")
            sid = str(sid).strip()
            session_class = str(getattr(self, 'active_class', class_id) or class_id).strip()
            try:
                part_val = float(part) if str(part).strip() != "" else 0.0
            except Exception:
                part_val = 0.0
            entries.append({
                "student_id": sid,
                "class_id": session_class,
                "participation": part_val,
                "presence": 1,
            })

        try:
            result = save_session_records(
                token=self.current_token,
                session_type_id=stype_id,
                session_datetime=now_str,
                entries=entries,
            )
        except Exception as e:
            messagebox.showerror(_("خطأ"), _("تعذر الحفظ:\n{error}").format(error=e))
            return

        saved = result.inserted
        updated = result.updated
        skipped = result.skipped

        self.session_saved = True
        status_msg = _("تم حفظ {saved} سجل.").format(saved=saved)
        if updated:
            status_msg += _(" تم تحديث {updated} سجل.").format(updated=updated)
        if skipped:
            status_msg += _(" لم يتم حفظ {skipped} تكرار.").format(skipped=len(skipped))
        if hasattr(self, "set_status"):
            self.set_status(status_msg)

        msg_lines = [_("تم حفظ الجلسة ({saved} سجل جديد).").format(saved=saved)]
        if updated:
            msg_lines.append(_("تم تحديث {updated} سجل موجود.").format(updated=updated))
        if skipped:
            msg_lines.append(_("تم تجاهل {skipped} لأنهم موجودون مسبقًا.").format(skipped=len(skipped)))
        messagebox.showinfo(_("تم"), "\n".join(msg_lines))
        for child in self.tree_preview.get_children():
            self.tree_preview.delete(child)
        try:
            self.scanned_preview.clear()
        except Exception:
            self.scanned_preview = []
        self.current_token = None
        self.update_counter()

    # ===== حذف طالب من الحضور =====
    def delete_selected_attendee(self):
        sel = self.tree_preview.selection()
        if not sel: messagebox.showwarning(_("تنبيه"), _("اختر طالباً.")); return
        vals = self.tree_preview.item(sel[0], "values")
        if not vals or len(vals) < 4:
            self.tree_preview.delete(sel[0]); self.update_counter(); return
        _, sid, name_val, surname_val = vals[:4]
        if messagebox.askyesno(_("تأكيد"), _("حذف {sid} - {surname} {name}؟").format(sid=sid, surname=surname_val, name=name_val)):
            self.tree_preview.delete(sel[0])
            try:
                self.scanned_preview = [s for s in self.scanned_preview if s.get("id") != sid]
            except Exception:
                pass
            if hasattr(self, "_duplicate_alerts") and isinstance(self._duplicate_alerts, dict):
                self._duplicate_alerts.pop(sid, None)
            if hasattr(self, "_recent_scans") and isinstance(self._recent_scans, dict):
                self._recent_scans.pop(sid, None)
            self.session_saved = False
            self._apply_preview_sort()
            self.update_counter()

    def clear_preview_without_save(self):
        rows = self.tree_preview.get_children()
        if not rows:
            messagebox.showinfo(_("لا يوجد شيء"), _("القائمة فارغة بالفعل."))
            return
        if not messagebox.askyesno(_("تأكيد"), _("سيتم حذف جميع الطلبة من القائمة دون حفظ. المتابعة؟")):
            return

        for item in rows:
            self.tree_preview.delete(item)
        try:
            self.scanned_preview.clear()
        except Exception:
            self.scanned_preview = []
        if hasattr(self, "_recent_scans") and isinstance(self._recent_scans, dict):
            self._recent_scans.clear()
        else:
            self._recent_scans = {}
        if hasattr(self, "_duplicate_alerts") and isinstance(self._duplicate_alerts, dict):
            self._duplicate_alerts.clear()
        else:
            self._duplicate_alerts = {}

        self.session_saved = True
        self.current_token = None
        self.update_counter()
        if hasattr(self, "set_status"):
            try:
                self.set_status(_("تم تفريغ قائمة الحضور."))
            except Exception:
                pass

    def _on_delete_att_key(self, event=None):
        self.delete_selected_attendee(); return "break"
    
        # ===== تعديل المشاركة عند الدبل كليك =====
    def on_double_click_part(self, event=None):
        sel = self.tree_preview.selection()
        if not sel:
            return
        item = sel[0]
        vals = self.tree_preview.item(item, "values")
        # Expecting 6 values: (rownum, id, name, surname, class, part)
        if not vals or len(vals) < 6:
            return

        # Unpack while ignoring rownum
        _, student_id, name_val, surname_val, class_id, old_part = vals

        import gettext
        _ = gettext.gettext

        win = tk.Toplevel(self.root)
        tr = gettext.gettext
        win.title(tr("تعديل المشاركة"))



        if hasattr(self, "center_window"):
            self.center_window(win, 300, 150)
        win.transient(self.root)
        safe_grab(win)

        ttk.Label(win, text=_("👤 {student_id} - {surname} {name}").format(student_id=student_id, surname=surname_val, name=name_val)).pack(pady=6)

        part_text = str(old_part) if old_part not in (None, "") else "0"
        part_var = tk.StringVar(value=part_text)
        entry = ttk.Entry(win, textvariable=part_var, justify="center")
        entry.pack(pady=6)

        def save_new_part():
            try:
                new_val = float(part_var.get())
            except ValueError:
                messagebox.showerror(_("خطأ"), _("قيمة المشاركة يجب أن تكون رقمية"))
                return
            # تحديث القيمة في الجدول فقط (قبل الحفظ في DB)
            current_vals = list(self.tree_preview.item(item, "values"))
            # Ensure we replace the 'part' column (last element)
            if len(current_vals) >= 6:
                current_vals[5] = new_val
            else:
                # Fallback: replace last
                current_vals[-1] = new_val
            self.tree_preview.item(item, values=current_vals)
            sid_str = str(student_id)
            for entry in self.scanned_preview:
                if str(entry.get("id")) == sid_str:
                    entry["part"] = new_val
                    break
            self._apply_preview_sort()
            self.session_saved = False
            self.update_counter()
            win.destroy()

        ttk.Button(win, text=_("💾 حفظ"), command=save_new_part).pack(pady=8)
        entry.bind("<Return>", lambda _event: save_new_part())
        entry.focus_set()
        entry.select_range(0, tk.END)
    def on_close_app(self):
        # Si la session n'est pas sauvegardée et qu'il y a des présences dans le Treeview
        if not self.session_saved and self.tree_preview.get_children():
            if not messagebox.askyesno(_("مغادرة؟"), _("هناك قائمة حضور غير محفوظة. هل تريد حقًا المغادرة؟")):
                return  # Annule la fermeture
        if not messagebox.askyesno(_("تأكيد"), _("هل تريد مغادرة البرنامج؟")):
            return
        if hasattr(self, "stop_camera"):
            try:
                self.stop_camera()
            except Exception:
                pass
        if hasattr(self, "root"):
            self.root.destroy()

    # ===== العداد =====
    def update_counter(self):
        total = len(self.tree_preview.get_children())
        try:
            total_class = count_students_in_class(self.active_class) if self.active_class else 0
        except Exception:
            total_class = 0
        self.counter_var.set(f"{total} / {total_class}")
