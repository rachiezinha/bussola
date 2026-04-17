import streamlit as st
import pandas as pd
import re
import io
from collections import Counter
from utils.helpers import extrair_padroes, log_acao, df_to_csv_bytes

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


def _limpar_html(texto):
    if not BS4_OK:
        return re.sub(r"<[^>]+>", " ", texto)
    soup = BeautifulSoup(texto, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _frequencia_termos(texto, top_n=30, min_len=4):
    palavras = re.findall(r"[a-zA-ZÀ-ÖØ-öø-ÿ]{%d,}" % min_len, texto)
    # Stopwords mínimas
    stops = {"para","como","mais","que","com","dos","das","uma","uns","umas","por",
             "são","está","isso","esse","essa","este","esta","mas","não","nos","nas",
             "pelo","pela","pelos","pelas","também","sobre","quando","entre","após",
             "durante","antes","desde","até","pois","assim","então","ainda"}
    palavras = [p.lower() for p in palavras if p.lower() not in stops]
    return Counter(palavras).most_common(top_n)


def render():
    st.subheader("📄 Extrair de Texto")

    # Verifica se já tem texto carregado de arquivo anterior
    texto_sessao = st.session_state.get("texto_carregado", "")
    nome_sessao  = st.session_state.get("nome_arquivo", "")

    st.markdown("Faça upload de um arquivo textual ou cole o texto diretamente.")

    fonte = st.radio("Fonte do texto", ["Upload de arquivo", "Colar texto", "Usar arquivo já carregado"],
                     horizontal=True, key="txt_fonte")

    texto_bruto = ""

    if fonte == "Upload de arquivo":
        arq = st.file_uploader("TXT, HTML ou PDF", type=["txt","html","htm","pdf"], key="upload_texto")
        if arq:
            conteudo = arq.read()
            ext = arq.name.rsplit(".",1)[-1].lower()
            if ext in ("txt",):
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

    else:
        if texto_sessao:
            texto_bruto = texto_sessao
            st.info(f"📎 Usando texto do arquivo: **{nome_sessao}**")
        else:
            st.warning("Nenhum arquivo textual foi carregado na aba **Carregar Dados**.")
            return

    if not texto_bruto.strip():
        return

    texto_limpo = re.sub(r"\s+", " ", texto_bruto).strip()

    st.divider()
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Caracteres", f"{len(texto_bruto):,}".replace(",","."))
    col_m2.metric("Palavras",   f"{len(texto_bruto.split()):,}".replace(",","."))

    with st.expander("📄 Texto bruto"):
        st.text_area("", texto_bruto[:5000], height=200, disabled=True, key="txt_bruto_view")

    with st.expander("🧹 Texto limpo"):
        st.text_area("", texto_limpo[:5000], height=150, disabled=True, key="txt_limpo_view")

    st.divider()

    # ── Extração de padrões ───────────────────────────────────────────────────
    st.markdown("#### 🔍 Entidades e padrões extraídos automaticamente")
    padroes = extrair_padroes(texto_bruto)

    if padroes:
        for nome, valores in padroes.items():
            with st.expander(f"**{nome}** — {len(valores)} encontrado(s)"):
                df_pad = pd.DataFrame({"Valor": valores})
                st.dataframe(df_pad, use_container_width=True, hide_index=True)
                st.download_button(
                    f"⬇️  Exportar {nome}",
                    df_to_csv_bytes(df_pad),
                    f"bussola_{nome.lower().replace(' ','_')}.csv",
                    "text/csv",
                    key=f"exp_{nome}"
                )
    else:
        st.info("Nenhum padrão estruturado identificado (datas, valores, CPF, etc.).")

    st.divider()

    # ── Frequência de termos ───────────────────────────────────────────────────
    st.markdown("#### 📊 Termos mais frequentes")
    top_n = st.slider("Top N termos", 10, 100, 30, key="top_n_termos")
    freq = _frequencia_termos(texto_limpo, top_n=top_n)
    if freq:
        df_freq = pd.DataFrame(freq, columns=["Termo", "Frequência"])
        col_f1, col_f2 = st.columns([1,1])
        with col_f1:
            st.dataframe(df_freq, use_container_width=True, hide_index=True)
        with col_f2:
            import plotly.express as px
            from utils.helpers import OURO, MARROM
            fig = px.bar(df_freq.head(20), x="Frequência", y="Termo", orientation="h",
                         color_discrete_sequence=[OURO])
            fig.update_traces(marker_color=OURO)
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(autorange="reversed"),
                height=500,
                margin=dict(l=0,r=0,t=10,b=0)
            )
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Busca no documento ────────────────────────────────────────────────────
    st.markdown("#### 🔎 Busca por palavra-chave no documento")
    termo_busca = st.text_input("Buscar termo", key="busca_doc")
    if termo_busca:
        ocorrencias = [(m.start(), texto_bruto[max(0,m.start()-120):m.end()+120])
                       for m in re.finditer(re.escape(termo_busca), texto_bruto, re.IGNORECASE)]
        if ocorrencias:
            st.success(f"**{len(ocorrencias)}** ocorrência(s) encontrada(s).")
            for i, (pos, trecho) in enumerate(ocorrencias[:20], 1):
                trecho_highlight = re.sub(
                    f"({re.escape(termo_busca)})",
                    r"<mark style='background:#bd8e27;color:#fff;border-radius:3px;padding:0 3px'>\1</mark>",
                    trecho, flags=re.IGNORECASE
                )
                st.markdown(f"**#{i}** (pos {pos}): …{trecho_highlight}…", unsafe_allow_html=True)
                st.divider()
        else:
            st.info("Termo não encontrado no documento.")

    log_acao(f"Extração de texto realizada — {len(padroes)} tipos de padrão encontrados")
