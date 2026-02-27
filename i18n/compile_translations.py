from pathlib import Path

def compile_mo_files(locale_dir: Path, domain: str = "mizan_talib"):
    try:
        import polib  # type: ignore
    except ModuleNotFoundError:
        raise SystemExit(
            "\n".join(
                [
                    "[i18n] تعذر تجميع ملفات الترجمة لأن الحزمة polib غير مثبتة في بايثون الحالي.",
                    "",
                    "حلول مقترحة:",
                    "1) شغّل السكربت عبر نفس بايثون الخاص بالمشروع (.venv):",
                    "   .venv\\Scripts\\python.exe i18n\\compile_translations.py",
                    "2) أو ثبّت polib في بايثون الحالي:",
                    "   python -m pip install polib",
                    "",
                    "ملاحظة: وجود ملف .po وحده لا يكفي؛ التطبيق يحتاج ملف .mo ليقرأ الترجمة.",
                ]
            )
        )
    for lang_dir in locale_dir.iterdir():
        lc_messages = lang_dir / "LC_MESSAGES"
        po_file = lc_messages / f"{domain}.po"
        mo_file = lc_messages / f"{domain}.mo"
        if po_file.exists():
            print(f"Compiling {po_file} -> {mo_file}")
            try:
                po = polib.pofile(str(po_file))
                po.save_as_mofile(str(mo_file))
            except Exception as e:
                print(f"Failed to compile {po_file}: {e}")

if __name__ == "__main__":
    here = Path(__file__).parent
    locale_dir = here / "locale"
    compile_mo_files(locale_dir)
    print("Done.")
