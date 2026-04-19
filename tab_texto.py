import streamlit as st
import pandas as pd
import re
import io
import unicodedata
from collections import Counter
from helpers import extrair_padroes, log_acao, df_to_csv_bytes, OURO, MARROM

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


# ── Stopwords base (português) ─────────────────────────────────────────────
_STOPS_BASE = {
    "para", "como", "mais", "que", "com", "dos", "das", "uma", "uns", "umas", "por",
    "são", "está", "isso", "esse", "essa", "este", "esta", "mas", "não", "nos", "nas",
    "pelo", "pela", "pelos", "pelas", "também", "sobre", "quando", "entre", "após",
    "durante", "antes", "desde", "até", "pois", "assim", "então", "ainda", "muito",
    "bem", "aqui", "onde", "qual", "quem", "será", "seria", "foram", "sendo", "tendo",
    "todo", "toda", "todos", "todas", "mesmo", "disso", "desse", "desta", "deste",
    "neste", "nessa", "naquele", "naquela", "seus", "suas", "nosso", "nossa",
    "tudo", "nada", "fazer", "feito", "apenas", "pode", "deve", "teve", "sido",
    "num", "numa", "outra", "outro", "outros", "outras", "cada", "tanto", "quanto",
    "depois", "sempre", "nunca", "talvez", "porém", "logo",
}

# termos muito genéricos no contexto jurídico/político
_STOPS_JORNALISMO = {
    "decisão", "documento", "federal", "nacional", "processo", "autos",
    "valores", "cumprimento", "execução", "relator", "relatora", "acórdão",
    "petição", "agravo", "regimental", "tribunal", "supremo", "corte",
}

# ── Lista de órgãos / instituições conhecidas ──────────────────────────────
_ORGAOS_LISTA = [
    "Supremo Tribunal Federal", "Superior Tribunal de Justiça", "Tribunal Superior do Trabalho",
    "Tribunal Superior Eleitoral", "Superior Tribunal Militar", "Tribunal de Contas da União",
    "Tribunal Regional Federal", "Tribunal Regional do Trabalho", "Tribunal Regional Eleitoral",
    "Ministério Público Federal", "Ministério Público Estadual", "Ministério Público",
    "Polícia Federal", "Polícia Civil", "Polícia Militar", "Polícia Rodoviária Federal",
    "Advocacia-Geral da União", "Controladoria-Geral da União", "Receita Federal",
    "Banco Central", "Banco do Brasil", "Caixa Econômica Federal", "BNDES",
    "IBGE", "IPEA", "ANATEL", "ANEEL", "ANS", "ANVISA", "ANAC", "ANP", "ANTAQ", "ANTT",
    "Petrobras", "Eletrobras", "Embraer", "Embrapa",
    "Câmara dos Deputados", "Senado Federal", "Congresso Nacional",
    "Presidência da República", "Casa Civil", "Palácio do Planalto",
    "Ministério da Fazenda", "Ministério da Justiça", "Ministério da Saúde",
    "Ministério da Educação", "Ministério do Trabalho", "Ministério do Meio Ambiente",
    "Ministério das Comunicações", "Ministério da Defesa", "Ministério das Relações Exteriores",
    "Secretaria do Tesouro Nacional", "Comissão de Valores Mobiliários", "CVM",
    "Conselho Administrativo de Defesa Econômica", "CADE",
    "Instituto Nacional do Seguro Social", "INSS", "SUS", "FGTS",
    "STF", "STJ", "TST", "TSE", "STM", "TCU", "TRF", "TRT", "TRE", "MPF", "MPE",
    "AGU", "CGU", "PGR", "DPU", "PF", "PRF", "PC", "PM",
]
_ORGAOS_LISTA.sort(key=len, reverse=True)

# padrões genéricos de órgão
_PADROES_ORGAOS = [
    r"\bSupremo Tribunal Federal\b",
    r"\bSuperior Tribunal de Justiça\b",
    r"\bTribunal Regional Federal(?:\s+da\s+\d+ª?\s+Região)?\b",
    r"\bTribunal Regional do Trabalho(?:\s+da\s+\d+ª?\s+Região)?\b",
    r"\bTribunal Regional Eleitoral\b",
    r"\bTribunal de Contas da União\b",
    r"\bTribunal Superior [A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]+)?\b",
    r"\bMinistério(?:\s+Público)?\s+da[s]?\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]+){0,3}\b",
    r"\bPolícia\s+(?:Federal|Civil|Militar|Rodoviária Federal)\b",
    r"\bDefensoria Pública(?:\s+da\s+União|\s+do\s+Estado)?\b",
    r"\bAdvocacia-Geral da União\b",
    r"\bControladoria-Geral da União\b",
    r"\bReceita Federal\b",
    r"\bCâmara dos Deputados\b",
    r"\bSenado Federal\b",
    r"\bCongresso Nacional\b",
    r"\bPresidência da República\b",
    r"\bCasa Civil\b",
    r"\bPalácio do Planalto\b",
    r"\bSecretaria\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]+(?:\s+do|\s+da|\s+de|\s+das|\s+dos)?(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç]+){0,4}\b",
]

