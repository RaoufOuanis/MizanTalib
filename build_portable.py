from __future__ import annotations
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Iterable, List

try:
    import PyInstaller.__main__  # type: ignore[import]
except ModuleNotFoundError as exc:  # pragma: no cover - build-time dependency
    raise RuntimeError(
        "PyInstaller غير مثبت. ثبت الحزمة عبر 'pip install pyinstaller' قبل تشغيل build_portable.py"
    ) from exc

try:
    from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files  # type: ignore
except ModuleNotFoundError:
    collect_dynamic_libs = collect_data_files = None  # type: ignore

ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"

EXECUTABLE_BASE_NAME = "MizanTalib"
DISPLAY_DIR_NAME = "ميزان الطالب"
DISPLAY_EXE_NAME = f"{DISPLAY_DIR_NAME}.exe"


def _format_add_data(source: Path, target: str) -> str:
    return f"--add-data={source}{os.pathsep}{target}"


def build() -> None:
    _ensure_64bit_environment()
    data_args = [
        _format_add_data(ROOT_DIR / "assets", "assets"),
        _format_add_data(ROOT_DIR / "i18n" / "locale", "i18n/locale"),
    ]
    # Ajoute polib comme module caché si utilisé à runtime
    hidden_imports = ["cv2", "polib", "pandas", "pandas._libs", "tkcalendar", "tkinter", "_tkinter"]
    binary_args = list(_collect_binary_args())
    data_args.extend(_collect_tk_tcl_data_args())
    _log_bundle_summary(binary_args)

    PyInstaller.__main__.run([
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--exclude-module=numpy.tests",
        "--exclude-module=numpy.testing",
        "--exclude-module=PIL.ImageQt",
        f"--name={EXECUTABLE_BASE_NAME}",
        f"--icon={ROOT_DIR / 'assets' / 'logo.ico'}",
        *(f"--hidden-import={mod}" for mod in hidden_imports),
        *_runtime_hook_args(),
        *binary_args,
        *data_args,
        str(ROOT_DIR / "main.py"),
    ])

    produced_dir = DIST_DIR / EXECUTABLE_BASE_NAME
    target_dir = DIST_DIR / DISPLAY_DIR_NAME

    if not produced_dir.exists():
        raise RuntimeError("تعذر العثور على مجلد الإخراج الذي أنشأه PyInstaller.")

    try:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        produced_dir.rename(target_dir)
    except OSError as exc:  # pragma: no cover - filesystem specific
        raise RuntimeError(
            f"تعذر إعادة تسمية مجلد الإصدار إلى {DISPLAY_DIR_NAME}: {exc}"
        ) from exc

    _ensure_font_assets(target_dir)

    # Ensure Tcl/Tk runtime data exists inside the built folder.
    # This prevents common runtime crashes on other machines:
    #   "tcl data not found" / "Can't find a usable init.tcl"
    _ensure_tk_tcl_runtime_data(target_dir)

    # Some PyInstaller runtime hooks (pyi_rth__tkinter.py) expect the Tcl data
    # directory to be named '_tcl_data' (or '_internal/_tcl_data'). On some
    # environments PyInstaller collects those files under a directory named
    # '_tk_data' instead. If that happens, create a copy named '_tcl_data' so
    # the built executable can find the Tcl data on other machines.
    try:
        internal_dir = target_dir / "_internal"
        tk_data = None
        tcl_data = None

        # possible locations
        candidates = [
            (target_dir / "_tk_data", target_dir / "_tcl_data"),
            (internal_dir / "_tk_data", internal_dir / "_tcl_data"),
        ]
        for src, dst in candidates:
            try:
                if src.exists() and src.is_dir() and not dst.exists():
                    # copy tree to the expected destination name
                    shutil.copytree(src, dst)
                    print(f"[build_portable] duplicated Tcl data: {src} -> {dst}")
            except Exception:
                # non-fatal; continue checking other candidates
                continue
    except Exception:
        # Best-effort only; don't fail the build for this housekeeping step.
        pass

    produced_exe = target_dir / f"{EXECUTABLE_BASE_NAME}.exe"
    target_exe = target_dir / DISPLAY_EXE_NAME
    if produced_exe.exists():
        try:
            if target_exe.exists():
                target_exe.unlink()
            produced_exe.rename(target_exe)
        except OSError as exc:  # pragma: no cover - filesystem specific
            raise RuntimeError(
                f"تعذر إعادة تسمية الملف التنفيذي إلى {DISPLAY_EXE_NAME}: {exc}"
            ) from exc


def _collect_binary_args() -> Iterable[str]:
    if collect_dynamic_libs is None:
        return []

    binaries: List[str] = []
    for module in ("cv2",):
        try:
            libs = collect_dynamic_libs(module)
        except Exception:
            libs = []
        for src, dest in libs:
            if module == "cv2" and not _is_64bit_binary(Path(src)):
                continue
            binaries.append(f"--add-binary={src}{os.pathsep}{dest}")
    return binaries


