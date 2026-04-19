import streamlit as st
import pandas as pd
import re
import io
from collections import Counter
from helpers import extrair_padroes, log_acao, df_to_csv_bytes

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

import plotly.express as px
from helpers import OURO, MARROM

# ── Stopwords base (português) ─────────────────────────────────────────────
_STOPS_BASE = {
    "para","como","mais","que","com","dos","das","uma","uns","umas","por",
    "são","está","isso","esse","essa","este","esta","mas","não","nos","nas",
    "pelo","pela","pelos","pelas","também","sobre","quando","entre","após",
    "durante","antes","desde","até","pois","assim","então","ainda","muito",
    "bem","aqui","onde","qual","quem","será","seria","foram","sendo","tendo",
    "todo","toda","todos","todas","mesmo","disso","desse","desta","deste",
    "neste","nessa","nessa","naquele","naquela","seus","suas","nosso","nossa",
    "tudo","nada","fazer","feito","apenas","pode","deve","teve","será","sido",
    "pelo","pela","num","numa","pelo","pela","outra","outro","outros","outras",
    "cada","tanto","quanto","depois","sempre","nunca","talvez","porém","logo",
}

# ── Lista de órgãos / instituições conhecidas ──────────────────────────────
_ORGAOS_LISTA = [
    "Supremo Tribunal Federal","Superior Tribunal de Justiça","Tribunal Superior do Trabalho",
    "Tribunal Superior Eleitoral","Superior Tribunal Militar","Tribunal de Contas da União",
    "Tribunal Regional Federal","Tribunal Regional do Trabalho","Tribunal Regional Eleitoral",
    "Ministério Público Federal","Ministério Público Estadual","Ministério Público",
    "Polícia Federal","Polícia Civil","Polícia Militar","Polícia Rodoviária Federal",
    "Advocacia-Geral da União","Controladoria-Geral da União","Receita Federal",
    "Banco Central","Banco do Brasil","Caixa Econômica Federal","BNDES",
    "IBGE","IPEA","ANATEL","ANEEL","ANS","ANVISA","ANAC","ANP","ANTAQ","ANTT",
    "Petrobras","Eletrobras","Embraer","Embrapa",
    "Câmara dos Deputados","Senado Federal","Congresso Nacional",
    "Presidência da República","Casa Civil","Palácio do Planalto",
    "Ministério da Fazenda","Ministério da Justiça","Ministério da Saúde",
    "Ministério da Educação","Ministério do Trabalho","Ministério do Meio Ambiente",
    "Ministério das Comunicações","Ministério da Defesa","Ministério das Relações Exteriores",
    "Secretaria do Tesouro Nacional","Comissão de Valores Mobiliários","CVM",
    "Conselho Administrativo de Defesa Econômica","CADE",
    "Instituto Nacional do Seguro Social","INSS","SUS","FGTS",
    "STF","STJ","TST","TSE","STM","TCU","TRF","TRT","TRE","MPF","MPE",
    "AGU","CGU","PGR","DPU","PF","PRF","PC","PM",
]
# Ordena do mais longo para o mais curto para evitar match parcial
_ORGAOS_LISTA.sort(key=len, reverse=True)

# ── Helpers de limpeza ─────────────────────────────────────────────────────
def _limpar_html(texto):
    if not BS4_OK:
        return re.sub(r"<[^>]+>", " ", texto)
    soup = BeautifulSoup(texto, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def _texto_limpo(texto_bruto):
    return re.sub(r"\s+", " ", texto_bruto).strip()

# ── 1. Palavras mais frequentes ────────────────────────────────────────────
def _frequencia_termos(texto, top_n=30, min_len=4, stops_extras=None):
    stops = _STOPS_BASE.copy()
    if stops_extras:
        stops.update(w.strip().lower() for w in stops_extras if w.strip())
    palavras = re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ]{%d,}" % min_len, texto)
    palavras = [p.lower() for p in palavras if p.lower() not in stops]
    return Counter(palavras).most_common(top_n)

