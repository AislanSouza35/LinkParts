chrome.action.onClicked.addListener(async () => {
  try {
    const cookies = (await chrome.cookies.getAll({ domain: "google.com" })).filter(
      (cookie) => cookie.domain === "google.com" || cookie.domain.endsWith(".google.com")
    );
    if (!cookies.length) throw new Error("Entre na conta Google antes de exportar.");
    const lines = ["# Netscape HTTP Cookie File", "# LinkParts - sessao Google local"];
    for (const cookie of cookies) {
      const fields = [
        (cookie.httpOnly ? "#HttpOnly_" : "") + cookie.domain,
        cookie.domain.startsWith(".") ? "TRUE" : "FALSE",
        cookie.path,
        cookie.secure ? "TRUE" : "FALSE",
        cookie.expirationDate === undefined ? "" : String(Math.floor(cookie.expirationDate)),
        cookie.name,
        cookie.value,
      ];
      if (fields.some((field) => /[\t\r\n]/.test(field))) {
        throw new Error("Formato de sessao nao suportado.");
      }
      lines.push(fields.join("\t"));
    }
    await chrome.downloads.download({
      url: "data:text/plain;charset=utf-8," + encodeURIComponent(lines.join("\n") + "\n"),
      filename: "linkparts-google-session.txt",
      saveAs: true,
    });
    await chrome.action.setBadgeText({ text: "OK" });
    await chrome.action.setTitle({ title: "Sessao exportada. Importe o arquivo no LinkParts." });
  } catch {
    await chrome.action.setBadgeText({ text: "ERRO" });
    await chrome.action.setTitle({ title: "Falha ao exportar. Entre na conta Google e tente novamente." });
  }
});
