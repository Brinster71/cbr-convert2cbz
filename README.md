# CBR to CBZ Web Converter

A small Flask app that lets you browse folders, select `.cbr` files, and convert them to `.cbz`.

## Features

- Browser-based folder navigation
- Select one or more `.cbr` files in a folder
- Convert to `.cbz` in-place
- Uses `7z` if available, otherwise falls back to Python `rarfile`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Then open <http://localhost:8000>.

## Notes

- The UI is restricted to `BROWSER_ROOT` (defaults to your home directory).
- You can change root with:

```bash
BROWSER_ROOT=/path/to/comics python app.py
```

- `7z` is preferred for extraction. Install it with your package manager if conversions fail.