# ── Filtros de nomes próprios ──────────────────────────────────────────────
_TOKENS_INSTITUCIONAIS = {
    "tribunal", "supremo", "superior", "corte", "polícia", "ministério", "união",
    "federal", "estadual", "nacional", "secretaria", "congresso", "senado", "câmara",
    "presidência", "palácio", "governo", "prefeitura", "estado", "município",
    "rodoviária", "público", "justiça", "defensoria", "advocacia", "controladoria",
    "receita", "comissão", "instituto", "conselho", "banco", "caixa",
    "nota", "jurídica", "documento", "autos", "processo", "relator", "relatora",
    "portaria", "normativa", "excelência", "tribunal", "pleno", "corte",
}

_TOKENS_NOME_VALIDOS = {"de", "da", "do", "das", "dos", "e"}

_ESTADOS_E_LUGARES = {
    "acre", "alagoas", "amapá", "amazonas", "bahia", "ceará", "distrito federal",
    "espírito santo", "goiás", "maranhão", "mato grosso", "mato grosso do sul",
    "minas gerais", "pará", "paraíba", "paraná", "pernambuco", "piauí",
    "rio de janeiro", "rio grande do norte", "rio grande do sul", "rondônia",
    "roraima", "santa catarina", "são paulo", "sergipe", "tocantins",
    "belo horizonte", "brasília",
}

_PALAVRAS_COMUNS_CAPITALIZADAS = {
    "Para", "Como", "Mais", "Que", "Com", "Por", "Não", "Nos", "Nas", "Pelo", "Pela",
    "Também", "Sobre", "Quando", "Entre", "Após", "Durante", "Antes", "Desde",
    "Pois", "Assim", "Então", "Ainda", "Muito", "Bem", "Aqui", "Onde", "Qual",
    "Essa", "Este", "Esta", "Esse", "Todo", "Toda", "Numa", "Num", "Depois",
    "Sempre", "Nunca", "Porém", "Logo", "Caso", "Cada", "Tanto", "Quanto",
    "Segundo", "Conforme", "Mediante", "Através", "Enquanto", "Embora", "Apesar",
}

# ── Helpers de limpeza ─────────────────────────────────────────────────────
def _sem_acento(texto):
    return "".join(
        ch for ch in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(ch) != "Mn"
    )

def _df_ativo():
    df_limpo = st.session_state.get("df_limpo")
    if df_limpo is not None:
        return df_limpo

    df = st.session_state.get("df")
    if df is not None:
        return df

    return None

def _limpar_html(texto):
    if not BS4_OK:
        return re.sub(r"<[^>]+>", " ", texto)
    soup = BeautifulSoup(texto, "html.parser")
    return soup.get_text(separator=" ", strip=True)

def _texto_limpo(texto_bruto):
    return re.sub(r"\s+", " ", texto_bruto).strip()

def _normalizar_espacos(texto):
    return re.sub(r"\s+", " ", str(texto)).strip()

def _normalizar_chave_texto(texto):
    return _sem_acento(_normalizar_espacos(texto).lower())

def _titulo_limpo(texto):
    texto = _normalizar_espacos(texto)
    texto = re.sub(r"\s+([,.;:!?])", r"\1", texto)
    return texto

def _eh_candidato_pessoa(nome):
    nome_limpo = _titulo_limpo(nome)
    nome_norm = _normalizar_chave_texto(nome_limpo)

    if nome_norm in _ESTADOS_E_LUGARES:
        return False

    partes = nome_limpo.split()
    if not 2 <= len(partes) <= 4:
        return False

    if partes[0] in _PALAVRAS_COMUNS_CAPITALIZADAS:
        return False

    fortes = 0
    for parte in partes:
        p_norm = _normalizar_chave_texto(parte)
        if p_norm in _TOKENS_INSTITUCIONAIS:
            return False
        if p_norm not in _TOKENS_NOME_VALIDOS:
            fortes += 1

    # exige pelo menos 2 palavras "fortes" de nome
    return fortes >= 2

