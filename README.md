# ميزان الطالب — MizanTalib

<p align="center">
  <img src="assets/logo.png" alt="MizanTalib Logo" width="140"/>
</p>

<div dir="rtl">

## 🇩🇿 بالعربية

**ميزان الطالب** هو تطبيق سطح مكتب مطوّر بـ Python/Tkinter لتسيير الحضور والمشاركة ونقاط الطلبة. موجّه للأساتذة في الجامعات الجزائرية (ليسانس / ماستر).

---

### ✨ المميزات

- **تسيير الأقسام** — إنشاء وتنظيم الأقسام حسب الطور، السنة، الفوج، الشعبة والتخصص.
- **تسيير الطلبة** — إضافة، تعديل وحذف الطلبة حسب القسم.
- **تسجيل الحضور بالكاميرا** — مسح بطاقات الطلبة عبر الكاميرا (باركود / QR) باستخدام OpenCV.
- **أنواع الحصص** — تحديد المواد وأنواع الحصص (محاضرة، TD، TP…).
- **متابعة المشاركة** — تسجيل مشاركة الطلبة في كل حصة.
- **الغيابات المبررة** — تسيير الغيابات مع التبريرات.
- **الإقصاءات** — تحديد الطلبة المقصيين حسب عتبة الغيابات.
- **الاختبارات والتقييم** — تسجيل واستشارة نقاط الطلبة.
- **التقارير النهائية** — توليد تقارير تلخيصية حسب القسم.
- **الأرشفة** — أرشفة واسترجاع بيانات السداسيات السابقة.
- **متعدد اللغات** — واجهة متاحة بالعربية 🇩🇿 والإنجليزية 🇬🇧 عبر gettext.
- **إدارة آمنة** — كلمة مرور المسؤول مشفرة بـ SHA-256.
- **بناء محمول** — إنشاء ملف تنفيذي Windows مستقل باستخدام PyInstaller.

---

### 🛠️ المتطلبات

- **Python 3.11+** (مُجرّب على Python 3.11 في Windows)
- **pip** (مدير حزم Python)
- **كاميرا ويب** (اختياري، لخاصية المسح بالكاميرا)

---

### 🚀 التثبيت

#### 1. استنساخ المستودع

</div>

```bash
git clone https://github.com/RaoufOuanis/MizanTalib.git
cd MizanTalib
```

<div dir="rtl">

#### 2. إنشاء بيئة افتراضية (مستحسن)

</div>

```bash
python -m venv .venv
```

<div dir="rtl">

تفعيل البيئة:

</div>

- **Windows (PowerShell)** :
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Windows (CMD)** :
  ```cmd
  .venv\Scripts\activate.bat
  ```

<div dir="rtl">

#### 3. تثبيت المكتبات

</div>

```bash
pip install pillow opencv-python pandas tkcalendar polib
```

<div dir="rtl">

#### 4. تشغيل التطبيق

</div>

```bash
python main.py
```

<div dir="rtl">

---

### 📦 بناء محمول (ملف تنفيذي Windows)

</div>

```bash
pip install pyinstaller
python build_portable.py
```

<div dir="rtl">

سيتم توليد الملف التنفيذي في مجلد `dist/MizanTalib/`.

---

### 🗄️ قاعدة البيانات

يستخدم التطبيق **SQLite** (`attendance.db`) مع الجداول الرئيسية:

| الجدول | الوصف |
|---|---|
| `classes` | تعريف الأقسام (الطور، السنة، الفوج…) |
| `students` | قائمة الطلبة المنتسبين لقسم |
| `sessions` | تسجيلات الحضور حسب الحصة |
| `session_types` | أنواع الحصص (المادة + النوع) |
| `tests` | نقاط التقييمات |
| `excused_absences` | الغيابات المبررة |
| `exclusions` | الطلبة المقصيين |
| `settings` | الإعدادات (كلمة مرور المسؤول، القسم النشط…) |

</div>

---
---

## 🇬🇧 English

