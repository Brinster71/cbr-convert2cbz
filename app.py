from __future__ import annotations

import os
import shutil
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
    except ValueError as exc:  # pragma: no cover - tiny guard clause
        raise ConversionError("Requested path is outside of the allowed browser root.") from exc
    return candidate


def _list_directory(path: Path) -> tuple[list[Path], list[Path]]:
    dirs: list[Path] = []
    cbr_files: list[Path] = []

    for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.is_dir():
            dirs.append(entry)
        elif entry.is_file() and entry.suffix.lower() == ".cbr":
            cbr_files.append(entry)

    return dirs, cbr_files


def convert_cbr_to_cbz(source: Path) -> Path:
    """Convert a .cbr file into a .cbz file in the same directory."""
    if source.suffix.lower() != ".cbr":
        raise ConversionError(f"Unsupported file type: {source.name}")

    source = source.resolve()
    target = source.with_suffix(".cbz")

    with tempfile.TemporaryDirectory(prefix="cbr_extract_") as tmpdir:
        tmp_path = Path(tmpdir)

        extractor = shutil.which("7z") or shutil.which("7za")
        if extractor:
            import subprocess

            result = subprocess.run(
                [extractor, "x", str(source), f"-o{tmp_path}", "-y"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise ConversionError(
                    f"Failed to extract {source.name} with 7-Zip: {result.stderr.strip() or result.stdout.strip()}"
                )
        else:
            try:
                import rarfile
            except ImportError as exc:
                raise ConversionError(
                    "No extractor available. Install 7z (preferred) or install the 'rarfile' Python package."
                ) from exc

            try:
                with rarfile.RarFile(source) as archive:
                    archive.extractall(path=tmp_path)
            except rarfile.Error as exc:
                raise ConversionError(f"Failed to read {source.name}: {exc}") from exc

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
            for file_path in sorted(tmp_path.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmp_path)
                    zipf.write(file_path, arcname)

    return target


@app.get("/")
def index():
    error = request.args.get("error")
    success = request.args.get("success")
    requested_path = request.args.get("path")

    try:
        current = _safe_path(requested_path)
    except ConversionError as exc:
        return redirect(url_for("index", error=str(exc)))

    if not current.exists() or not current.is_dir():
        return redirect(url_for("index", error="The requested directory does not exist."))

    dirs, cbr_files = _list_directory(current)

    parent = None
    if current != BROWSER_ROOT:
        parent_candidate = current.parent
        if BROWSER_ROOT in [parent_candidate, *parent_candidate.parents]:
            parent = parent_candidate

    return render_template(
        "index.html",
        browser_root=BROWSER_ROOT,
        current=current,
        parent=parent,
        directories=dirs,
        cbr_files=cbr_files,
        success=success,
        error=error,
    )


@app.post("/convert")
def convert():
    current_dir = request.form.get("current_dir", "")
    selected_files = request.form.getlist("selected_files")

    try:
        current = _safe_path(current_dir)
    except ConversionError as exc:
        return redirect(url_for("index", error=str(exc)))

    if not selected_files:
        return redirect(url_for("index", path=current, error="Please select at least one .cbr file."))

    converted: list[str] = []
    try:
        for name in selected_files:
            source = (current / name).resolve()
            source.relative_to(current)
            if not source.exists() or not source.is_file():
                raise ConversionError(f"File not found: {name}")
            target = convert_cbr_to_cbz(source)
            converted.append(target.name)
    except (ConversionError, ValueError) as exc:
        return redirect(url_for("index", path=current, error=str(exc)))

    message = f"Converted {len(converted)} file(s): {', '.join(converted)}"
    return redirect(url_for("index", path=current, success=message))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
