from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
