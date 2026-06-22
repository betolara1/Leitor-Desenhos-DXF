# 📐 Leitor de Desenhos (XML)

Aplicativo desktop em **Python + Tkinter** que lê arquivos XML de projetos de
marcenaria, extrai automaticamente os **códigos de desenho** das peças e ajuda o
usuário a **localizar e copiar** os arquivos de desenho correspondentes (DXF, PDF,
DWG, etc.) de uma pasta de origem para uma pasta de destino — com **log de
exportação** de tudo o que foi copiado.

> Pensado para o fluxo de produção de móveis planejados: o software gerador (Promob/ASPAN)
> exporta um XML descrevendo todos os módulos e peças do projeto; este leitor transforma
> esse XML numa lista limpa de desenhos e automatiza a coleta dos arquivos para o
> nesting/corte.

---

## 🎯 Para recrutadores — visão técnica rápida

Projeto pessoal que resolve uma dor real de produção. Pontos de engenharia que vale destacar:

| Tema | Como foi resolvido |
|------|--------------------|
| **Zero dependências externas** | Usa apenas a biblioteca padrão do Python (`tkinter`, `xml.etree`, `re`, `shutil`). Roda em qualquer Windows sem `pip install`. |
| **Parsing robusto** | Estratégia de dois estágios: primeiro tenta o parser estrito de XML (`ElementTree`); se o arquivo estiver malformado, cai para um **fallback por regex** que rastreia o aninhamento das tags `<ESTRUTURA>` para extrair os atributos certos. |
| **Separação de responsabilidades** | Toda a lógica de negócio (parsing, busca de arquivos, filtros, log) vive em **funções puras**, separadas da camada de interface (`LeitorDesenhosApp`). Isso torna o núcleo testável sem abrir a UI. |
| **Regras de negócio configuráveis** | O filtro de quais desenhos exibir é declarativo e isolado em uma única função (`_desenho_permitido`) e uma constante (`REFERENCIAS_LIN_PERMITIDAS`), fácil de auditar e ajustar. |
| **Persistência simples** | As pastas usadas ficam salvas em `config.json` e são recarregadas a cada abertura. Toda exportação é auditada em `log_exportacao.txt`. |
| **Experiência de uso** | Filtro em tempo real, cópia em lote, atalhos (duplo-clique abre a pasta do arquivo) e mensagens de status claras. |

**Stack:** Python 3 · Tkinter (GUI) · `xml.etree.ElementTree` + regex (parsing) ·
arquitetura lógica/UI desacoplada.

---

## 🧠 Como funciona (passo a passo)

1. **Leitura do XML** — o usuário abre um arquivo XML do projeto.
2. **Extração dos desenhos** — o programa varre todas as tags dentro de blocos
   `<ESTRUTURA>` e coleta o valor do atributo `DESENHO="..."` de cada item, junto
   com a `REFERENCIA` daquele mesmo item.
3. **Aplicação das regras de filtro** (função `_desenho_permitido`):
   - Desenhos que começam com **`FUN`** → **nunca aparecem**.
   - Desenhos que começam com **`LIN`** → só aparecem se a `REFERENCIA` do item
     estiver na lista de referências permitidas (`REFERENCIAS_LIN_PERMITIDAS`).
   - Qualquer outro desenho → **sempre aparece**.
4. **Remoção de duplicatas** preservando a ordem de aparição.
5. **Lista na tela** — o usuário pode filtrar por texto, abrir a pasta do desenho,
   copiar um desenho ou copiar todos os filtrados de uma vez.
6. **Localização do arquivo** — para cada desenho, o programa procura
   recursivamente na *pasta de busca* um arquivo com o mesmo nome (com ou sem
   extensão). Arquivos `.dxf` têm prioridade; `.bak` são ignorados.
7. **Exportação + log** — os arquivos encontrados são copiados para a *pasta de
   destino* e o resultado (sucessos e falhas) é registrado em `log_exportacao.txt`.

### Ajustando o filtro de referências

Para liberar os desenhos `LIN` de outras referências, edite a constante no topo
do `app.py`:

```python
REFERENCIAS_LIN_PERMITIDAS = {"LN001173", "LN000023"}  # adicione/remova códigos aqui
```

---

## 🚀 Como usar (guia para qualquer usuário)

### 1. Pré-requisitos
- **Windows** com **Python 3** instalado ([python.org](https://www.python.org/downloads/)).
  Marque a opção *"Add Python to PATH"* durante a instalação.
- Não é preciso instalar mais nada — o Tkinter já vem com o Python no Windows.

### 2. Abrir o programa
- Dê **duplo-clique** no `app.py`, **ou** abra o terminal na pasta do projeto e rode:
  ```bash
  python app.py
  ```

### 3. Configurar as pastas (só na primeira vez)
- **Pasta de busca (origem):** onde estão os arquivos de desenho (ex.: a pasta de
  nesting/DXF). Clique em **Selecionar...** e escolha a pasta.
- **Pasta de destino (colar):** onde você quer que os desenhos copiados sejam
  salvos. Clique em **Selecionar...**.
- *Essas pastas ficam memorizadas para as próximas vezes.*

### 4. Carregar um projeto
- Clique em **Abrir XML...** e escolha o arquivo XML do projeto.
- A lista **"Desenhos encontrados"** será preenchida automaticamente.

### 5. Trabalhar com a lista
- **Filtrar desenho:** digite parte do código para reduzir a lista em tempo real.
- **Duplo-clique** em um desenho → abre a pasta onde o arquivo está.
- **Abrir pasta do desenho** → mesma ação pelo botão.
- **Copiar desenho** → copia o desenho selecionado para a pasta de destino.
- **Copiar todos (filtrados)** → copia de uma vez todos os desenhos que estão na
  lista no momento.

### 6. Conferir o que foi exportado
- Clique em **Abrir log de exportação** para ver o histórico (data/hora, projeto
  de origem, destino, quantos foram copiados e quais falharam).

---

## 📁 Estrutura do projeto

```
Leitor Desenhos/
├── app.py               # Aplicação completa (lógica + interface)
├── config.json          # Pastas memorizadas (gerado automaticamente)
├── log_exportacao.txt   # Histórico de exportações (gerado automaticamente)
└── README.md            # Este arquivo
```

---

## ❓ Perguntas frequentes

**O programa não acha o arquivo de um desenho.**
Confira se a *pasta de busca* aponta para o local correto e se o arquivo existe
com o mesmo nome do código de desenho (a extensão pode ser diferente).

**Abri um XML e a lista veio vazia ou menor que o esperado.**
Lembre-se das regras de filtro: desenhos `FUN` são sempre ocultados e desenhos
`LIN` só aparecem para as referências permitidas. Ajuste
`REFERENCIAS_LIN_PERMITIDAS` se necessário.

**Funciona no macOS/Linux?**
A lógica é multiplataforma e o app abre, mas o fluxo foi desenhado e testado para
**Windows**.
