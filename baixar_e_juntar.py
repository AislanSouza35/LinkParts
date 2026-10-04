import argparse
from contextlib import contextmanager
from http.cookiejar import MozillaCookieJar
import html
from pathlib import Path
import re
import shutil
import ssl
import sys
import tempfile
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen, urlretrieve

import gdown


DEFAULT_LINKS_FILE = Path("links.txt")
DEFAULT_PARTS_DIR = Path("downloads") / "partes"
DEFAULT_OUTPUT_PATH = Path("downloads") / "arquivo_final.bin"
USER_AGENT = "Mozilla/5.0"


def read_links(path: Path) -> list[str]:
    links = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            links.append(line)
    return links


def part_path(parts_dir: Path, index: int) -> Path:
    return parts_dir / f"parte-{index:04d}.part"


@contextmanager
def google_drive_session(browser: str | None, cookies_source: Path | None = None):
    if browser is None and cookies_source is None:
        yield None
        return
    if browser is not None and browser not in {"chrome", "edge", "firefox"}:
        raise ValueError("Navegador invalido. Escolha Chrome, Edge ou Firefox.")

    from gdown.download import _import_cookies_from_browser

    with tempfile.TemporaryDirectory(prefix="linkparts-session-") as session_dir:
        cookies_file = str(Path(session_dir) / "cookies.txt")
        if cookies_source is not None:
            source = MozillaCookieJar(str(cookies_source))
            try:
                source.load(ignore_discard=True)
            except (OSError, ValueError) as exc:
                raise RuntimeError("Arquivo de sessao invalido. Exporte novamente pelo Chrome.") from exc
            filtered = MozillaCookieJar(cookies_file)
            for cookie in source:
                if cookie.domain == "google.com" or cookie.domain.endswith(".google.com"):
                    filtered.set_cookie(cookie)
            filtered.save(ignore_discard=True)
            count = len(filtered)
        else:
            print(f"Carregando sessao Google do {browser}...")
            try:
                count = _import_cookies_from_browser(browser=browser, cookies_file=cookies_file)
            except Exception as exc:
                raise RuntimeError(
                    f"Nao foi possivel ler a sessao do {browser}. Feche o navegador e tente "
                    "novamente, use Importar sessao com a extensao LinkParts ou entre "
                    "na conta Google pelo Firefox e selecione Firefox."
                ) from exc
        if count == 0:
            raise RuntimeError(
                "Nenhuma sessao Google valida encontrada. Entre na sua conta Google "
                "no navegador e carregue a sessao novamente."
            )
        print("Sessao Google carregada para este download.")
        yield cookies_file


