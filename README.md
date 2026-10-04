# Baixar partes e juntar

Ferramenta simples para baixar varias partes de um arquivo.

Ela tambem reconhece arquivos RAR multipartes, como `arquivo.part01.rar`,
`arquivo.part02.rar` etc. Nesse caso, os arquivos nao sao juntados em um unico
arquivo: eles ficam separados na mesma pasta, como o WinRAR e o 7-Zip esperam.

## Como usar

### Pelo executavel

Abra:

```text
dist\atualizado\LinkParts.exe
```

O executavel salva `links.txt` e a pasta `downloads` ao lado dele.

Para gerar novamente o executavel:

```powershell
python -m pip install pyinstaller
python -m PyInstaller LinkParts.spec --distpath dist/atualizado --clean --noconfirm
```

### Pela interface

Instale as dependencias antes de executar pelo Python (o executavel ja as inclui):

```powershell
python -m pip install -r requirements.txt
```

Rode:

```powershell
python interface.py
```

Na janela, voce pode colar os links, abrir qualquer TXT, salvar no TXT e iniciar o download.
O texto pode ter descricoes junto: a interface extrai automaticamente URLs iniciadas por
`http://` ou `https://`, remove espacos, remove pontuacao final comum e elimina duplicados.

Para usar sua conta Google, entre na conta pelo navegador e escolha Chrome, Edge ou
Firefox em **Sessao Google Drive** antes de iniciar. A sessao e usada tanto para
identificar os nomes quanto para baixar os arquivos. Os cookies do Google ficam em
uma pasta temporaria, removida ao concluir ou falhar; nao sao salvos no projeto.

Se o navegador bloquear a leitura, feche-o e tente novamente. Chrome/Edge recentes
no Windows podem proteger os cookies mesmo com o navegador fechado. Nesse caso,
entre na conta Google pelo Firefox e selecione Firefox. O login nao garante a
liberacao de um arquivo cuja cota de downloads foi excedida.

### Sessao do Chrome quando a leitura direta estiver bloqueada

1. No Chrome conectado a sua conta Google, abra `chrome://extensions`.
2. Ative **Modo do desenvolvedor**, clique em **Carregar sem compactacao** e selecione
   a pasta `chrome-extension` deste projeto.
3. Clique na extensao **LinkParts - Sessao Google** para salvar
   `linkparts-google-session.txt` no computador.
4. No LinkParts, clique em **Importar sessao**, selecione esse arquivo e inicie o download.

A extensao usa apenas cookies do Google e salva um arquivo local, sem enviar a sessao
a servidores. Esse arquivo permite usar sua sessao: mantenha-o privado e apague-o
apos o uso. O LinkParts apaga sua copia temporaria, mas preserva o arquivo importado.

Pelo terminal:

```powershell
python baixar_e_juntar.py --navegador firefox
```

### Pelo terminal

1. Abra `links.txt`.
2. Cole os links das partes, um por linha, na ordem correta. Use `links.example.txt` como modelo.
   Pela interface, tambem pode colar texto com descricoes; ela salva apenas os links encontrados.
3. Rode:

```powershell
python baixar_e_juntar.py
```

Por padrao, as partes ficam em `downloads/partes/` e o arquivo final fica em `downloads/arquivo_final.bin`.

Para escolher o nome do arquivo final:

```powershell
python baixar_e_juntar.py --saida video.mp4
```

Para usar outro arquivo de links:

```powershell
python baixar_e_juntar.py --links meus_links.txt --saida arquivo_final.zip
```

## Observacoes

- Links publicos de arquivos do Google Drive sao aceitos, incluindo `/file/d/ID/view`.
  O programa trata a confirmacao de download e reconhece o nome original das partes RAR.
  Arquivos privados ou com download bloqueado pelo Drive exibem erro no registro.
- O script baixa uma parte por vez.
- Se uma parte ja existir e nao estiver vazia, ela nao sera baixada de novo.
- Se algum download falhar, o arquivo final nao sera criado.
- Linhas vazias e linhas comecando com `#` em `links.txt` sao ignoradas.

## Arquivos `.part01.rar`, `.part02.rar`, etc.

Para RAR multipartes:

```powershell
python baixar_e_juntar.py
```

Depois que terminar, abra `downloads/partes/ktn25.part01.rar` no WinRAR ou
7-Zip e extraia por ele. Nao tente juntar manualmente as partes.
