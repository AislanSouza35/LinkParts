# Baixar partes e juntar

Ferramenta simples para baixar varias partes de um arquivo.

Ela tambem reconhece arquivos RAR multipartes, como `arquivo.part01.rar`,
`arquivo.part02.rar` etc. Nesse caso, os arquivos nao sao juntados em um unico
arquivo: eles ficam separados na mesma pasta, como o WinRAR e o 7-Zip esperam.

## Como usar

### Pelo executavel

Abra:

```text
dist\LinkParts.exe
```

O executavel salva `links.txt` e a pasta `downloads` ao lado dele.

### Pela interface

Rode:

```powershell
python interface.py
```

Na janela, voce pode colar os links, abrir qualquer TXT, salvar no TXT e iniciar o download.
O texto pode ter descricoes junto: a interface extrai automaticamente URLs iniciadas por
`http://` ou `https://`, remove espacos, remove pontuacao final comum e elimina duplicados.

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
