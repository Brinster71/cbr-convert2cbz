import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path


class _FakeFlask:
    def __init__(self, _name: str):
        pass

    def get(self, _route: str):
        def decorator(func):
            return func

        return decorator

    def post(self, _route: str):
        def decorator(func):
            return func

        return decorator


fake_flask_module = types.SimpleNamespace(
    Flask=_FakeFlask,
    redirect=lambda value: value,
    render_template=lambda *args, **kwargs: "",
    request=types.SimpleNamespace(args={}, form=types.SimpleNamespace(get=lambda *a, **k: "", getlist=lambda *a, **k: [])),
    url_for=lambda *args, **kwargs: "",
)
sys.modules.setdefault("flask", fake_flask_module)

from app import convert_cbr_to_cbz


class ConversionTests(unittest.TestCase):
    def test_sidecar_xml_is_embedded_as_comicinfo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "book.cbr"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("page1.jpg", b"fake-image")

            source.with_suffix(".xml").write_text("<ComicInfo><Title>Book</Title></ComicInfo>", encoding="utf-8")

            target = convert_cbr_to_cbz(source)

            with zipfile.ZipFile(target) as archive:
                names = set(archive.namelist())
                self.assertIn("ComicInfo.xml", names)
                self.assertIn("page1.jpg", names)

    def test_existing_comicinfo_in_archive_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "book.cbr"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr("page1.jpg", b"fake-image")
                archive.writestr("ComicInfo.xml", "<ComicInfo><Title>FromArchive</Title></ComicInfo>")

            source.with_suffix(".xml").write_text("<ComicInfo><Title>FromSidecar</Title></ComicInfo>", encoding="utf-8")

            target = convert_cbr_to_cbz(source)

            with zipfile.ZipFile(target) as archive:
                content = archive.read("ComicInfo.xml").decode("utf-8")
                self.assertIn("FromArchive", content)
                self.assertNotIn("FromSidecar", content)


if __name__ == "__main__":
    unittest.main()
