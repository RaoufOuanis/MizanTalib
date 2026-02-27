import ast
import re
from pathlib import Path

import polib

ROOT = Path(r"C:\Users\Raooooof\Desktop\projectSep")
PO_PATH = ROOT / "i18n" / "locale" / "en" / "LC_MESSAGES" / "mizan_talib.po"


def iter_python_files(root: Path) -> list[Path]:
    py_files: list[Path] = []
    for p in root.rglob("*.py"):
        sp = str(p)
        if "\\.venv\\" in sp or "\\build\\" in sp or "\\__pycache__\\" in sp:
            continue
        py_files.append(p)
    return py_files


class GettextVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.literals: set[str] = set()
        self.occurrences: dict[str, set[str]] = {}

    def _record(self, msgid: str, filename: str) -> None:
        self.literals.add(msgid)
        self.occurrences.setdefault(msgid, set()).add(filename)

    def visit_Call(self, node: ast.Call):
        # Match _('...') where first arg is a string literal
        func = node.func
        is_gettext = isinstance(func, ast.Name) and func.id == "_"
        if is_gettext and node.args:
            arg0 = node.args[0]
            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                # filename is injected via attribute by the caller
                filename = getattr(self, "_current_file", "<unknown>")
                self._record(arg0.value, filename)
        self.generic_visit(node)


def main() -> None:
    po = polib.pofile(str(PO_PATH))
    po_msgids = {e.msgid for e in po if e.msgid}

    visitor = GettextVisitor()
    parse_issues: list[tuple[str, str]] = []

    py_files = iter_python_files(ROOT)
    for p in py_files:
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
            visitor._current_file = str(p.relative_to(ROOT))  # type: ignore[attr-defined]
            visitor.visit(tree)
        except Exception as e:
            parse_issues.append((str(p.relative_to(ROOT)), str(e)))

    missing = sorted([s for s in visitor.literals if s not in po_msgids])

    arabic_re = re.compile(r"[\u0600-\u06FF]")
    emojiish_re = re.compile(r"[\U0001F300-\U0001FAFF]")
    focus = [s for s in missing if arabic_re.search(s) or emojiish_re.search(s)]

    print("py_files", len(py_files))
    print("gettext_literals", len(visitor.literals))
    print("po_msgids", len(po_msgids))
    print("missing", len(missing))
    print("missing_focus", len(focus))
    for s in focus[:120]:
        print("MISS", repr(s))

    report_path = ROOT / "tools" / "i18n_missing_report.txt"
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as fh:
            fh.write(f"py_files={len(py_files)}\n")
            fh.write(f"gettext_literals={len(visitor.literals)}\n")
            fh.write(f"po_msgids={len(po_msgids)}\n")
            fh.write(f"missing={len(missing)}\n")
            fh.write(f"missing_focus={len(focus)}\n\n")
            for msgid in focus:
                files = sorted(visitor.occurrences.get(msgid, set()))
                fh.write(msgid + "\n")
                for f in files[:10]:
                    fh.write(f"  - {f}\n")
                if len(files) > 10:
                    fh.write(f"  - ... (+{len(files) - 10} more)\n")
                fh.write("\n")
        print(f"\nWrote report: {report_path}")
    except Exception as e:
        print(f"\nFailed to write report: {e}")

    if parse_issues:
        print("\nParse issues (non-fatal):")
        for f, e in parse_issues[:50]:
            print(" -", f, e)


if __name__ == "__main__":
    main()