def _normalizar_numero_texto(valor):
    valor = _normalizar_espacos(valor)
    valor = valor.replace("R$ ", "R$").replace("R$.", "R$")
    valor = valor.replace(" ,", ",").replace(" .", ".")
    return valor

def _adicionar_resultado_num(resultados, spans, inicio, fim, tipo, valor):
    # evita sobreposição de matches, ex: R$ 100 mil entrar também como quantidade
    if any(not (fim <= s or inicio >= e) for s, e in spans):
        return

    valor_fmt = _normalizar_numero_texto(valor)
    chave = (tipo, valor_fmt.lower())
    if chave in resultados:
        return

    resultados[chave] = {"Tipo": tipo, "Valor encontrado": valor_fmt}
    spans.append((inicio, fim))


# ── 1. Palavras mais frequentes ────────────────────────────────────────────
def _frequencia_termos(texto, top_n=30, min_len=4, stops_extras=None):
    stops = _STOPS_BASE | _STOPS_JORNALISMO
    if stops_extras:
        stops.update(w.strip().lower() for w in stops_extras if w.strip())

    palavras = re.findall(rf"[a-zA-ZÀ-ÖØ-öø-ÿ]{{{min_len},}}", texto)
    palavras = [p.lower() for p in palavras if p.lower() not in stops]
    return Counter(palavras).most_common(top_n)


# ── 2. Nomes próprios ──────────────────────────────────────────────────────
def _extrair_nomes(texto):
    # remove órgãos conhecidos e padrões institucionais antes de procurar pessoas
    texto_sem_orgaos = texto

    for org in _ORGAOS_LISTA:
        texto_sem_orgaos = re.sub(re.escape(org), " ", texto_sem_orgaos, flags=re.IGNORECASE)

    for padrao in _PADROES_ORGAOS:
        texto_sem_orgaos = re.sub(padrao, " ", texto_sem_orgaos, flags=re.IGNORECASE)

    # permite conectores tipo "de", "da", "do", "dos", "das", "e"
    padrao = (
        r"\b("
        r"[A-ZÁÉÍÓÚÀÂÊÎÔÛÃÕÇ][a-záéíóúàâêîôûãõç]+"
        r"(?:\s(?:de|da|do|das|dos|e)\s[A-ZÁÉÍÓÚÀÂÊÎÔÛÃÕÇ][a-záéíóúàâêîôûãõç]+)?"
        r"(?:\s[A-ZÁÉÍÓÚÀÂÊÎÔÛÃÕÇ][a-záéíóúàâêîôûãõç]+){1,2}"
        r")\b"
    )

    candidatos = re.findall(padrao, texto_sem_orgaos)
    candidatos = [_titulo_limpo(c) for c in candidatos]
    filtrados = [c for c in candidatos if _eh_candidato_pessoa(c)]

    contagem = Counter()
    for nome in filtrados:
        contagem[nome] += 1

    return contagem.most_common(50)


# ── 3. Órgãos / Instituições ───────────────────────────────────────────────
def _extrair_orgaos(texto):
    contagem = Counter()

    # lista fixa
    for org in _ORGAOS_LISTA:
        ocorrs = re.findall(re.escape(org), texto, flags=re.IGNORECASE)
        if ocorrs:
            contagem[_titulo_limpo(org)] += len(ocorrs)

    # padrões mais soltos
    for padrao in _PADROES_ORGAOS:
        for m in re.finditer(padrao, texto, re.IGNORECASE):
            org = _titulo_limpo(m.group())
            contagem[org] += 1

    return contagem.most_common(50)


# ── 4. Números / Valores ───────────────────────────────────────────────────
_PADRAO_VALOR_RS = r"R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d+)?(?:\s*(?:mil|milhão|milhões|bilhão|bilhões|trilhão|trilhões))?"
_PADRAO_PERCENTUAL = r"\b\d+(?:[.,]\d+)?\s*%"
_PADRAO_QUANTIDADE = r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b"
_PADRAO_NUM_SIMPLES = r"\b\d+(?:[.,]\d+)?\s*(?:mil|milhão|milhões|bilhão|bilhões|trilhão|trilhões)\b"