# ── 2. Nomes próprios (heurística: sequências Title Case fora de início de frase) ──
def _extrair_nomes(texto):
    """
    Heurística simples: sequências de 2-4 palavras iniciadas por maiúscula
    que não sejam órgãos já mapeados. Filtra palavras comuns capitalizadas
    (início de frase) exigindo que o token anterior não seja pontuação final.
    """
    # Remove os órgãos do texto para evitar dupla contagem
    texto_sem_orgaos = texto
    for org in _ORGAOS_LISTA:
        texto_sem_orgaos = re.sub(re.escape(org), " ", texto_sem_orgaos, flags=re.IGNORECASE)

    # Padrão: 2 a 4 palavras Title Case consecutivas
    padrao = r'\b([A-ZÁÉÍÓÚÀÂÊÎÔÛÃÕÇ][a-záéíóúàâêîôûãõç]+(?:\s[A-ZÁÉÍÓÚÀÂÊÎÔÛÃÕÇ][a-záéíóúàâêîôûãõç]+){1,3})\b'
    candidatos = re.findall(padrao, texto_sem_orgaos)

    # Remove sequências que começam logo após ponto/exclamação/interrogação
    # (início de frase — muito falso positivo)
    # Estratégia: remover se a primeira palavra for stopword capitalizada
    _palavras_comuns = {
        "Para","Como","Mais","Que","Com","Por","Não","Nos","Nas","Pelo","Pela",
        "Também","Sobre","Quando","Entre","Após","Durante","Antes","Desde",
        "Pois","Assim","Então","Ainda","Muito","Bem","Aqui","Onde","Qual",
        "Essa","Este","Esta","Esse","Todo","Toda","Numa","Num","Pelo","Pela",
        "Depois","Sempre","Nunca","Porém","Logo","Caso","Cada","Tanto","Quanto",
        "Segundo","Conforme","Mediante","Através","Enquanto","Embora","Apesar",
    }
    filtrados = [c for c in candidatos if c.split()[0] not in _palavras_comuns]
    return Counter(filtrados).most_common(50)

# ── 3. Órgãos / Instituições ───────────────────────────────────────────────
def _extrair_orgaos(texto):
    contagem = Counter()
    for org in _ORGAOS_LISTA:
        ocorrs = re.findall(re.escape(org), texto, flags=re.IGNORECASE)
        if ocorrs:
            contagem[org] += len(ocorrs)
    return contagem.most_common(50)