def filename_from_link(url: str, cookies_file: str | None = None) -> str:
    if is_google_drive_link(url):
        metadata = gdown.download(
            url=url, skip_download=True, quiet=True, use_cookies=bool(cookies_file),
            cookies_file=cookies_file, timeout=30,
        )
        name = metadata.path
        if not name or name in {".", ".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
            raise ValueError("Nome de arquivo do Google Drive invalido para Windows.")
        return name
    parts = [unquote(part) for part in urlparse(url).path.split("/") if part]
    if len(parts) >= 3 and parts[0] == "file" and parts[-1] == "file":
        return parts[-2]
    if parts:
        return parts[-1]
    return "arquivo.part"


def is_google_drive_link(url: str) -> bool:
    return urlparse(url).hostname in {"drive.google.com", "www.drive.google.com"}


def is_multipart_rar(filenames: list[str]) -> bool:
    return all(re.search(r"\.part\d+\.rar$", name, re.IGNORECASE) for name in filenames)


def join_parts(part_files: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output:
        for part_file in part_files:
            with part_file.open("rb") as part:
                shutil.copyfileobj(part, output)


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        context = ssl._create_unverified_context()
        with urlopen(request, timeout=30, context=context) as response:
            return response.read().decode("utf-8", errors="replace")


def resolve_mediafire_direct_link(url: str, html_text: str | None = None) -> str:
    page = html_text if html_text is not None else fetch_text(url)
    for match in re.finditer(r'href=["\']([^"\']+)["\']', page):
        href = html.unescape(match.group(1))
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"} and "download" in parsed.netloc:
            if "mediafire.com" in parsed.netloc:
                return href
    raise ValueError("Nao encontrei o link direto de download do MediaFire.")


def download_url(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        context = ssl._create_unverified_context()
        with urlopen(
            request, timeout=60, context=context
        ) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def download_part(url: str, destination: Path, cookies_file: str | None = None) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        print(f"Pulando {destination.name}: ja existe.")
        return True

    temporary = destination.with_name(destination.name + ".download")
    try:
        print(f"Baixando {destination.name}...")
        if is_google_drive_link(url):
            gdown.download(
                url=url, output=str(temporary), quiet=True,
                use_cookies=bool(cookies_file), cookies_file=cookies_file, timeout=60,
            )
            if not temporary.exists() or temporary.stat().st_size == 0:
                raise RuntimeError("O Google Drive nao retornou o arquivo.")
            temporary.replace(destination)
        elif "mediafire.com/file/" in url:
            download_url(resolve_mediafire_direct_link(url), destination)
        else:
            urlretrieve(url, destination)
        return destination.exists() and destination.stat().st_size > 0
    except Exception as exc:
        print(f"Erro ao baixar {destination.name}: {exc}")
        if is_google_drive_link(url) and temporary.exists():
            temporary.unlink()
        if destination.exists() and destination.stat().st_size == 0:
            destination.unlink()
        return False


def download_all_parts(
    links: list[str], parts_dir: Path, keep_names: bool = False,
    cookies_file: str | None = None,
) -> list[Path]:
    part_files = []
    total = len(links)
    for index, url in enumerate(links, start=1):
        destination = (
            parts_dir / filename_from_link(url, cookies_file=cookies_file)
            if keep_names else part_path(parts_dir, index)
        )
        print(f"[{index}/{total}] {url}")
        if not download_part(url, destination, cookies_file=cookies_file):
            raise RuntimeError(f"Falha na parte {index}: {url}")
        part_files.append(destination)
    return part_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Baixa partes de um arquivo e junta tudo em um arquivo final."
    )
    parser.add_argument(
        "--links",
        default=str(DEFAULT_LINKS_FILE),
        help="Arquivo com um link por linha. Padrao: links.txt",
    )
    parser.add_argument(
        "--cookies", type=Path,
        help="Arquivo de sessao Netscape exportado pela extensao LinkParts.",
    )
    parser.add_argument(
        "--navegador", choices=["chrome", "edge", "firefox"],
        help="Usar a sessao Google conectada neste navegador para links do Drive.",
    )
    parser.add_argument(
        "--saida",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Arquivo final. Padrao: downloads/arquivo_final.bin",
    )
    return parser


def run_download(
    links_file: Path,
    output_path: Path,
    parts_dir: Path = DEFAULT_PARTS_DIR,
    browser: str | None = None,
    cookies_source: Path | None = None,
) -> int:
    if not links_file.exists():
        print(f"Arquivo {links_file} nao encontrado.")
        print("Crie um links.txt com um link por linha e rode novamente.")
        return 1

    links = read_links(links_file)
    if not links:
        print(f"Nenhum link valido encontrado em {links_file}.")
        return 1

    try:
        has_drive = any(is_google_drive_link(link) for link in links)
        with google_drive_session(
            browser if has_drive else None, cookies_source if has_drive else None
        ) as cookies_file:
            filenames = [filename_from_link(link, cookies_file=cookies_file) for link in links]
            multipart_rar = is_multipart_rar(filenames)
            part_files = download_all_parts(
                links, parts_dir, keep_names=multipart_rar, cookies_file=cookies_file
            )
    except Exception as exc:
        print(exc)
        print("Arquivo final nao foi criado porque houve falha no download.")
        return 1

    if multipart_rar:
        print("RAR multipartes detectado.")
        print(f"Partes salvas em: {parts_dir}")
        print("Nao junte esses arquivos. Extraia abrindo a parte 01 no WinRAR ou 7-Zip.")
        return 0

    print(f"Juntando {len(part_files)} partes em {output_path}...")
    join_parts(part_files, output_path)
    print(f"Pronto: {output_path}")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return run_download(
        Path(args.links), Path(args.saida), browser=args.navegador, cookies_source=args.cookies
    )


if __name__ == "__main__":
    sys.exit(main())
