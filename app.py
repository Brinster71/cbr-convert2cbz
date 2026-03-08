from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

# Root directory visible in the browser UI. Override with BROWSER_ROOT if needed.
BROWSER_ROOT = Path(os.environ.get("BROWSER_ROOT", Path.home())).resolve()


class ConversionError(RuntimeError):
    """Raised when CBR conversion cannot be completed."""


def _safe_path(user_path: str | None) -> Path:
    if not user_path:
        return BROWSER_ROOT

    candidate = Path(user_path).expanduser().resolve()
    try:
        candidate.relative_to(BROWSER_ROOT)
    except ValueError as exc:
        raise ConversionError("Requested path is outside of the allowed browser root.") from exc
    return candidate


def _extract_with_7z(source: Path, destination: Path) -> str | None:
    extractor = shutil.which("7z") or shutil.which("7za")
    if not extractor:
        return "7z/7za not installed"

    result = subprocess.run(
        [extractor, "x", str(source), f"-o{destination}", "-y"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return None

    return result.stderr.strip() or result.stdout.strip() or "Unknown 7z extraction error"


def _extract_with_zipfile(source: Path, destination: Path) -> str | None:
    try:
        with zipfile.ZipFile(source) as archive:
            archive.extractall(path=destination)
        return None
    except zipfile.BadZipFile:
        return "Not a ZIP-compatible archive"


def _extract_with_rarfile(source: Path, destination: Path) -> str | None:
    try:
        import rarfile
    except ImportError:
        return "rarfile module not installed"

    try:
        with rarfile.RarFile(source) as archive:
            archive.extractall(path=destination)
        return None
    except rarfile.Error as exc:
        return str(exc)


def _extract_archive(source: Path, destination: Path) -> None:
    errors: list[str] = []
    for label, method in (
        ("7z", _extract_with_7z),
        ("zipfile", _extract_with_zipfile),
        ("rarfile", _extract_with_rarfile),
    ):
        error = method(source, destination)
        if error is None:
            return
        errors.append(f"{label}: {error}")

    raise ConversionError(f"Failed to extract {source.name}. Tried: {' | '.join(errors)}")


def _list_entries(path: Path) -> list[Path]:
    return sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))


def _list_cbr_files(path: Path) -> list[Path]:
    return [entry for entry in _list_entries(path) if entry.is_file() and entry.suffix.lower() == ".cbr"]


def convert_cbr_to_cbz(source: Path) -> Path:
    if source.suffix.lower() != ".cbr":
        raise ConversionError(f"Unsupported file type: {source.name}")

    source = source.resolve()
    target = source.with_suffix(".cbz")

    with tempfile.TemporaryDirectory(prefix="cbr_extract_") as tmpdir:
        tmp_path = Path(tmpdir)
        _extract_archive(source, tmp_path)

        extracted_files = [path for path in sorted(tmp_path.rglob("*")) if path.is_file()]
        if not extracted_files:
            raise ConversionError(f"Extraction succeeded but no files were found in {source.name}")

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for file_path in extracted_files:
                zipf.write(file_path, file_path.relative_to(tmp_path))

    return target


@app.get("/")
def home():
    return render_template("home.html", browser_root=BROWSER_ROOT, error=request.args.get("error"))


@app.get("/browse")
def browse():
    requested_path = request.args.get("path")
    error = request.args.get("error")

    try:
        current = _safe_path(requested_path)
    except ConversionError as exc:
        return redirect(url_for("home", error=str(exc)))

    if not current.exists():
        return redirect(url_for("home", error="The requested path does not exist."))

    if current.is_file():
        return redirect(url_for("file_view", path=current))

    if not current.is_dir():
        return redirect(url_for("home", error="The requested path is not a regular file or directory."))

    entries = _list_entries(current)
    parent = None
    if current != BROWSER_ROOT:
        parent_candidate = current.parent
        if BROWSER_ROOT in [parent_candidate, *parent_candidate.parents]:
            parent = parent_candidate

    return render_template(
        "browse.html",
        browser_root=BROWSER_ROOT,
        current=current,
        parent=parent,
        entries=entries,
        error=error,
    )


@app.get("/folder")
def folder_view():
    requested_path = request.args.get("path")

    try:
        current = _safe_path(requested_path)
    except ConversionError as exc:
        return redirect(url_for("home", error=str(exc)))

    if not current.exists() or not current.is_dir():
        return redirect(url_for("home", error="Folder does not exist."))

    cbr_files = _list_cbr_files(current)

    return render_template(
        "folder.html",
        browser_root=BROWSER_ROOT,
        current=current,
        cbr_files=cbr_files,
        success=request.args.get("success"),
        error=request.args.get("error"),
    )


@app.get("/file")
def file_view():
    requested_path = request.args.get("path")

    try:
        file_path = _safe_path(requested_path)
    except ConversionError as exc:
        return redirect(url_for("home", error=str(exc)))

    if not file_path.exists() or not file_path.is_file():
        return redirect(url_for("home", error="File does not exist."))

    return render_template(
        "file.html",
        browser_root=BROWSER_ROOT,
        file_path=file_path,
        success=request.args.get("success"),
        error=request.args.get("error"),
    )


@app.post("/convert-folder")
def convert_folder():
    current_dir = request.form.get("current_dir", "")
    selected_files = request.form.getlist("selected_files")

    try:
        current = _safe_path(current_dir)
    except ConversionError as exc:
        return redirect(url_for("home", error=str(exc)))

    if not selected_files:
        return redirect(url_for("folder_view", path=current, error="Please select at least one .cbr file."))

    converted: list[str] = []
    failed: list[str] = []

    for name in selected_files:
        try:
            source = (current / name).resolve()
            source.relative_to(current)
            if not source.exists() or not source.is_file():
                raise ConversionError(f"File not found: {name}")
            target = convert_cbr_to_cbz(source)
            converted.append(target.name)
        except (ConversionError, ValueError) as exc:
            failed.append(f"{name} ({exc})")

    if converted and not failed:
        return redirect(url_for("folder_view", path=current, success=f"Converted {len(converted)} file(s): {', '.join(converted)}"))

    if converted and failed:
        return redirect(
            url_for(
                "folder_view",
                path=current,
                success=f"Converted {len(converted)} file(s): {', '.join(converted)}",
                error=f"Failed {len(failed)} file(s): {'; '.join(failed)}",
            )
        )

    return redirect(url_for("folder_view", path=current, error=f"Failed {len(failed)} file(s): {'; '.join(failed)}"))


@app.post("/convert-file")
def convert_file():
    raw_path = request.form.get("file_path", "")

    try:
        file_path = _safe_path(raw_path)
    except ConversionError as exc:
        return redirect(url_for("home", error=str(exc)))

    if not file_path.exists() or not file_path.is_file():
        return redirect(url_for("home", error="File does not exist."))

    try:
        target = convert_cbr_to_cbz(file_path)
        return redirect(url_for("file_view", path=file_path, success=f"Converted to {target.name}"))
    except ConversionError as exc:
        return redirect(url_for("file_view", path=file_path, error=str(exc)))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