# ── 4. Números / Valores ───────────────────────────────────────────────────
_PADROES_NUMEROS = [
    ("Valor em R$",    r"R\$\s*[\d.,]+(?:\s*(?:mil|milhões?|bilhões?|trilhões?))?"),
    ("Percentual",     r"\d+(?:[.,]\d+)?\s*%"),
    ("Quantidade",     r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b"),   # ex: 1.234.567
    ("Número simples", r"\b\d+(?:[.,]\d+)?\s*(?:mil|milhões?|bilhões?)"),
]

def _extrair_numeros(texto):
    resultados = []
    for tipo, padrao in _PADROES_NUMEROS:
        for m in re.finditer(padrao, texto, re.IGNORECASE):
            resultados.append({"Tipo": tipo, "Valor encontrado": m.group().strip()})
    # Remove duplicatas mantendo ordem
    vistos = set()
    unicos = []
    for r in resultados:
        chave = (r["Tipo"], r["Valor encontrado"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    return unicos

# ── 5. Datas ───────────────────────────────────────────────────────────────
_MESES = r"(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)"

_PADROES_DATAS = [
    ("Data completa (DD/MM/AAAA)", r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ("Data completa (DD-MM-AAAA)", r"\b\d{1,2}-\d{1,2}-\d{2,4}\b"),
    ("Data por extenso",           rf"\b\d{{1,2}}\s+de\s+{_MESES}(?:\s+de\s+\d{{4}})?\b"),
    ("Mês e ano",                  rf"\b{_MESES}(?:\s+de)?\s+\d{{4}}\b"),
    ("Ano isolado",                r"\b(?:19[0-9]{2}|20[0-2][0-9])\b"),
]

def _extrair_datas(texto):
    resultados = []
    for tipo, padrao in _PADROES_DATAS:
        for m in re.finditer(padrao, texto, re.IGNORECASE):
            resultados.append({"Tipo": tipo, "Data encontrada": m.group().strip()})
    vistos = set()
    unicos = []
    for r in resultados:
        chave = (r["Tipo"], r["Data encontrada"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    return unicos

# ── 6. Siglas ──────────────────────────────────────────────────────────────
# Falsos positivos comuns a ignorar
_SIGLAS_IGNORAR = {"I","A","E","O","U","DE","DO","DA","DI","EM","NA","NO","AO"}

def _extrair_siglas(texto):
    # Siglas: 2-7 letras maiúsculas, opcionalmente com hífen/ponto interno
    candidatos = re.findall(r'\b[A-ZÁÉÍÓÚÀ]{2,7}(?:[-\.][A-ZÁÉÍÓÚÀ]{1,4})?\b', texto)
    filtrados = [s for s in candidatos if s not in _SIGLAS_IGNORAR and not s.isdigit()]
    return Counter(filtrados).most_common(50)

# ── Bloco de exibição padronizado ──────────────────────────────────────────
def _mostrar_tabela(df, label_vazio="Nenhum resultado encontrado."):
    if df is None or df.empty:
        st.info(label_vazio)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

def _botao_export(df, nome_arquivo, key):
    if df is not None and not df.empty:
        st.download_button(
            f"⬇️ Exportar CSV",
            df_to_csv_bytes(df),
            nome_arquivo,
            "text/csv",
            key=key,
        )

# ══════════════════════════════════════════════════════════════════════════════
def render():
    st.subheader("📄 Extrair de Texto")

    # ── Fonte do texto ────────────────────────────────────────────────────
    texto_sessao = st.session_state.get("texto_carregado", "")
    nome_sessao  = st.session_state.get("nome_arquivo", "")

    # Verifica se há colunas de texto no DataFrame carregado
    df_ativo = st.session_state.get("df_limpo") or st.session_state.get("df")
    cols_texto_df = []
    if df_ativo is not None:
        cols_texto_df = df_ativo.select_dtypes("object").columns.tolist()

    st.markdown("Faça upload de um arquivo textual, cole o texto ou analise uma coluna da base carregada.")

    opcoes_fonte = ["Upload de arquivo", "Colar texto", "Usar arquivo já carregado"]
    if cols_texto_df:
        opcoes_fonte.append("Coluna da base de dados")

    fonte = st.radio("Fonte do texto", opcoes_fonte, horizontal=True, key="txt_fonte")

    texto_bruto = ""

    if fonte == "Upload de arquivo":
        arq = st.file_uploader("TXT, HTML ou PDF", type=["txt","html","htm","pdf"], key="upload_texto")
        if arq:
            conteudo = arq.read()
            ext = arq.name.rsplit(".", 1)[-1].lower()
            if ext == "txt":
                texto_bruto = conteudo.decode("utf-8", errors="replace")
            elif ext in ("html","htm"):
                texto_bruto = _limpar_html(conteudo.decode("utf-8", errors="replace"))
            elif ext == "pdf":
                if PDF_OK:
                    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
                        texto_bruto = "\n".join(p.extract_text() or "" for p in pdf.pages)
                else:
                    st.error("pdfplumber não instalado. Execute: pip install pdfplumber")

    elif fonte == "Colar texto":
        texto_bruto = st.text_area("Cole o texto aqui", height=200, key="txt_area")

    elif fonte == "Usar arquivo já carregado":
        if texto_sessao:
            texto_bruto = texto_sessao
            st.info(f"📎 Usando texto do arquivo: **{nome_sessao}**")
        else:
            st.warning("Nenhum arquivo textual foi carregado na aba **Carregar Dados**.")
            return

    elif fonte == "Coluna da base de dados":
        col_sel = st.selectbox("Selecione a coluna de texto", cols_texto_df, key="txt_col_df")
        # Concatena todos os valores não-nulos da coluna em um único corpus
        texto_bruto = " ".join(df_ativo[col_sel].dropna().astype(str).tolist())
        st.info(f"📊 Analisando coluna **{col_sel}** — {len(df_ativo[col_sel].dropna())} registros concatenados.")

    if not texto_bruto.strip():
        return

    texto_lp = _texto_limpo(texto_bruto)

    # ── Métricas gerais ───────────────────────────────────────────────────
    st.divider()
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Caracteres", f"{len(texto_bruto):,}".replace(",","."))
    col_m2.metric("Palavras",   f"{len(texto_bruto.split()):,}".replace(",","."))

    with st.expander("📄 Texto bruto"):
        st.text_area("", texto_bruto[:5000], height=200, disabled=True, key="txt_bruto_view")
    with st.expander("🧹 Texto limpo"):
        st.text_area("", texto_lp[:5000], height=150, disabled=True, key="txt_limpo_view")

    st.divider()

    # ════════════════════════════════════════════════════════════════════════
    # ABAS DE EXTRAÇÃO
    # ════════════════════════════════════════════════════════════════════════
    aba_freq, aba_nomes, aba_orgaos, aba_nums, aba_datas, aba_siglas, aba_padroes, aba_busca = st.tabs([
        "📊 Palavras frequentes",
        "👤 Nomes próprios",
        "🏛️ Órgãos / Instituições",
        "🔢 Números / Valores",
        "📅 Datas",
        "🔤 Siglas",
        "🔍 Padrões estruturados",
        "🔎 Busca no documento",
    ])

    # ── Aba 1: Palavras frequentes ─────────────────────────────────────────
    with aba_freq:
        st.markdown("Termos que aparecem com mais frequência no texto, excluindo palavras muito comuns.")

        top_n = st.slider("Top N termos", 10, 100, 30, key="top_n_termos")
        stops_input = st.text_input(
            "Stopwords adicionais (separadas por vírgula)",
            placeholder="ex: empresa, governo, federal",
            key="stops_extras",
        )
        stops_extras = [s.strip() for s in stops_input.split(",")] if stops_input else []

        freq = _frequencia_termos(texto_lp, top_n=top_n, stops_extras=stops_extras)
        if freq:
            df_freq = pd.DataFrame(freq, columns=["Termo", "Frequência"])
            col_f1, col_f2 = st.columns([1, 1])
            with col_f1:
                _mostrar_tabela(df_freq)
                _botao_export(df_freq, "bussola_palavras_freq.csv", "exp_freq")
            with col_f2:
                fig = px.bar(df_freq.head(20), x="Frequência", y="Termo", orientation="h",
                             color_discrete_sequence=[OURO])
                fig.update_traces(marker_color=OURO)
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"), height=500,
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum termo frequente encontrado no texto.")

    # ── Aba 2: Nomes próprios ──────────────────────────────────────────────
    with aba_nomes:
        st.markdown("Sequências de palavras com iniciais maiúsculas que podem indicar nomes de pessoas.")
        st.caption("⚠️ Detecção por heurística — pode incluir falsos positivos. Revise os resultados.")

        nomes = _extrair_nomes(texto_bruto)
        if nomes:
            df_nomes = pd.DataFrame(nomes, columns=["Nome", "Frequência"])
            _mostrar_tabela(df_nomes)
            _botao_export(df_nomes, "bussola_nomes.csv", "exp_nomes")
        else:
            st.info("Nenhum nome próprio identificado com o padrão atual.")

    # ── Aba 3: Órgãos / Instituições ──────────────────────────────────────
    with aba_orgaos:
        st.markdown("Menções a órgãos públicos, tribunais, ministérios e instituições conhecidas.")

        orgaos = _extrair_orgaos(texto_bruto)
        if orgaos:
            df_orgaos = pd.DataFrame(orgaos, columns=["Órgão / Instituição", "Frequência"])
            _mostrar_tabela(df_orgaos)
            _botao_export(df_orgaos, "bussola_orgaos.csv", "exp_orgaos")
        else:
            st.info("Nenhum órgão ou instituição da lista foi encontrado no texto.")

        with st.expander("ℹ️ Ver lista de órgãos reconhecidos"):
            st.markdown(", ".join(f"`{o}`" for o in sorted(_ORGAOS_LISTA)))

    # ── Aba 4: Números / Valores ───────────────────────────────────────────
    with aba_nums:
        st.markdown("Valores monetários, percentuais e quantidades numéricas relevantes encontrados no texto.")

        nums = _extrair_numeros(texto_bruto)
        if nums:
            df_nums = pd.DataFrame(nums)
            _mostrar_tabela(df_nums)
            _botao_export(df_nums, "bussola_numeros.csv", "exp_nums")
        else:
            st.info("Nenhum valor monetário, percentual ou quantidade identificado.")

    # ── Aba 5: Datas ───────────────────────────────────────────────────────
    with aba_datas:
        st.markdown("Datas em diferentes formatos encontradas no texto.")

        datas = _extrair_datas(texto_bruto)
        if datas:
            df_datas = pd.DataFrame(datas)
            _mostrar_tabela(df_datas)
            _botao_export(df_datas, "bussola_datas.csv", "exp_datas")
        else:
            st.info("Nenhuma data identificada no texto.")

    # ── Aba 6: Siglas ──────────────────────────────────────────────────────
    with aba_siglas:
        st.markdown("Siglas detectadas no texto (sequências de 2 a 7 letras maiúsculas).")
        st.caption("Palavras muito curtas e artigos em maiúscula são filtrados automaticamente.")

        siglas = _extrair_siglas(texto_bruto)
        if siglas:
            df_siglas = pd.DataFrame(siglas, columns=["Sigla", "Frequência"])
            col_s1, col_s2 = st.columns([1, 1])
            with col_s1:
                _mostrar_tabela(df_siglas)
                _botao_export(df_siglas, "bussola_siglas.csv", "exp_siglas")
            with col_s2:
                fig_s = px.bar(df_siglas.head(20), x="Frequência", y="Sigla", orientation="h",
                               color_discrete_sequence=[OURO])
                fig_s.update_traces(marker_color=OURO)
                fig_s.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"), height=500,
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig_s, use_container_width=True)
        else:
            st.info("Nenhuma sigla identificada no texto.")

    # ── Aba 7: Padrões estruturados (lógica original de extrair_padroes) ───
    with aba_padroes:
        st.markdown("Padrões estruturados detectados via `extrair_padroes` (CPF, CNPJ, e-mails, URLs, etc.).")

        padroes = extrair_padroes(texto_bruto)
        if padroes:
            for nome, valores in padroes.items():
                with st.expander(f"**{nome}** — {len(valores)} encontrado(s)"):
                    df_pad = pd.DataFrame({"Valor": valores})
                    st.dataframe(df_pad, use_container_width=True, hide_index=True)
                    st.download_button(
                        f"⬇️ Exportar {nome}",
                        df_to_csv_bytes(df_pad),
                        f"bussola_{nome.lower().replace(' ','_')}.csv",
                        "text/csv",
                        key=f"exp_{nome}",
                    )
        else:
            st.info("Nenhum padrão estruturado identificado (datas, valores, CPF, etc.).")

    # ── Aba 8: Busca no documento ──────────────────────────────────────────
    with aba_busca:
        st.markdown("Busque qualquer palavra ou expressão no texto e veja os trechos onde ela aparece.")

        termo_busca = st.text_input("Buscar termo", key="busca_doc")
        if termo_busca:
            ocorrencias = [
                (m.start(), texto_bruto[max(0, m.start()-120):m.end()+120])
                for m in re.finditer(re.escape(termo_busca), texto_bruto, re.IGNORECASE)
            ]
            if ocorrencias:
                st.success(f"**{len(ocorrencias)}** ocorrência(s) encontrada(s).")
                for i, (pos, trecho) in enumerate(ocorrencias[:20], 1):
                    trecho_hl = re.sub(
                        f"({re.escape(termo_busca)})",
                        r"**\1**",
                        trecho, flags=re.IGNORECASE,
                    )
                    st.markdown(f"**#{i}** (pos {pos}): …{trecho_hl}…")
                    st.divider()
            else:
                st.info("Termo não encontrado no documento.")

    log_acao(f"Extração de texto — {len(padroes) if 'padroes' in dir() else 0} tipos de padrão encontrados")
