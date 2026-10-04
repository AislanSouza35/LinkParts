from pathlib import Path
import tempfile
import re
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from http.cookiejar import Cookie, MozillaCookieJar

import baixar_e_juntar as downloader

from baixar_e_juntar import (
    download_all_parts,
    download_part,
    filename_from_link,
    is_multipart_rar,
    join_parts,
    part_path,
    read_links,
    resolve_mediafire_direct_link,
)


class BaixarEJuntarTests(unittest.TestCase):
    def test_authenticated_drive_requests_use_supported_browser_identity(self):
        def hosted_file(**kwargs):
            identity = re.search(r"Chrome/(\d+)", kwargs.get("user_agent", "Chrome/39.0"))
            if identity is None or int(identity[1]) < 100:
                raise downloader.gdown.exceptions.FileURLRetrievalError("sign-in requested")
            if kwargs.get("skip_download"):
                return SimpleNamespace(path="test.part01.rar")
            Path(kwargs["output"]).write_bytes(b"Rar!\x1a\x07\x01\x00test")
            return kwargs["output"]

        with tempfile.TemporaryDirectory() as temp_dir, patch("gdown.download", side_effect=hosted_file):
            link = "https://drive.google.com/file/d/example/view"
            name = filename_from_link(link, cookies_file="synthetic-session.txt")
            destination = Path(temp_dir) / name
            self.assertTrue(download_part(link, destination, cookies_file="synthetic-session.txt"))
            self.assertTrue(destination.read_bytes().startswith(b"Rar!\x1a\x07"))

    def test_imported_cookie_file_filters_domains_and_is_cleaned_up(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "session.txt"
            jar = MozillaCookieJar(str(source))
            for domain in [".google.com", ".example.com"]:
                jar.set_cookie(Cookie(
                    0, "session", "synthetic", None, False, domain, True,
                    True, "/", True, True, None, True, None, None, {},
                ))
            jar.save(ignore_discard=True)
            with downloader.google_drive_session(None, cookies_source=source) as session:
                imported = MozillaCookieJar(session)
                imported.load(ignore_discard=True)
                self.assertEqual([c.domain for c in imported], [".google.com"])
                temporary = Path(session)
            self.assertFalse(temporary.parent.exists())
            self.assertTrue(source.exists())

    def test_browser_session_is_used_for_metadata_and_download_then_removed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            links = root / "links.txt"
            links.write_text("https://drive.google.com/file/d/example/view", encoding="utf-8")
            session_paths = []

            def import_session(*, browser, cookies_file):
                self.assertEqual(browser, "firefox")
                jar = MozillaCookieJar(cookies_file)
                jar.set_cookie(Cookie(
                    0, "test_session", "synthetic", None, False, ".google.com", True,
                    True, "/", True, True, None, True, None, None, {},
                ))
                jar.save(ignore_discard=True)
                session_paths.append(Path(cookies_file))
                return 1

            def drive_download(**kwargs):
                self.assertTrue(kwargs["use_cookies"])
                jar = MozillaCookieJar(kwargs["cookies_file"])
                jar.load(ignore_discard=True)
                self.assertEqual(next(iter(jar)).value, "synthetic")
                if kwargs.get("skip_download"):
                    return SimpleNamespace(path="test.part01.rar")
                Path(kwargs["output"]).write_bytes(b"Rar!\x1a\x07\x01\x00test")
                return kwargs["output"]

            with patch("gdown.download._import_cookies_from_browser", side_effect=import_session), patch(
                "gdown.download", side_effect=drive_download
            ):
                result = downloader.run_download(
                    links, root / "final.bin", root / "partes", browser="firefox"
                )
            self.assertEqual(result, 0)
            self.assertTrue((root / "partes" / "test.part01.rar").exists())
            self.assertFalse((root / "final.bin").exists())
            self.assertEqual(len(session_paths), 1)
            self.assertFalse(session_paths[0].parent.exists())

    def test_browser_without_google_session_stops_before_download(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            links = root / "links.txt"
            links.write_text("https://drive.google.com/file/d/example/view", encoding="utf-8")
            with patch("gdown.download._import_cookies_from_browser", return_value=0), patch(
                "gdown.download", side_effect=AssertionError("should not download without session")
            ):
                self.assertEqual(downloader.run_download(
                    links, root / "out.bin", root / "partes", browser="chrome"
                ), 1)

    def test_browser_session_is_removed_when_drive_rejects_download(self):
        session_paths = []
        def import_session(*, browser, cookies_file):
            Path(cookies_file).write_text("synthetic", encoding="utf-8")
            session_paths.append(Path(cookies_file))
            return 1
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            links = root / "links.txt"
            links.write_text("https://drive.google.com/file/d/example/view", encoding="utf-8")
            with patch("gdown.download._import_cookies_from_browser", side_effect=import_session), patch(
                "gdown.download", side_effect=ValueError("quota exceeded")
            ):
                self.assertEqual(downloader.run_download(
                    links, root / "out.bin", root / "partes", browser="firefox"
                ), 1)
            self.assertFalse(session_paths[0].parent.exists())

    def test_drive_filename_preserves_rar_volume_name(self):
        with patch("gdown.download", return_value=SimpleNamespace(path="Ktp26.part01.rar")):
            self.assertEqual(
                filename_from_link("https://drive.google.com/file/d/example/view?usp=sharing"),
                "Ktp26.part01.rar",
            )

    def test_drive_download_uses_file_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "Ktp26.part01.rar"

            def drive_download(**kwargs):
                Path(kwargs["output"]).write_bytes(b"Rar!\x1a\x07\x01\x00archive")
                return kwargs["output"]

            with patch("gdown.download", side_effect=drive_download), patch(
                "baixar_e_juntar.urlretrieve", side_effect=ValueError("preview is not a file")
            ):
                self.assertTrue(download_part("https://drive.google.com/file/d/example/view", destination))
            self.assertEqual(destination.read_bytes(), b"Rar!\x1a\x07\x01\x00archive")

    def test_failed_drive_download_does_not_leave_completed_part(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "Ktp26.part01.rar"

            def interrupted_download(**kwargs):
                Path(kwargs["output"]).write_bytes(b"partial")
                raise OSError("connection lost")

            with patch("gdown.download", side_effect=interrupted_download), patch(
                "baixar_e_juntar.urlretrieve", side_effect=ValueError("preview is not a file")
            ):
                self.assertFalse(download_part("https://drive.google.com/file/d/example/view", destination))
            self.assertFalse(destination.exists())

    def test_drive_metadata_failure_is_reported_without_crashing(self):
        from baixar_e_juntar import run_download
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            links = root / "links.txt"
            links.write_text("https://drive.google.com/file/d/example/view", encoding="utf-8")
            with patch("gdown.download", side_effect=ValueError("access denied")), patch(
                "baixar_e_juntar.download_part", return_value=True
            ):
                self.assertEqual(run_download(links, root / "final.bin", root / "partes"), 1)

    def test_read_links_ignores_empty_lines_and_comments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            links_file = Path(temp_dir) / "links.txt"
            links_file.write_text(
                "\n# comentario\nhttps://example.com/parte1\n  https://example.com/parte2  \n",
                encoding="utf-8",
            )

            self.assertEqual(
                read_links(links_file),
                [
                    "https://example.com/parte1",
                    "https://example.com/parte2",
                ],
            )

    def test_part_path_uses_ordered_numbered_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parts_dir = Path(temp_dir)

            self.assertEqual(part_path(parts_dir, 1), parts_dir / "parte-0001.part")
            self.assertEqual(part_path(parts_dir, 12), parts_dir / "parte-0012.part")

    def test_join_parts_preserves_binary_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            first = temp_path / "parte-0001.part"
            second = temp_path / "parte-0002.part"
            output = temp_path / "final.bin"
            first.write_bytes(b"abc")
            second.write_bytes(b"123")

            join_parts([first, second], output)

            self.assertEqual(output.read_bytes(), b"abc123")

    def test_download_part_skips_existing_non_empty_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "parte-0001.part"
            destination.write_bytes(b"already here")

            with patch("baixar_e_juntar.urlretrieve") as urlretrieve:
                self.assertTrue(download_part("https://example.com/parte1", destination))

            urlretrieve.assert_not_called()

    def test_download_all_parts_returns_numbered_paths_in_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parts_dir = Path(temp_dir)

            with patch("baixar_e_juntar.download_part", return_value=True):
                part_files = download_all_parts(["u1", "u2"], parts_dir)

            self.assertEqual(
                part_files,
                [
                    parts_dir / "parte-0001.part",
                    parts_dir / "parte-0002.part",
                ],
            )

    def test_download_all_parts_can_keep_names_from_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parts_dir = Path(temp_dir)
            links = [
                "https://www.mediafire.com/file/a/ktn25.part01.rar/file",
                "https://www.mediafire.com/file/b/ktn25.part02.rar/file",
            ]

            with patch("baixar_e_juntar.download_part", return_value=True):
                part_files = download_all_parts(links, parts_dir, keep_names=True)

            self.assertEqual(
                part_files,
                [
                    parts_dir / "ktn25.part01.rar",
                    parts_dir / "ktn25.part02.rar",
                ],
            )

    def test_filename_from_mediafire_link_uses_archive_name(self):
        link = "https://www.mediafire.com/file/abc123/ktn25.part01.rar/file"

        self.assertEqual(filename_from_link(link), "ktn25.part01.rar")

    def test_is_multipart_rar_detects_numbered_rar_parts(self):
        self.assertTrue(
            is_multipart_rar(
                [
                    "ktn25.part01.rar",
                    "ktn25.part02.rar",
                    "ktn25.part03.rar",
                ]
            )
        )

    def test_resolve_mediafire_direct_link_reads_download_button(self):
        html = '''
        <a href="https://download123.mediafire.com/token/abc123/ktn25.part01.rar">
            Download (9.8GB)
        </a>
        '''

        self.assertEqual(
            resolve_mediafire_direct_link(
                "https://www.mediafire.com/file/abc123/ktn25.part01.rar/file",
                html,
            ),
            "https://download123.mediafire.com/token/abc123/ktn25.part01.rar",
        )


if __name__ == "__main__":
    unittest.main()
