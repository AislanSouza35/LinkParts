from pathlib import Path
import contextlib
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from baixar_e_juntar import DEFAULT_PARTS_DIR, run_download


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = app_dir()
DEFAULT_LINKS_FILE = APP_DIR / "links.txt"
DEFAULT_OUTPUT_FILE = APP_DIR / "downloads" / "arquivo_final.bin"


TRAILING_URL_CHARS = ".,;:!?)]}>\"'"
BROWSER_SESSIONS = {
    "Sem login": None, "Chrome": "chrome", "Edge": "edge", "Firefox": "firefox",
    "Sessao importada": None,
}


def extract_links(text: str) -> list[str]:
    links = []
    seen = set()
    for match in re.finditer(r"https?://\S+", text):
        link = match.group(0).strip().rstrip(TRAILING_URL_CHARS)
        if link and link not in seen:
            links.append(link)
            seen.add(link)
    return links


def normalize_links_text(text: str) -> str:
    links = extract_links(text)
    if links:
        return "\n".join(links) + "\n"

    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


class LogWriter:
    def __init__(self, callback):
        self.callback = callback

    def write(self, text: str) -> int:
        if text:
            self.callback(text)
        return len(text)

    def flush(self) -> None:
        return None


class DownloaderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Baixar partes")
        self.root.geometry("820x620")
        self.root.minsize(720, 520)

        self.output_var = tk.StringVar(value=str(DEFAULT_OUTPUT_FILE))
        self.browser_var = tk.StringVar(value="Sem login")
        self.cookies_source = None
        self.status_var = tk.StringVar(value="Cole os links ou carregue o links.txt.")
        self.running = False

        self._build_ui()
        self.load_links()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.root.rowconfigure(4, weight=1)

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)

        ttk.Label(top, text="Links das partes").grid(row=0, column=0, sticky="w")
        button_bar = ttk.Frame(top)
        button_bar.grid(row=0, column=1, sticky="e")

        ttk.Button(button_bar, text="Abrir TXT", command=self.choose_links_file).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Button(button_bar, text="Salvar TXT", command=self.save_links).grid(
            row=0, column=1
        )

        self.links_text = scrolledtext.ScrolledText(self.root, height=13, wrap="word")
        self.links_text.grid(row=1, column=0, sticky="nsew", padx=10)

        output_frame = ttk.Frame(self.root, padding=(10, 8))
        output_frame.grid(row=2, column=0, sticky="ew")
        output_frame.columnconfigure(1, weight=1)

        ttk.Label(output_frame, text="Arquivo de saida").grid(row=0, column=0, sticky="w")
        ttk.Entry(output_frame, textvariable=self.output_var).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Button(output_frame, text="Escolher", command=self.choose_output).grid(
            row=0, column=2
        )

        ttk.Label(output_frame, text="Sessao Google Drive").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        self.browser_combo = ttk.Combobox(
            output_frame, textvariable=self.browser_var,
            values=list(BROWSER_SESSIONS), state="readonly", width=18,
        )
        self.browser_combo.grid(row=1, column=1, sticky="w", padx=8, pady=(8, 0))
        self.import_session_button = ttk.Button(
            output_frame, text="Importar sessao", command=self.choose_session_file
        )
        self.import_session_button.grid(row=1, column=2, pady=(8, 0))

        actions = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(1, weight=1)

        self.start_button = ttk.Button(
            actions, text="Iniciar download", command=self.start_download
        )
        self.start_button.grid(row=0, column=0, sticky="w")
        ttk.Label(actions, textvariable=self.status_var).grid(
            row=0, column=1, sticky="w", padx=10
        )

        self.log_text = scrolledtext.ScrolledText(self.root, height=12, wrap="word")
        self.log_text.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def load_links(self) -> None:
        if DEFAULT_LINKS_FILE.exists():
            self.links_text.delete("1.0", tk.END)
            self.links_text.insert(tk.END, DEFAULT_LINKS_FILE.read_text(encoding="utf-8"))
            self.status_var.set(f"Carregado: {DEFAULT_LINKS_FILE.name}")
        else:
            self.status_var.set("links.txt ainda nao existe.")

    def choose_links_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Escolha o arquivo TXT",
            initialdir=str(APP_DIR),
            filetypes=[
                ("Arquivos de texto", "*.txt"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not selected:
            return

        path = Path(selected)
        self.links_text.delete("1.0", tk.END)
        self.links_text.insert(tk.END, path.read_text(encoding="utf-8"))
        self.status_var.set(f"Carregado: {path.name}")

    def save_links(self) -> bool:
        normalized = normalize_links_text(self.links_text.get("1.0", tk.END))
        if not normalized:
            messagebox.showwarning("Sem links", "Cole pelo menos um link antes de salvar.")
            return False
        DEFAULT_LINKS_FILE.write_text(normalized, encoding="utf-8")
        self.links_text.delete("1.0", tk.END)
        self.links_text.insert(tk.END, normalized)
        self.status_var.set(f"Salvo: {DEFAULT_LINKS_FILE.name}")
        return True

    def choose_output(self) -> None:
        selected = filedialog.asksaveasfilename(
            title="Escolha o arquivo final",
            initialdir=str(APP_DIR / "downloads"),
            initialfile="arquivo_final.bin",
            filetypes=[
                ("Arquivos compactados", "*.rar *.zip *.7z"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if selected:
            self.output_var.set(selected)

    def choose_session_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Escolha a sessao exportada pelo Chrome",
            filetypes=[("Sessao Google", "*.txt"), ("Todos os arquivos", "*.*")],
        )
        if selected:
            self.cookies_source = Path(selected)
            self.browser_var.set("Sessao importada")
            self.status_var.set("Sessao importada selecionada.")

    def start_download(self) -> None:
        if self.running:
            messagebox.showinfo("Download em andamento", "Aguarde o download atual terminar.")
            return
        if self.browser_var.get() == "Sessao importada" and self.cookies_source is None:
            self.choose_session_file()
            if self.cookies_source is None:
                return
        if not self.save_links():
            return

        self.log_text.delete("1.0", tk.END)
        self.running = True
        self.start_button.configure(state=tk.DISABLED)
        self.browser_combo.configure(state=tk.DISABLED)
        self.import_session_button.configure(state=tk.DISABLED)
        self.status_var.set("Download em andamento...")

        thread = threading.Thread(
            target=self._run_download,
            args=(
                Path(self.output_var.get()), BROWSER_SESSIONS[self.browser_var.get()],
                self.cookies_source if self.browser_var.get() == "Sessao importada" else None,
            ),
            daemon=True,
        )
        thread.start()

    def _run_download(
        self, output_file: Path, browser: str | None, cookies_source: Path | None
    ) -> None:
        writer = LogWriter(self._append_log)
        try:
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                return_code = run_download(
                    DEFAULT_LINKS_FILE, output_file, APP_DIR / DEFAULT_PARTS_DIR,
                    browser=browser, cookies_source=cookies_source,
                )
            if return_code == 0:
                self._set_status("Finalizado.")
            else:
                self._set_status(f"Finalizado com erro: codigo {return_code}.")
        except Exception as exc:
            self._append_log(f"Erro ao iniciar download: {exc}\n")
            self._set_status("Erro ao iniciar download.")
        finally:
            self.running = False
            self.root.after(0, self._enable_download_controls)

    def _enable_download_controls(self) -> None:
        self.start_button.configure(state=tk.NORMAL)
        self.browser_combo.configure(state="readonly")
        self.import_session_button.configure(state=tk.NORMAL)

    def _append_log(self, text: str) -> None:
        def update() -> None:
            self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)

        self.root.after(0, update)

    def _set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))


def main() -> None:
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
