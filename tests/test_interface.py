import unittest
import tempfile
from pathlib import Path
import tkinter as tk
from unittest.mock import patch

from interface import DownloaderApp, LogWriter, app_dir, extract_links, normalize_links_text


class InterfaceTests(unittest.TestCase):
    def test_selected_browser_is_captured_before_worker_starts(self):
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as temp_dir, patch(
                "interface.DEFAULT_LINKS_FILE", Path(temp_dir) / "links.txt"
            ), patch("interface.threading.Thread") as worker:
                app = DownloaderApp(root)
                app.browser_var.set("Firefox")
                app.links_text.insert("1.0", "https://drive.google.com/file/d/example/view")
                app.start_download()
                self.assertEqual(worker.call_args.kwargs["args"][1], "firefox")
                self.assertTrue(app.running)
                self.assertEqual(str(app.browser_combo.cget("state")), "disabled")
                self.assertEqual(worker.call_count, 1)
        finally:
            root.destroy()

    def test_normalize_links_text_removes_empty_lines_and_comments(self):
        text = "\n# comentario\nhttps://example.com/a\n  https://example.com/b  \n"

        self.assertEqual(
            normalize_links_text(text),
            "https://example.com/a\nhttps://example.com/b\n",
        )

    def test_extract_links_from_mixed_text(self):
        text = """
        Parte 1: https://example.com/arquivo.part01.rar/file
        Parte 2 - baixar em (https://example.com/arquivo.part02.rar/file).
        Repetido: https://example.com/arquivo.part01.rar/file
        Outro: [https://example.com/arquivo.part03.rar/file],
        """

        self.assertEqual(
            extract_links(text),
            [
                "https://example.com/arquivo.part01.rar/file",
                "https://example.com/arquivo.part02.rar/file",
                "https://example.com/arquivo.part03.rar/file",
            ],
        )

    def test_normalize_links_text_extracts_links_from_descriptions(self):
        text = "Parte 1: https://example.com/a.rar\nParte 2: https://example.com/b.rar."

        self.assertEqual(
            normalize_links_text(text),
            "https://example.com/a.rar\nhttps://example.com/b.rar\n",
        )

    def test_log_writer_forwards_text_to_callback(self):
        chunks = []
        writer = LogWriter(chunks.append)

        self.assertEqual(writer.write("linha\n"), 6)
        writer.flush()

        self.assertEqual(chunks, ["linha\n"])

    def test_app_dir_uses_executable_parent_when_frozen(self):
        with patch("sys.frozen", True, create=True), patch(
            "sys.executable", "C:/Apps/LinkParts/LinkParts.exe"
        ):
            self.assertEqual(str(app_dir()).replace("\\", "/"), "C:/Apps/LinkParts")


if __name__ == "__main__":
    unittest.main()
