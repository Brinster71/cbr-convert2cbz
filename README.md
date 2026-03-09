# CBR to CBZ Web Converter

A small Flask app with a start page, path browser, single-file converter, and folder-based batch converter for `.cbr` to `.cbz`.

## Features

- Start page with optional path input (blank starts at configured root)
- Path browser that lists both files and folders
- File click opens single-file converter page
- Folder click opens batch conversion page
- Tries `7z`, then `zipfile`, then `rarfile` to handle mixed/mislabeled `.cbr` archives
- If a same-name sidecar XML exists (for example `MyBook.xml`), it is embedded into the output CBZ as `ComicInfo.xml`

## Quick start (Linux/macOS)

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:8000>.

## Quick start (Windows PowerShell)

From the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:8000>.

If PowerShell blocks activation scripts, run this once in PowerShell and retry:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## Why you don't see a `venv` folder

This project uses `.venv` (with a leading dot), not `venv`.

- The command `python3 -m venv .venv` **creates** that folder for you.
- Because it starts with a dot, it is hidden in normal `ls` output.
- Use `ls -la` to see it.

## Troubleshooting

- If `python3 -m venv .venv` fails, install your OS `venv` package first.
  - Debian/Ubuntu example: `sudo apt install python3-venv`
- If conversion fails for some `.cbr` files, install `7z` (`p7zip`) with your package manager.

## Optional configuration

The UI is restricted to `BROWSER_ROOT` (defaults to your home directory).

```bash
BROWSER_ROOT=/path/to/comics python app.py
```