def _python_base_prefixes() -> list[Path]:
    bases: list[Path] = []
    for base in (
        getattr(sys, "base_prefix", None),
        getattr(sys, "real_prefix", None),
        getattr(sys, "prefix", None),
    ):
        if not base:
            continue
        try:
            bases.append(Path(str(base)))
        except Exception:
            continue
    # de-duplicate while preserving order
    seen: set[str] = set()
    unique: list[Path] = []
    for b in bases:
        key = str(b).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(b)
    return unique


def _find_python_tcl_root() -> Path | None:
    for base in _python_base_prefixes():
        candidate = base / "tcl"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return None


def _collect_tk_tcl_data_args() -> list[str]:
    tcl_root = _find_python_tcl_root()
    if not tcl_root:
        return []

    args: list[str] = []
    tcl_src = tcl_root / "tcl8.6"
    tk_src = tcl_root / "tk8.6"

    # Note: PyInstaller's tkinter runtime hook typically searches under
    # sys._MEIPASS/_tcl_data and sys._MEIPASS/_tk_data.
    if tcl_src.exists() and tcl_src.is_dir():
        args.append(_format_add_data(tcl_src, "_tcl_data"))
    if tk_src.exists() and tk_src.is_dir():
        args.append(_format_add_data(tk_src, "_tk_data"))
    return args


def _ensure_tk_tcl_runtime_data(target_dir: Path) -> None:
    tcl_root = _find_python_tcl_root()
    if not tcl_root:
        print("[build_portable] تحذير: لم يتم العثور على مجلد Tcl ضمن تثبيت بايثون.")
        return

    # For one-dir builds, PyInstaller places most runtime files under _internal.
    internal_dir = target_dir / "_internal"
    dest_bases = [internal_dir, target_dir] if internal_dir.exists() else [target_dir]

    pairs = [
        (tcl_root / "tcl8.6", "_tcl_data"),
        (tcl_root / "tk8.6", "_tk_data"),
    ]

    for src, dest_name in pairs:
        if not (src.exists() and src.is_dir()):
            continue
        for base in dest_bases:
            dst = base / dest_name
            try:
                if not dst.exists():
                    shutil.copytree(src, dst)
                    print(f"[build_portable] bundled {dest_name}: {src} -> {dst}")
            except Exception as exc:
                print(f"[build_portable] تحذير: تعذر تضمين {dest_name}: {exc}")


def _runtime_hook_args() -> list[str]:
    hook = ROOT_DIR / "hooks" / "runtime_dll_paths.py"
    return [f"--runtime-hook={hook}"] if hook.exists() else []


def _collect_data_args() -> Iterable[str]:
    if collect_data_files is None:
        return []

    data_args: list[str] = []
    includes = {
        "PIL": ["*.icc"],
    }
    for module, patterns in includes.items():
        try:
            files = collect_data_files(module, includes=patterns)
        except Exception:
            files = []
        for src, dest in files:
            data_args.append(_format_add_data(Path(src), dest))
    return data_args





def _is_64bit_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            mz = fh.read(2)
            if mz != b"MZ":
                return True
            fh.seek(60)
            offset = int.from_bytes(fh.read(4), "little")
            fh.seek(offset + 4)
            machine = int.from_bytes(fh.read(2), "little")
            return machine == 0x8664
    except Exception:
        return True


def _ensure_64bit_environment() -> None:
    arch, _ = platform.architecture()
    if arch != "64bit":
        raise RuntimeError("يجب استعمال بايثون 64-بت لبناء نسخة محمولة تدعم الكاميرا.")


def _log_bundle_summary(binary_args: List[str]) -> None:
    print("[build_portable] سيتم تضمين الملفات التالية:")
    for item in binary_args:
        print("  ", item)


def _ensure_font_assets(target_dir: Path) -> None:
    """تأكد من أن خط Tajawal والأصول المشابهة متاحة داخل حزمة الإصدار."""

    fonts_src = ROOT_DIR / "assets" / "fonts"
    if not fonts_src.exists():
        return

    fonts_dest = target_dir / "assets" / "fonts"
    try:
        fonts_dest.parent.mkdir(parents=True, exist_ok=True)
        fonts_dest.mkdir(parents=True, exist_ok=True)

        for item in fonts_src.iterdir():
            dest_path = fonts_dest / item.name
            if item.is_dir():
                shutil.copytree(item, dest_path, dirs_exist_ok=True)
            elif item.is_file():
                shutil.copy2(item, dest_path)
        print("[build_portable] تم التأكد من تضمين خطوط الواجهة (assets/fonts).")
    except Exception as exc:  # pragma: no cover - best-effort copy
        print(f"[build_portable] تحذير: تعذر نسخ الخطوط إلى الحزمة: {exc}")


if __name__ == "__main__":
    build()
