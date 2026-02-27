import importlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

try:
    from tkcalendar import DateEntry
except Exception:
    DateEntry = None

from center_window import safe_grab
from tooltip import ToolTip
from i18n import gettext_ as _

from services.exclusion_service import (
    list_classes,
    list_session_types_for_class,
    list_students_for_class,
    compute_exclusion_risk,
    export_exclusion_to_workbook,
    get_default_exclusion_start_date,
    set_default_exclusion_start_date,
    list_exceptions,
    add_exception,
    remove_exception,
)

openpyxl = None
try:
    openpyxl = importlib.import_module("openpyxl")
except ImportError:
    openpyxl = None


class ExclusionManagerMixin:
    def open_exclusion_manager(self):
        """فتح نافذة لإدارة/عرض طلاب مهددين بالإقصاء (غيابات >= 3).

        سيُحتسب الغياب المبرر كحضور (وفق توجيه المستخدم).
        يدعم الوضع الفرعي (subgroup) عبر قراءة الإعداد من DB.
        """
        win = tk.Toplevel(self.root)
        win.title(_("إدارة حالات الإقصاء — طلاب مهددون بالإقصاء"))
        W, H = 1120, 620
        try:
            win.update_idletasks()
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            x = max(0, (sw // 2) - (W // 2))
            y = max(0, (sh // 2) - (H // 2))
            win.geometry(f"{W}x{H}+{x}+{y}")
        except Exception:
            try:
                win.geometry(f"{W}x{H}")
            except Exception:
                pass
        try:
            win.minsize(900, 520)
            win.resizable(True, True)
        except Exception:
            pass
        win.transient(self.root)
        safe_grab(win)
    # log_window_geometry supprimé (non essentiel)

        header = ttk.Frame(win, padding=(12, 10))
        header.pack(fill='x')
        ttk.Label(header, text=_("⚠️ إدارة حالات الإقصاء"), font=("Tajawal", 16, "bold")).pack(side='right')
        ttk.Label(header, text=_("سيُحتسب الغياب المبرر كحضور كامل."), foreground="#555").pack(side='left')

        # Filters
        filt = ttk.Frame(win, padding=(12, 8))
        filt.pack(fill='x')

        for c in range(0, 10):
            try:
                filt.columnconfigure(c, weight=0)
            except Exception:
                pass
        try:
            filt.columnconfigure(3, weight=1)
        except Exception:
            pass

        ttk.Label(filt, text=_("القسم")).grid(row=0, column=0, sticky='e')
        class_var = tk.StringVar()
        class_cb = ttk.Combobox(filt, textvariable=class_var, state='readonly', width=16)
        class_cb.grid(row=0, column=1, sticky='e', padx=(6, 12))

        ttk.Label(filt, text=_("نوع الحصة")).grid(row=0, column=2, sticky='e')
        stype_var = tk.StringVar()
        stype_cb = ttk.Combobox(filt, textvariable=stype_var, state='readonly', width=30)
        stype_cb.grid(row=0, column=3, sticky='ew', padx=(6, 12))

        ttk.Label(filt, text=_("عتبة الغياب")).grid(row=0, column=4, sticky='e')
        thresh_var = tk.IntVar(value=3)
        thresh_spin = ttk.Spinbox(filt, from_=1, to=99, textvariable=thresh_var, width=4)
        thresh_spin.grid(row=0, column=5, sticky='e', padx=(6, 12))

        ttk.Label(filt, text=_("من تاريخ")).grid(row=1, column=0, sticky='e', pady=(6, 0))
        start_date_var = tk.StringVar(value="")
        if DateEntry is not None:
            start_date_entry = DateEntry(
                filt,
                textvariable=start_date_var,
                width=12,
                date_pattern="yyyy-mm-dd",
            )
        else:
            start_date_entry = ttk.Entry(filt, textvariable=start_date_var, width=12, justify="center")
        start_date_entry.grid(row=1, column=1, sticky='e', padx=(6, 12), pady=(6, 0))
        ToolTip(start_date_entry, _("اختياري: اختر التاريخ من التقويم. عند تركه فارغاً تُحسب كل الحصص."))

        # Default date: last chosen by user; else oldest session date in DB
        try:
            default_date = get_default_exclusion_start_date()
        except Exception:
            default_date = None
        if default_date:
            try:
                start_date_var.set(default_date)
                if DateEntry is not None and hasattr(start_date_entry, "set_date"):
                    start_date_entry.set_date(datetime.strptime(default_date, "%Y-%m-%d").date())
            except Exception:
                pass

        def _clear_start_date():
            try:
                start_date_var.set("")
            except Exception:
                pass

        ttk.Button(filt, text=_("مسح"), command=_clear_start_date).grid(row=1, column=2, sticky='e', pady=(6, 0))

        # Action buttons (always visible)
        btn_show = ttk.Button(filt, text=_("عرض"), command=lambda: load_results())
        btn_show.grid(row=1, column=3, sticky='w', padx=(12, 6), pady=(6, 0))

        btn_export = ttk.Button(filt, text=_("تصدير Excel"), command=lambda: export_results())
        btn_export.grid(row=1, column=4, sticky='w', padx=(6, 6), pady=(6, 0))

        btn_manage_exc = ttk.Button(filt, text=_("إدارة الاستثناءات"), command=lambda: manage_exceptions())
        btn_manage_exc.grid(row=1, column=5, sticky='w', padx=(6, 0), pady=(6, 0))

        table_frame = ttk.Frame(win)
        table_frame.pack(fill='both', expand=True, padx=12, pady=(6, 12))

        cols = ("StudentId", "Name", "Surname", "attended", "denom", "absences")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        headers = {
            "StudentId": _("الرقم"),
            "Name": _("اللقب"),
            "Surname": _("الاسم"),
            "attended": _("عدد مرات الحضور"),
            "denom": _("الحصص الرسمية"),
            "absences": _("الغيابات")
        }
        for c in cols:
            tree.heading(c, text=headers[c])
            tree.column(c, anchor='center', width=120)

        yscr = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=yscr.set)
        tree.grid(row=0, column=0, sticky='nsew')
        yscr.grid(row=0, column=1, sticky='ns')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        # load combos
        def populate_classes():
            try:
                rows = list_classes()
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل الأقسام:\n{exc}").format(exc=exc), parent=win)
                rows = []
            class_cb['values'] = rows
            if getattr(self, 'active_class', None) in rows:
                class_var.set(self.active_class)
            elif rows:
                class_cb.current(0)
                class_var.set(class_cb.get())

        def populate_stypes(*_args):
            cid = (class_var.get() or '').strip()
            if not cid:
                stype_cb['values'] = []
                stype_var.set('')
                return
            try:
                rows = list_session_types_for_class(cid)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل أنواع الحصص:\n{exc}").format(exc=exc), parent=win)
                rows = []
            key_by_id = {row['id']: row['label'] for row in rows}
            values = [f"{sid} - {label}" for sid, label in sorted(key_by_id.items(), key=lambda it: it[1])]
            stype_cb['values'] = values
            if values:
                stype_cb.current(0)
                stype_var.set(stype_cb.get())

        def load_results():
            for ch in tree.get_children():
                tree.delete(ch)
            cid = (class_var.get() or '').strip()
            raw = (stype_var.get() or '').strip()
            if not cid or not raw or ' - ' not in raw:
                messagebox.showwarning(_("تنبيه"), _("اختر قسماً ونوع الحصة أولاً"), parent=win)
                return
            try:
                stype_id = int(raw.split(' - ', 1)[0])
            except Exception:
                messagebox.showwarning(_("تنبيه"), _("نوع الحصة غير صالح"), parent=win)
                return
            threshold = int(thresh_var.get() or 3)

            start_date = (start_date_var.get() or "").strip()
            if start_date:
                parsed = None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        parsed = datetime.strptime(start_date, fmt).date()
                        break
                    except ValueError:
                        continue
                if not parsed:
                    messagebox.showwarning(_("تنبيه"), _("صيغة التاريخ غير صحيحة. استعمل YYYY-MM-DD أو DD/MM/YYYY"), parent=win)
                    return
                start_date = parsed.strftime("%Y-%m-%d")
            else:
                start_date = None

            # persist last chosen date (only if user provided one)
            if start_date:
                try:
                    set_default_exclusion_start_date(start_date)
                except Exception:
                    pass
            try:
                rows = compute_exclusion_risk(cid, stype_id, threshold, start_date)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر حساب الحالات:\n{exc}").format(exc=exc), parent=win)
                return
            for r in rows:
                tree.insert('', 'end', values=r)

        def export_results():
            cid = (class_var.get() or '').strip()
            raw = (stype_var.get() or '').strip()
            if not cid or not raw or ' - ' not in raw:
                messagebox.showwarning(_("تنبيه"), _("اختر قسماً ونوع الحصة أولاً"), parent=win)
                return
            if openpyxl is None:
                messagebox.showerror(_("خطأ"), _("حزمة openpyxl غير مثبتة في هذه البيئة. ثبتها ثم حاول مجددًا."), parent=win)
                return
            try:
                stype_id = int(raw.split(' - ', 1)[0])
            except Exception:
                messagebox.showwarning(_("تنبيه"), _("نوع الحصة غير صالح"), parent=win)
                return
            threshold = int(thresh_var.get() or 3)

            start_date = (start_date_var.get() or "").strip()
            if start_date:
                parsed = None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                    try:
                        parsed = datetime.strptime(start_date, fmt).date()
                        break
                    except ValueError:
                        continue
                if not parsed:
                    messagebox.showwarning(_("تنبيه"), _("صيغة التاريخ غير صحيحة. استعمل YYYY-MM-DD أو DD/MM/YYYY"), parent=win)
                    return
                start_date = parsed.strftime("%Y-%m-%d")
            else:
                start_date = None

            if start_date:
                try:
                    set_default_exclusion_start_date(start_date)
                except Exception:
                    pass
            try:
                rows = compute_exclusion_risk(cid, stype_id, threshold, start_date)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر حساب الحالات:\n{exc}").format(exc=exc), parent=win)
                return
            if not rows:
                messagebox.showinfo(_("لا توجد حالات"), _("لا يوجد طلاب مهددون بالإقصاء للمحددات الحالية"), parent=win)
                return
            fn = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel','*.xlsx')])
            if not fn:
                return
            try:
                wb = openpyxl.Workbook()
                export_exclusion_to_workbook(rows, [headers[c] for c in cols], wb)
                wb.save(fn)
                messagebox.showinfo(_("تم"), _("تصدير ناجح"), parent=win)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر التصدير:\n{exc}").format(exc=exc), parent=win)

        def manage_exceptions():
            cid = (class_var.get() or '').strip()
            raw = (stype_var.get() or '').strip()
            if not cid or not raw or ' - ' not in raw:
                messagebox.showwarning(_("تنبيه"), _("اختر قسماً ونوع الحصة أولاً"), parent=win)
                return
            try:
                stype_id = int(raw.split(' - ', 1)[0])
            except Exception:
                messagebox.showwarning(_("تنبيه"), _("نوع الحصة غير صالح"), parent=win)
                return

            try:
                studs = list_students_for_class(cid)
            except Exception as exc:
                messagebox.showerror(_("خطأ"), _("تعذر تحميل الطلبة:\n{exc}").format(exc=exc), parent=win)
                return
            current = list_exceptions(cid, stype_id)

            m = tk.Toplevel(win)
            m.title(_("إدارة الاستثناءات — {cid}").format(cid=cid))
            # enlarge modal so all buttons show comfortably
            W2, H2 = 640, 520
            try:
                m.update_idletasks()
                sw = m.winfo_screenwidth(); sh = m.winfo_screenheight()
                x = max(0, (sw // 2) - (W2 // 2)); y = max(0, (sh // 2) - (H2 // 2))
                m.geometry(f"{W2}x{H2}+{x}+{y}")
            except Exception:
                try:
                    m.geometry(f"{W2}x{H2}")
                except Exception:
                    pass
            m.transient(win)
            safe_grab(m)

            frame = ttk.Frame(m, padding=12)
            frame.pack(fill='both', expand=True)
            lbl = ttk.Label(frame, text=_(':علم الطلبة المستثنين من الإقصاء لهذا القسم ونوع الحصة'), font=('Tahoma', 10), justify='right')
            lbl.pack(anchor='e')

            # controls: select/deselect all
            controls_top = ttk.Frame(frame)
            controls_top.pack(fill='x', pady=(6, 6))

            def _select_all():
                for v in check_vars.values():
                    v.set(1)

            def _deselect_all():
                for v in check_vars.values():
                    v.set(0)

            # buttons will work even if check_vars is populated later
            ttk.Button(controls_top, text=_('اختيار الكل'), command=_select_all).pack(side='right', padx=6)
            ttk.Button(controls_top, text=_('إلغاء الكل'), command=_deselect_all).pack(side='right')

            canvas = tk.Canvas(frame)
            scrollbar = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
            list_frame = ttk.Frame(canvas)
            list_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
            canvas.create_window((0, 0), window=list_frame, anchor='nw')
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            check_vars = {}
            for s in studs:
                sid0 = s['StudentId']
                var = tk.IntVar(value=1 if sid0 in current else 0)
                cb = ttk.Checkbutton(
                    list_frame,
                    text=_("{name} {surname} ({sid})").format(name=s['Name'], surname=s['Surname'], sid=sid0),
                    variable=var
                )
                cb.pack(anchor='w', pady=2)
                check_vars[sid0] = var

            def save_exc():
                # require admin
                try:
                    if not self.require_admin_password():
                        messagebox.showwarning(_("تنبيه"), _("كلمة السر الإدارية مطلوبة للحفظ"), parent=m)
                        return
                except Exception:
                    messagebox.showwarning(_("تنبيه"), _("فشل التحقق من كلمة السر"), parent=m)
                    return

                # apply diffs
                for sid0, var in check_vars.items():
                    try:
                        if var.get():
                            add_exception(cid, stype_id, sid0)
                        else:
                            remove_exception(cid, stype_id, sid0)
                    except Exception:
                        # non-fatal — continue
                        pass
                m.destroy()
                load_results()

            btns = ttk.Frame(m, padding=8)
            btns.pack(fill='x')
            ttk.Button(btns, text=_('💾 حفظ'), command=save_exc).pack(side='right', padx=6)
            ttk.Button(btns, text=_('إلغاء'), command=m.destroy).pack(side='right')

        # wire events
        populate_classes()
        class_cb.bind('<<ComboboxSelected>>', lambda _e: populate_stypes())
        # initial populate stypes
        populate_stypes()

        ToolTip(class_cb, _('اختر القسم'))
        ToolTip(stype_cb, _('اختر نوع الحصة'))
