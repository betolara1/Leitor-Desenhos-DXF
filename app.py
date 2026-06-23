# -*- coding: utf-8 -*-
"""
Leitor de Desenhos (XML)
------------------------
Lê arquivos XML, extrai todos os valores do atributo `desenho="..."`,
lista os desenhos, permite filtrar/buscar, abrir a pasta de origem com
o arquivo selecionado e copiar o arquivo do desenho para a pasta de destino.

Requisitos: apenas Python padrão (Tkinter incluso no Windows).
Execute com:  python leitor_desenhos.py
"""

import os
import re
import sys
import json
import shutil
import subprocess
from datetime import datetime
import xml.etree.ElementTree as ET

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# --------------------------------------------------------------------------- #
# Lógica (sem interface) — facilita testes                                    #
# --------------------------------------------------------------------------- #

def obter_pasta_base():
    """Retorna a pasta onde devem ser gravados config.json e o log.

    Quando empacotado com PyInstaller (--onefile), usa a pasta do executável,
    pois o __file__ aponta para uma pasta temporária que é apagada ao fechar.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()


def obter_caminho_config():
    """Retorna o caminho do arquivo de configuração config.json."""
    return os.path.join(obter_pasta_base(), "config.json")


def carregar_config():
    """Lê as pastas salvas do config.json se existirem."""
    caminho = obter_caminho_config()
    if os.path.isfile(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def salvar_config(config):
    """Salva as pastas no config.json."""
    caminho = obter_caminho_config()
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def obter_caminho_log():
    """Retorna o caminho do arquivo de log log_exportacao.txt."""
    return os.path.join(obter_pasta_base(), "log_exportacao.txt")


def registrar_log(xml_origem, destino, sucessos, falhas):
    """Grava as informações de exportação no arquivo de log."""
    caminho_log = obter_caminho_log()
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    linhas = [
        "=======================================================================",
        f"DATA/HORA: {timestamp}",
        f"XML DE ORIGEM: {xml_origem}",
        f"PASTA DE DESTINO: {destino}",
        f"QUANTIDADE EXPORTADA (SUCESSO): {len(sucessos)}",
        f"QUANTIDADE COM FALHA: {len(falhas)}",
        ""
    ]
    
    if sucessos:
        linhas.append("DESENHOS EXPORTADOS COM SUCESSO:")
        for s in sucessos:
            linhas.append(f"  - {s}")
        linhas.append("")
        
    if falhas:
        linhas.append("DESENHOS COM FALHA:")
        for f in falhas:
            linhas.append(f"  - {f}")
        linhas.append("")
        
    linhas.append("=======================================================================\n")
    
    texto_log = "\n".join(linhas)
    try:
        with open(caminho_log, "a", encoding="utf-8") as f:
            f.write(texto_log)
    except Exception:
        pass


def abrir_arquivo(caminho):
    """Abre o arquivo com o programa padrão do sistema."""
    caminho = os.path.abspath(caminho)
    if sys.platform.startswith("win"):
        os.startfile(caminho)
    elif sys.platform == "darwin":
        subprocess.run(["open", caminho])
    else:
        subprocess.run(["xdg-open", caminho])


# Referências para as quais os desenhos "LIN" devem aparecer.
# Um desenho cujo nome começa com "LIN" só é listado quando a REFERENCIA do
# mesmo item estiver nesta lista. Os demais desenhos aparecem normalmente.
# Para liberar outras referências, basta acrescentá-las aqui.
REFERENCIAS_LIN_PERMITIDAS = {"LN001173", "LN000023"}


def _desenho_permitido(desenho, referencia):
    """Decide se um desenho deve aparecer na lista.

    Desenhos cujo nome começa com "FUN" ou "HOR" nunca são permitidos.
    Desenhos cujo nome começa com "LIN" só são permitidos quando a REFERENCIA
    do item for uma das referências em REFERENCIAS_LIN_PERMITIDAS. Qualquer
    outro desenho é sempre permitido.
    """
    desenho_upper = desenho.strip().upper()
    if desenho_upper.startswith("FUN") or desenho_upper.startswith("HOR"):
        return False
    if desenho_upper.startswith("LIN"):
        return (referencia or "").strip().upper() in REFERENCIAS_LIN_PERMITIDAS
    return True


def _atributos_de(trecho):
    """Extrai um dicionário de atributos (com chaves em minúsculas) a partir
    do corpo de uma tag XML (aceita aspas duplas ou simples)."""
    attrs = {}
    for nome, _aspas, valor in re.findall(r'([\w:.\-]+)\s*=\s*(["\'])(.*?)\2', trecho):
        attrs[nome.lower()] = valor
    return attrs


def extrair_desenhos_do_texto(texto):
    """Extrai todos os valores de desenho="..." que estejam dentro de <ESTRUTURA> de um texto XML,
    e também desenhos fora de <ESTRUTURA> (pai) se começarem com ESP ou com ES0 (quando a REFERENCIA começa com ES0).

    Funciona mesmo se o XML estiver levemente malformado, pois usa regex
    como fallback. Retorna lista preservando a ordem e sem duplicatas.

    Desenhos "LIN..." são filtrados pela REFERENCIA do próprio item
    (ver _desenho_permitido / REFERENCIAS_LIN_PERMITIDAS).
    """
    valores = []

    # 1) Tenta o parser de XML de verdade
    try:
        root = ET.fromstring(texto)
        elementos_na_estrutura = set()
        for elem in root.iter():
            if elem.tag.upper() == "ESTRUTURA":
                for child in elem.iter():
                    elementos_na_estrutura.add(child)

        for elem in root.iter():
            attrs = {k.lower(): v for k, v in elem.attrib.items()}
            desenho = attrs.get("desenho")
            if not desenho:
                continue

            if elem in elementos_na_estrutura:
                if _desenho_permitido(desenho, attrs.get("referencia")):
                    valores.append(desenho.strip())
            else:
                # Desenhos pai (fora da ESTRUTURA)
                desenho_upper = desenho.strip().upper()
                ref_upper = attrs.get("referencia", "").strip().upper()
                if desenho_upper.startswith("ESP"):
                    valores.append(desenho.strip())
                elif desenho_upper.startswith("ES0") and ref_upper.startswith("ES0"):
                    valores.append(desenho.strip())
    except ET.ParseError:
        pass

    # 2) Fallback / complemento via regex.
    # Rastreia o aninhamento de <ESTRUTURA> e, para cada tag dentro dela,
    # lê os atributos desenho e referencia do mesmo item.
    pattern = re.compile(r'<(/?)([A-Za-z_][\w:.\-]*)([^>]*?)(/?)>', re.DOTALL)
    depth = 0
    for m in pattern.finditer(texto):
        fechamento, tag, corpo, autofecha = m.group(1), m.group(2), m.group(3), m.group(4)
        if tag.upper() == "ESTRUTURA":
            if fechamento:
                depth = max(0, depth - 1)
            elif not autofecha:
                depth += 1
            continue
        
        if fechamento:
            continue
            
        attrs = _atributos_de(corpo)
        desenho = attrs.get("desenho")
        if not desenho:
            continue

        if depth > 0:
            if _desenho_permitido(desenho, attrs.get("referencia")):
                valores.append(desenho.strip())
        else:
            # Desenhos pai (fora da ESTRUTURA)
            desenho_upper = desenho.strip().upper()
            ref_upper = attrs.get("referencia", "").strip().upper()
            if desenho_upper.startswith("ESP"):
                valores.append(desenho.strip())
            elif desenho_upper.startswith("ES0") and ref_upper.startswith("ES0"):
                valores.append(desenho.strip())

    # Remove duplicatas preservando ordem
    vistos = set()
    unicos = []
    for v in valores:
        if v and v not in vistos:
            vistos.add(v)
            unicos.append(v)
    return unicos


def extrair_desenhos_do_arquivo(caminho_xml):
    """Lê um arquivo XML e retorna a lista de desenhos encontrados."""
    with open(caminho_xml, "r", encoding="utf-8", errors="ignore") as f:
        texto = f.read()
    return extrair_desenhos_do_texto(texto)


def localizar_arquivo_desenho(nome_desenho, pasta_busca):
    """Procura, dentro da pasta de busca (recursivamente), um arquivo cujo
    nome corresponda ao desenho.

    Aceita o nome com ou sem extensão. Ex.: desenho "ABC123" casa com
    ABC123.pdf, ABC123.dwg, ABC123.tif, etc. Se o nome já tiver extensão,
    procura o nome exato primeiro.
    """
    if not pasta_busca or not os.path.isdir(pasta_busca):
        return None

    nome_alvo = nome_desenho.strip()
    base_alvo, ext_alvo = os.path.splitext(nome_alvo)
    base_alvo_l = base_alvo.lower()
    nome_alvo_l = nome_alvo.lower()

    candidato_base = None
    for raiz, _dirs, arquivos in os.walk(pasta_busca):
        for arq in arquivos:
            arq_l = arq.lower()
            if arq_l.endswith(".bak"):
                continue
            base_arq_l = os.path.splitext(arq)[0].lower()
            # Correspondência exata (com extensão)
            if ext_alvo and arq_l == nome_alvo_l:
                return os.path.join(raiz, arq)
            # Correspondência pelo nome base (sem extensão)
            if base_arq_l == base_alvo_l:
                caminho_completo = os.path.join(raiz, arq)
                if arq_l.endswith(".dxf"):
                    return caminho_completo
                if candidato_base is None:
                    candidato_base = caminho_completo
    return candidato_base


def mapear_pasta_arquivos(pasta):
    """Varre a pasta recursivamente e mapeia os arquivos por nome base (minúsculo)
    e por nome completo (minúsculo) para busca rápida.
    Retorna dois dicionários: {nome_base_l: caminho} e {nome_completo_l: caminho}.
    """
    mapa_base = {}
    mapa_completo = {}
    
    if not pasta or not os.path.isdir(pasta):
        return mapa_base, mapa_completo
        
    for raiz, _dirs, arquivos in os.walk(pasta):
        for arq in arquivos:
            arq_l = arq.lower()
            if arq_l.endswith(".bak"):
                continue
            
            caminho_completo = os.path.join(raiz, arq)
            # Mapa do nome completo
            if arq_l not in mapa_completo:
                mapa_completo[arq_l] = caminho_completo
                
            # Mapa do nome base (sem extensão)
            base_arq_l = os.path.splitext(arq)[0].lower()
            
            # Prioriza DXF se houver duplicatas de nome base
            if base_arq_l not in mapa_base:
                mapa_base[base_arq_l] = caminho_completo
            else:
                # Se já existe mas o novo é dxf, sobrescreve para dar prioridade ao dxf
                if arq_l.endswith(".dxf"):
                    mapa_base[base_arq_l] = caminho_completo
                    
    return mapa_base, mapa_completo


def buscar_em_mapa(nome_desenho, mapa_base, mapa_completo):
    """Procura um desenho no mapa de busca em O(1) reproduzindo a mesma prioridade
    de localizar_arquivo_desenho (exato > base_dxf > base_outros)."""
    nome_alvo = nome_desenho.strip()
    base_alvo, ext_alvo = os.path.splitext(nome_alvo)
    base_alvo_l = base_alvo.lower()
    nome_alvo_l = nome_alvo.lower()
    
    # 1. Correspondência exata se tiver extensão
    if ext_alvo and nome_alvo_l in mapa_completo:
        return mapa_completo[nome_alvo_l]
        
    # 2. Correspondência por nome base
    if base_alvo_l in mapa_base:
        return mapa_base[base_alvo_l]
        
    return None


def abrir_pasta_com_arquivo(caminho):
    """Abre o gerenciador de arquivos na pasta do caminho informado.
    No Windows, seleciona o arquivo. Em macOS/Linux abre a pasta.
    """
    caminho = os.path.abspath(caminho)
    if sys.platform.startswith("win"):
        if os.path.isfile(caminho):
            subprocess.run(["explorer", "/select,", caminho])
        else:
            subprocess.run(["explorer", caminho])
    elif sys.platform == "darwin":
        if os.path.isfile(caminho):
            subprocess.run(["open", "-R", caminho])
        else:
            subprocess.run(["open", caminho])
    else:
        pasta = caminho if os.path.isdir(caminho) else os.path.dirname(caminho)
        subprocess.run(["xdg-open", pasta])


# --------------------------------------------------------------------------- #
# Interface gráfica                                                           #
# --------------------------------------------------------------------------- #

class LeitorDesenhosApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Leitor de Desenhos (XML)")
        self.root.geometry("760x560")
        self.root.minsize(640, 480)

        config = carregar_config()
        self.pasta_busca = tk.StringVar(value=config.get("pasta_busca", ""))
        self.pasta_destino = tk.StringVar(value=config.get("pasta_destino", ""))
        self.arquivo_xml = tk.StringVar()
        self.filtro = tk.StringVar()
        self.status = tk.StringVar(value="Pronto.")

        self.todos_desenhos = []   # lista completa
        self.desenhos_exibidos = []  # após filtro

        self._montar_ui()

        # Atualiza a lista conforme o usuário digita no filtro
        self.filtro.trace_add("write", lambda *_: self._aplicar_filtro())

        # Salva as pastas nas configurações quando forem alteradas
        self.pasta_busca.trace_add("write", lambda *_: self._salvar_config())
        self.pasta_destino.trace_add("write", lambda *_: self._salvar_config())

    # ---- construção da interface ---------------------------------------- #
    def _montar_ui(self):
        pad = {"padx": 6, "pady": 4}

        frm_top = ttk.LabelFrame(self.root, text="Pastas")
        frm_top.pack(fill="x", padx=10, pady=(10, 4))

        # Pasta de busca (origem)
        ttk.Label(frm_top, text="Pasta de busca (origem):").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frm_top, textvariable=self.pasta_busca).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(frm_top, text="Selecionar...", command=self._sel_pasta_busca).grid(row=0, column=2, **pad)

        # Pasta de destino
        ttk.Label(frm_top, text="Pasta de destino (colar):").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm_top, textvariable=self.pasta_destino).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(frm_top, text="Selecionar...", command=self._sel_pasta_destino).grid(row=1, column=2, **pad)

        # Arquivo XML
        ttk.Label(frm_top, text="Arquivo XML:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm_top, textvariable=self.arquivo_xml).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Button(frm_top, text="Abrir XML...", command=self._abrir_xml).grid(row=2, column=2, **pad)

        frm_top.columnconfigure(1, weight=1)

        # Filtro
        frm_filtro = ttk.Frame(self.root)
        frm_filtro.pack(fill="x", padx=10, pady=4)
        ttk.Label(frm_filtro, text="Filtrar desenho:").pack(side="left")
        ent = ttk.Entry(frm_filtro, textvariable=self.filtro)
        ent.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(frm_filtro, text="Limpar", command=lambda: self.filtro.set("")).pack(side="left")

        # Lista
        frm_lista = ttk.LabelFrame(self.root, text="Desenhos encontrados")
        frm_lista.pack(fill="both", expand=True, padx=10, pady=4)

        self.listbox = tk.Listbox(frm_lista, activestyle="dotbox")
        self.listbox.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scroll = ttk.Scrollbar(frm_lista, orient="vertical", command=self.listbox.yview)
        scroll.pack(side="left", fill="y", pady=6)
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.bind("<Double-Button-1>", lambda e: self._abrir_pasta_do_desenho())

        # Botões de ação
        frm_btn = ttk.Frame(self.root)
        frm_btn.pack(fill="x", padx=10, pady=4)
        ttk.Button(frm_btn, text="Abrir pasta do desenho", command=self._abrir_pasta_do_desenho).pack(side="left")
        ttk.Button(frm_btn, text="Copiar desenho", command=self._copiar_desenho).pack(side="left", padx=6)
        ttk.Button(frm_btn, text="Copiar todos (filtrados)", command=self._copiar_todos).pack(side="left")
        ttk.Button(frm_btn, text="Comparar pasta...", command=self._comparar_pasta).pack(side="left", padx=6)
        ttk.Button(frm_btn, text="Abrir log de exportação", command=self._abrir_log).pack(side="right")

        # Barra de status
        ttk.Label(self.root, textvariable=self.status, relief="sunken", anchor="w").pack(
            fill="x", side="bottom", padx=0, pady=0
        )

    # ---- ações de pasta / arquivo --------------------------------------- #
    def _sel_pasta_busca(self):
        d = filedialog.askdirectory(title="Selecione a pasta de busca (origem)")
        if d:
            self.pasta_busca.set(d)

    def _sel_pasta_destino(self):
        d = filedialog.askdirectory(title="Selecione a pasta de destino (colar)")
        if d:
            self.pasta_destino.set(d)

    def _abrir_xml(self):
        inicial = self.pasta_busca.get() or os.path.expanduser("~")
        caminho = filedialog.askopenfilename(
            title="Selecione o arquivo XML",
            initialdir=inicial,
            filetypes=[("Arquivos XML", "*.xml"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return
        self.arquivo_xml.set(caminho)
        # Se a pasta de busca estiver vazia, usa a pasta do XML
        if not self.pasta_busca.get():
            self.pasta_busca.set(os.path.dirname(caminho))
        self._carregar_desenhos()

    def _carregar_desenhos(self):
        caminho = self.arquivo_xml.get()
        if not caminho or not os.path.isfile(caminho):
            messagebox.showwarning("Atenção", "Selecione um arquivo XML válido.")
            return
        try:
            self.todos_desenhos = extrair_desenhos_do_arquivo(caminho)
        except Exception as e:
            messagebox.showerror("Erro ao ler XML", str(e))
            return
        self._aplicar_filtro()
        self.status.set(f"{len(self.todos_desenhos)} desenho(s) encontrado(s) no XML.")

    # ---- filtro ---------------------------------------------------------- #
    def _aplicar_filtro(self):
        termo = self.filtro.get().strip().lower()
        if termo:
            self.desenhos_exibidos = [d for d in self.todos_desenhos if termo in d.lower()]
        else:
            self.desenhos_exibidos = list(self.todos_desenhos)

        self.listbox.delete(0, tk.END)
        for d in self.desenhos_exibidos:
            self.listbox.insert(tk.END, d)

        if self.todos_desenhos:
            self.status.set(
                f"Exibindo {len(self.desenhos_exibidos)} de {len(self.todos_desenhos)} desenho(s)."
            )

    def _desenho_selecionado(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Selecione", "Selecione um desenho na lista.")
            return None
        return self.desenhos_exibidos[sel[0]]

    # ---- abrir pasta ----------------------------------------------------- #
    def _abrir_pasta_do_desenho(self):
        desenho = self._desenho_selecionado()
        if not desenho:
            return
        caminho = localizar_arquivo_desenho(desenho, self.pasta_busca.get())
        if caminho:
            abrir_pasta_com_arquivo(caminho)
            self.status.set(f"Abrindo pasta: {caminho}")
        else:
            # Não achou o arquivo: abre ao menos a pasta de busca
            if os.path.isdir(self.pasta_busca.get()):
                abrir_pasta_com_arquivo(self.pasta_busca.get())
                self.status.set(
                    f"Arquivo do desenho '{desenho}' não encontrado. Abrindo a pasta de busca."
                )
            else:
                messagebox.showwarning(
                    "Não encontrado",
                    f"Não foi possível localizar o arquivo do desenho '{desenho}'.",
                )

    # ---- copiar ---------------------------------------------------------- #
    def _validar_destino(self):
        destino = self.pasta_destino.get()
        if not destino or not os.path.isdir(destino):
            messagebox.showwarning("Atenção", "Selecione uma pasta de destino válida.")
            return None
        return destino

    def _copiar_um(self, desenho, destino):
        caminho = localizar_arquivo_desenho(desenho, self.pasta_busca.get())
        if not caminho:
            return False, f"'{desenho}': arquivo não encontrado na pasta de busca."
        try:
            shutil.copy2(caminho, os.path.join(destino, os.path.basename(caminho)))
            return True, os.path.basename(caminho)
        except Exception as e:
            return False, f"'{desenho}': erro ao copiar ({e})."

    def _copiar_desenho(self):
        desenho = self._desenho_selecionado()
        if not desenho:
            return
        destino = self._validar_destino()
        if not destino:
            return
        ok, info = self._copiar_um(desenho, destino)
        if ok:
            self.status.set(f"Copiado: {info} → {destino}")
            registrar_log(self.arquivo_xml.get(), destino, [info], [])
            messagebox.showinfo("Sucesso", f"Desenho copiado:\n{info}\n\npara\n{destino}")
        else:
            self.status.set(info)
            registrar_log(self.arquivo_xml.get(), destino, [], [info])
            messagebox.showwarning("Não copiado", info)

    def _copiar_todos(self):
        if not self.desenhos_exibidos:
            messagebox.showinfo("Nada a copiar", "A lista está vazia.")
            return
        destino = self._validar_destino()
        if not destino:
            return
        sucessos, falhas = [], []
        for d in self.desenhos_exibidos:
            ok, info = self._copiar_um(d, destino)
            if ok:
                sucessos.append(info)
            else:
                falhas.append(info)
        
        registrar_log(self.arquivo_xml.get(), destino, sucessos, falhas)
        
        copiados = len(sucessos)
        msg = f"{copiados} arquivo(s) copiado(s) para:\n{destino}"
        if falhas:
            msg += "\n\nNão encontrados/erros:\n" + "\n".join(falhas[:20])
            if len(falhas) > 20:
                msg += f"\n... e mais {len(falhas) - 20}."
        self.status.set(f"{copiados} copiado(s), {len(falhas)} falha(s).")
        messagebox.showinfo("Resultado", msg)

    def _abrir_log(self):
        caminho_log = obter_caminho_log()
        if os.path.isfile(caminho_log):
            abrir_arquivo(caminho_log)
        else:
            messagebox.showinfo("Aviso", "Nenhum log de exportação foi gerado ainda.")

    def _comparar_pasta(self):
        if not self.todos_desenhos:
            messagebox.showwarning("Atenção", "Nenhum desenho carregado. Abra um XML primeiro.")
            return

        pasta = filedialog.askdirectory(title="Selecione a pasta para comparação")
        if not pasta:
            return

        self.status.set("Indexando arquivos...")
        self.root.update_idletasks()

        try:
            mapa_base, mapa_completo = mapear_pasta_arquivos(pasta)
        except Exception as e:
            messagebox.showerror("Erro ao ler pasta", f"Erro: {e}")
            self.status.set("Erro ao indexar pasta.")
            return

        self.status.set("Analisando existência...")
        self.root.update_idletasks()

        encontrados = []
        ausentes = []
        for d in self.todos_desenhos:
            caminho = buscar_em_mapa(d, mapa_base, mapa_completo)
            if caminho:
                encontrados.append((d, caminho))
            else:
                ausentes.append(d)

        self.status.set(f"Comparação concluída: {len(encontrados)} encontrados, {len(ausentes)} ausentes.")

        # Criar janela modal de resultados
        win = tk.Toplevel(self.root)
        win.title("Resultado da Comparação")
        win.geometry("680x500")
        win.minsize(550, 400)
        win.transient(self.root)
        win.grab_set()

        # Adicionar padding interno
        frm_main = ttk.Frame(win, padding=10)
        frm_main.pack(fill="both", expand=True)

        # Informações da pasta
        lbl_pasta = ttk.Label(frm_main, text=f"Pasta analisada: {pasta}", font=("TkDefaultFont", 9, "bold"), wraplength=600)
        lbl_pasta.pack(fill="x", anchor="w", pady=(0, 10))

        # Sumário
        frm_sumario = ttk.LabelFrame(frm_main, text="Sumário", padding=8)
        frm_sumario.pack(fill="x", pady=(0, 10))

        # Grid de informações
        col_pad = {"padx": 15, "pady": 4}
        lbl_tot = ttk.Label(frm_sumario, text=f"Total no XML: {len(self.todos_desenhos)}", font=("TkDefaultFont", 10, "bold"))
        lbl_tot.grid(row=0, column=0, sticky="w", **col_pad)

        lbl_enc = ttk.Label(frm_sumario, text=f"Encontrados: {len(encontrados)}", font=("TkDefaultFont", 10, "bold"), foreground="green")
        lbl_enc.grid(row=0, column=1, sticky="w", **col_pad)

        lbl_aus = ttk.Label(frm_sumario, text=f"Ausentes: {len(ausentes)}", font=("TkDefaultFont", 10, "bold"), foreground="red" if ausentes else "darkgreen")
        lbl_aus.grid(row=0, column=2, sticky="w", **col_pad)

        # Notebook (Abas)
        notebook = ttk.Notebook(frm_main)
        notebook.pack(fill="both", expand=True, pady=(0, 10))

        # Aba 1: Ausentes
        tab_ausentes = ttk.Frame(notebook)
        notebook.add(tab_ausentes, text=f"Ausentes ({len(ausentes)})")

        if ausentes:
            list_aus = tk.Listbox(tab_ausentes, selectmode="extended")
            list_aus.pack(side="left", fill="both", expand=True, padx=4, pady=4)
            scroll_aus = ttk.Scrollbar(tab_ausentes, orient="vertical", command=list_aus.yview)
            scroll_aus.pack(side="right", fill="y", pady=4)
            list_aus.config(yscrollcommand=scroll_aus.set)
            
            for item in ausentes:
                list_aus.insert(tk.END, item)
        else:
            lbl_ok = ttk.Label(tab_ausentes, text="🎉 Todos os desenhos estão presentes nesta pasta!", font=("TkDefaultFont", 11, "italic"), anchor="center")
            lbl_ok.pack(fill="both", expand=True)

        # Aba 2: Encontrados
        tab_encontrados = ttk.Frame(notebook)
        notebook.add(tab_encontrados, text=f"Encontrados ({len(encontrados)})")

        if encontrados:
            # Treeview para mostrar Desenho e Caminho do Arquivo
            cols = ("desenho", "caminho")
            tree_enc = ttk.Treeview(tab_encontrados, columns=cols, show="headings", selectmode="browse")
            tree_enc.heading("desenho", text="Desenho")
            tree_enc.heading("caminho", text="Caminho do Arquivo Encontrado")
            tree_enc.column("desenho", width=150, anchor="w")
            tree_enc.column("caminho", width=400, anchor="w")
            
            tree_enc.pack(side="left", fill="both", expand=True, padx=4, pady=4)
            
            scroll_enc = ttk.Scrollbar(tab_encontrados, orient="vertical", command=tree_enc.yview)
            scroll_enc.pack(side="right", fill="y", pady=4)
            tree_enc.config(yscrollcommand=scroll_enc.set)
            
            for d, cam in encontrados:
                tree_enc.insert("", tk.END, values=(d, cam))
        else:
            lbl_nok = ttk.Label(tab_encontrados, text="Nenhum desenho do XML foi encontrado nesta pasta.", font=("TkDefaultFont", 11, "italic"), anchor="center")
            lbl_nok.pack(fill="both", expand=True)

        # Ações na parte inferior
        frm_acoes = ttk.Frame(win, padding=10)
        frm_acoes.pack(fill="x", side="bottom")

        def copiar_ausentes():
            if not ausentes:
                messagebox.showinfo("Aviso", "Nenhum desenho ausente para copiar.")
                return
            win.clipboard_clear()
            win.clipboard_append("\n".join(ausentes))
            messagebox.showinfo("Copiado", "Lista de desenhos ausentes copiada para a área de transferência.")

        def exportar_relatorio():
            caminho_salvar = filedialog.asksaveasfilename(
                title="Salvar Relatório de Comparação",
                defaultextension=".txt",
                filetypes=[("Arquivos de Texto", "*.txt")],
                initialfile="relatorio_comparacao.txt"
            )
            if not caminho_salvar:
                return
            try:
                with open(caminho_salvar, "w", encoding="utf-8") as f:
                    f.write("=======================================================================\n")
                    f.write("RELATÓRIO DE COMPARAÇÃO DE EXISTÊNCIA DE DESENHOS\n")
                    f.write(f"DATA/HORA: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                    f.write(f"XML DE ORIGEM: {self.arquivo_xml.get()}\n")
                    f.write(f"PASTA DE COMPARAÇÃO: {pasta}\n")
                    f.write("=======================================================================\n\n")
                    
                    f.write(f"SUMÁRIO:\n")
                    f.write(f"  - Total de desenhos no XML: {len(self.todos_desenhos)}\n")
                    f.write(f"  - Desenhos encontrados: {len(encontrados)}\n")
                    f.write(f"  - Desenhos ausentes: {len(ausentes)}\n\n")
                    
                    f.write("=======================================================================\n")
                    f.write(f"DESENHOS AUSENTES ({len(ausentes)}):\n")
                    f.write("=======================================================================\n")
                    if ausentes:
                        for item in ausentes:
                            f.write(f"  - {item}\n")
                    else:
                        f.write("  (Nenhum desenho ausente)\n")
                    f.write("\n")
                    
                    f.write("=======================================================================\n")
                    f.write(f"DESENHOS ENCONTRADOS ({len(encontrados)}):\n")
                    f.write("=======================================================================\n")
                    if encontrados:
                        for d, cam in encontrados:
                            f.write(f"  - {d} -> {cam}\n")
                    else:
                        f.write("  (Nenhum desenho encontrado)\n")
                        
                messagebox.showinfo("Sucesso", f"Relatório exportado com sucesso para:\n{caminho_salvar}")
            except Exception as ex:
                messagebox.showerror("Erro ao exportar", f"Não foi possível salvar o relatório:\n{ex}")

        # Botões do rodapé da modal
        ttk.Button(frm_acoes, text="Copiar Nomes dos Ausentes", command=copiar_ausentes).pack(side="left")
        ttk.Button(frm_acoes, text="Exportar Relatório (.txt)", command=exportar_relatorio).pack(side="left", padx=8)
        ttk.Button(frm_acoes, text="Fechar", command=win.destroy).pack(side="right")

    def _salvar_config(self):
        config = {
            "pasta_busca": self.pasta_busca.get(),
            "pasta_destino": self.pasta_destino.get()
        }
        salvar_config(config)


def main():
    root = tk.Tk()
    # Tema mais agradável quando disponível
    try:
        ttk.Style().theme_use("vista" if sys.platform.startswith("win") else "clam")
    except tk.TclError:
        pass
    LeitorDesenhosApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