def _extrair_numeros(texto):
    resultados = {}
    spans = []

    # ordem importa: valores e percentuais primeiro
    for m in re.finditer(_PADRAO_VALOR_RS, texto, re.IGNORECASE):
        _adicionar_resultado_num(resultados, spans, m.start(), m.end(), "Valor em R$", m.group())

    for m in re.finditer(_PADRAO_PERCENTUAL, texto, re.IGNORECASE):
        _adicionar_resultado_num(resultados, spans, m.start(), m.end(), "Percentual", m.group())

    for m in re.finditer(_PADRAO_NUM_SIMPLES, texto, re.IGNORECASE):
        _adicionar_resultado_num(resultados, spans, m.start(), m.end(), "Número simples", m.group())

    for m in re.finditer(_PADRAO_QUANTIDADE, texto, re.IGNORECASE):
        _adicionar_resultado_num(resultados, spans, m.start(), m.end(), "Quantidade", m.group())

    return list(resultados.values())


# ── 5. Datas ───────────────────────────────────────────────────────────────
_MESES = r"(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)"

_PADROES_DATAS = [
    ("Data completa (DD/MM/AAAA)", r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ("Data completa (DD-MM-AAAA)", r"\b\d{1,2}-\d{1,2}-\d{2,4}\b"),
    ("Data por extenso", rf"\b\d{{1,2}}(?:º)?\s+de\s+{_MESES}(?:\s+de\s+\d{{4}})?\b"),
    ("Mês e ano", rf"\b{_MESES}(?:\s+de)?\s+\d{{4}}\b"),
    ("Ano isolado", r"\b(?:19[0-9]{2}|20[0-3][0-9])\b"),
]

def _extrair_datas(texto):
    resultados = []
    for tipo, padrao in _PADROES_DATAS:
        for m in re.finditer(padrao, texto, re.IGNORECASE):
            resultados.append({"Tipo": tipo, "Data encontrada": _titulo_limpo(m.group())})

    vistos = set()
    unicos = []
    for r in resultados:
        chave = (r["Tipo"], r["Data encontrada"].lower())
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    return unicos


# ── 6. Siglas ──────────────────────────────────────────────────────────────
_SIGLAS_IGNORAR = {"I", "A", "E", "O", "U", "DE", "DO", "DA", "DI", "EM", "NA", "NO", "AO"}

def _extrair_siglas(texto):
    candidatos = re.findall(r"\b[A-ZÁÉÍÓÚÀ]{2,7}(?:[-\.][A-ZÁÉÍÓÚÀ]{1,4})?\b", texto)
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
            "⬇️ Exportar CSV",
            df_to_csv_bytes(df),
            nome_arquivo,
            "text/csv",
            key=key,
        )