**MizanTalib** (ميزان الطالب) is a desktop application built with Python/Tkinter for managing student attendance, participation, and grades. It is designed for teachers in Algerian universities (Licence / Master).

---

### ✨ Features

- **Class Management** — Create and organize classes by cycle, year, group, section, and specialty.
- **Student Management** — Add, edit, and delete students per class.
- **Camera Attendance** — Scan student cards via webcam (barcode / QR code) using OpenCV.
- **Session Types** — Define subjects and session types (lecture, TD, TP…).
- **Participation Tracking** — Record student participation for each session.
- **Excused Absences** — Manage absences with justifications.
- **Exclusions** — Mark students as excluded based on absence threshold.
- **Tests & Evaluations** — Record and view student grades.
- **Final Reports** — Generate summary reports per class.
- **Archiving** — Archive and restore data from previous semesters.
- **Multilingual** — Interface available in Arabic (🇩🇿) and English (🇬🇧) via gettext.
- **Secure Administration** — Admin password hashed with SHA-256.
- **Portable Build** — Create a standalone Windows executable with PyInstaller.

---

### 🛠️ Requirements

- **Python 3.11+** (tested with Python 3.11 on Windows)
- **pip** (Python package manager)
- A **webcam** (optional, for camera scan feature)

---

### 🚀 Installation

#### 1. Clone the repository

```bash
git clone https://github.com/RaoufOuanis/MizanTalib.git
cd MizanTalib
```

#### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
```

Activate it:

- **Windows (PowerShell)**:
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Windows (CMD)**:
  ```cmd
  .venv\Scripts\activate.bat
  ```

#### 3. Install dependencies

```bash
pip install pillow opencv-python pandas tkcalendar polib
```

#### 4. Run the application

```bash
python main.py
```

---

### 📦 Portable Build (Windows Executable)

```bash
pip install pyinstaller
python build_portable.py
```

The executable will be generated in the `dist/MizanTalib/` folder.

---

### 📁 Project Structure

```
MizanTalib/
├── main.py                  # Main entry point (splash screen)
├── app.py                   # Main Tkinter application
├── db.py                    # SQLite database init & management
├── admin.py                 # Admin authentication
├── camera.py                # Camera / scanner module (OpenCV)
├── center_window.py         # Window centering utility
├── tooltip.py               # Custom tooltips
├── build_portable.py        # PyInstaller build script
├── assets/
│   ├── logo.png
│   ├── logo.ico
│   └── fonts/               # Bundled fonts (Tajawal, etc.)
├── i18n/
│   ├── __init__.py           # Internationalization module
│   ├── messages.py           # Translation strings
│   └── locale/               # .po / .mo files (ar, en)
├── services/                 # Business logic layer
│   ├── attendance_service.py
│   ├── student_service.py
│   ├── class_service.py
│   ├── archive_service.py
│   └── ...
├── tabs/                     # UI tabs
│   ├── attendance_tab.py
│   ├── students_tab.py
│   ├── classes_tab.py
│   ├── tests_tab.py
│   └── ...
├── DB plan/
│   └── erDiagram.mmd        # ER Diagram (Mermaid)
└── tools/                    # Utility scripts
```

---

### 🗄️ Database

The application uses **SQLite** (`attendance.db`) with these main tables:

| Table | Description |
|---|---|
| `classes` | Class definitions (cycle, year, group…) |
| `students` | Students linked to a class |
| `sessions` | Attendance records per session |
| `session_types` | Session types (subject + type) |
| `tests` | Evaluation grades |
| `excused_absences` | Excused absences |
| `exclusions` | Excluded students |
| `settings` | Settings (admin password, active class…) |

---

### 🌐 Languages

The interface supports **Arabic** and **English**. The language can be changed from the application settings. Translations are managed via `gettext` (`.po` / `.mo` files).

---

## 🤝 Contribution

Contributions are welcome! Feel free to open an *issue* or a *pull request*.

---

## 📄 License

This project is licensed under the **MIT** License. See the `LICENSE` file for details.

---

## 👤 Author

**Raouf Ouanis** — [GitHub](https://github.com/RaoufOuanis)