# ══════════════════════════════════════════════════════════════════════════════
def render():
    st.subheader("📄 Extrair de Texto")

    texto_sessao = st.session_state.get("texto_carregado", "")
    nome_sessao = st.session_state.get("nome_arquivo", "")

    df_ativo = _df_ativo()
    cols_texto_df = []
    if df_ativo is not None and not df_ativo.empty:
        cols_texto_df = df_ativo.select_dtypes("object").columns.tolist()

    st.markdown("Faça upload de um arquivo textual, cole o texto ou analise uma coluna da base carregada.")

    opcoes_fonte = ["Upload de arquivo", "Colar texto", "Usar arquivo já carregado"]
    if cols_texto_df:
        opcoes_fonte.append("Coluna da base de dados")

    fonte = st.radio("Fonte do texto", opcoes_fonte, horizontal=True, key="txt_fonte")

    texto_bruto = ""

    if fonte == "Upload de arquivo":
        arq = st.file_uploader("TXT, HTML ou PDF", type=["txt", "html", "htm", "pdf"], key="upload_texto")
        if arq:
            conteudo = arq.read()
            ext = arq.name.rsplit(".", 1)[-1].lower()

            if ext == "txt":
                texto_bruto = conteudo.decode("utf-8", errors="replace")
            elif ext in ("html", "htm"):
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
        texto_bruto = " ".join(df_ativo[col_sel].dropna().astype(str).tolist())
        st.info(f"📊 Analisando coluna **{col_sel}** — {len(df_ativo[col_sel].dropna())} registros concatenados.")

    if not texto_bruto.strip():
        return

    texto_lp = _texto_limpo(texto_bruto)

    st.divider()
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Caracteres", f"{len(texto_bruto):,}".replace(",", "."))
    col_m2.metric("Palavras", f"{len(texto_bruto.split()):,}".replace(",", "."))

    with st.expander("📄 Texto bruto"):
        st.text_area("", texto_bruto[:5000], height=200, disabled=True, key="txt_bruto_view")

    with st.expander("🧹 Texto limpo"):
        st.text_area("", texto_lp[:5000], height=150, disabled=True, key="txt_limpo_view")

    st.divider()

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
                fig = px.bar(
                    df_freq.head(20),
                    x="Frequência",
                    y="Termo",
                    orientation="h",
                    color_discrete_sequence=[OURO],
                )
                fig.update_traces(marker_color=OURO)
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"),
                    height=500,
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum termo frequente encontrado no texto.")

    with aba_nomes:
        st.markdown("Sequências de palavras com iniciais maiúsculas que podem indicar nomes de pessoas.")
        st.caption("⚠️ Agora a heurística tenta separar pessoa de órgão/lugar, mas ainda vale revisar.")

        nomes = _extrair_nomes(texto_bruto)
        if nomes:
            df_nomes = pd.DataFrame(nomes, columns=["Nome", "Frequência"])
            _mostrar_tabela(df_nomes)
            _botao_export(df_nomes, "bussola_nomes.csv", "exp_nomes")
        else:
            st.info("Nenhum nome próprio identificado com o padrão atual.")

    with aba_orgaos:
        st.markdown("Menções a órgãos públicos, tribunais, ministérios e instituições conhecidas.")

        orgaos = _extrair_orgaos(texto_bruto)
        if orgaos:
            df_orgaos = pd.DataFrame(orgaos, columns=["Órgão / Instituição", "Frequência"])
            _mostrar_tabela(df_orgaos)
            _botao_export(df_orgaos, "bussola_orgaos.csv", "exp_orgaos")
        else:
            st.info("Nenhum órgão ou instituição identificado no texto.")

        with st.expander("ℹ️ Ver lista de órgãos reconhecidos"):
            st.markdown(", ".join(f"`{o}`" for o in sorted(_ORGAOS_LISTA)))

    with aba_nums:
        st.markdown("Valores monetários, percentuais e quantidades numéricas relevantes encontrados no texto.")

        nums = _extrair_numeros(texto_bruto)
        if nums:
            df_nums = pd.DataFrame(nums)
            _mostrar_tabela(df_nums)
            _botao_export(df_nums, "bussola_numeros.csv", "exp_nums")
        else:
            st.info("Nenhum valor monetário, percentual ou quantidade identificado.")

    with aba_datas:
        st.markdown("Datas em diferentes formatos encontradas no texto.")

        datas = _extrair_datas(texto_bruto)
        if datas:
            df_datas = pd.DataFrame(datas)
            _mostrar_tabela(df_datas)
            _botao_export(df_datas, "bussola_datas.csv", "exp_datas")
        else:
            st.info("Nenhuma data identificada no texto.")

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
                fig_s = px.bar(
                    df_siglas.head(20),
                    x="Frequência",
                    y="Sigla",
                    orientation="h",
                    color_discrete_sequence=[OURO],
                )
                fig_s.update_traces(marker_color=OURO)
                fig_s.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=dict(autorange="reversed"),
                    height=500,
                    margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(fig_s, use_container_width=True)
        else:
            st.info("Nenhuma sigla identificada no texto.")

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
                        f"bussola_{nome.lower().replace(' ', '_')}.csv",
                        "text/csv",
                        key=f"exp_{nome}",
                    )
        else:
            st.info("Nenhum padrão estruturado identificado.")

    with aba_busca:
        st.markdown("Busque qualquer palavra ou expressão no texto e veja os trechos onde ela aparece.")

        termo_busca = st.text_input("Buscar termo", key="busca_doc")
        if termo_busca:
            ocorrencias = [
                (m.start(), texto_bruto[max(0, m.start() - 120):m.end() + 120])
                for m in re.finditer(re.escape(termo_busca), texto_bruto, re.IGNORECASE)
            ]

            if ocorrencias:
                st.success(f"**{len(ocorrencias)}** ocorrência(s) encontrada(s).")
                for i, (pos, trecho) in enumerate(ocorrencias[:20], 1):
                    trecho_hl = re.sub(
                        f"({re.escape(termo_busca)})",
                        r"**\1**",
                        trecho,
                        flags=re.IGNORECASE,
                    )
                    st.markdown(f"**#{i}** (pos {pos}): …{trecho_hl}…")
                    st.divider()
            else:
                st.info("Termo não encontrado no documento.")

    log_acao(f"Extração de texto — {len(padroes) if 'padroes' in locals() else 0} tipos de padrão encontrados")
