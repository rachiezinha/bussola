"""
Bússola — Ferramenta de jornalismo de dados
Ponto de entrada principal: streamlit run app.py
"""

import streamlit as st

# ── Configuração da página (deve ser o primeiro comando Streamlit) ────────────
st.set_page_config(
    page_title="Bússola · Jornalismo de Dados",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS global ────────────────────────────────────────────────────────────────
from helpers import inject_css, render_header
inject_css()

# ── Abas / módulos ────────────────────────────────────────────────────────────
import tab_carregar
import tab_limpar
import tab_explorar
import tab_visualizar
import tab_mapas
import tab_texto
import tab_comparador

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:16px 0 8px">
        <span style="font-size:2.4rem">🧭</span>
        <div style="font-size:1.4rem;font-weight:700;color:#bd8e27;font-family:Merriweather,serif">
            Bússola
        </div>
        <div style="font-size:.78rem;color:#c4b49a;margin-top:2px">
            Jornalismo de dados
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    SECOES = {
        "📂 Carregar Dados":        "carregar",
        "🧹 Limpar e Preparar":     "limpar",
        "🔎 Explorar Dados":        "explorar",
        "📈 Visualizar":            "visualizar",
        "🗺️  Mapas":               "mapas",
        "📄 Extrair de Texto":      "texto",
        "🔄 Comparador de Versões": "comparador",
    }

    secao_atual = st.radio(
        "Navegação",
        list(SECOES.keys()),
        key="nav_secao",
        label_visibility="collapsed"
    )
    chave = SECOES[secao_atual]

    st.divider()

    # Status do arquivo carregado
    df_sessao = st.session_state.get("df_limpo", None)
    if df_sessao is None:
        df_sessao = st.session_state.get("df", None)

    txt_sessao = st.session_state.get("texto_carregado", None)
    nome_arq = st.session_state.get("nome_arquivo", None)

    if nome_arq:
        st.markdown(f"""
        <div style="font-size:.78rem;color:#c4b49a">
            <b style="color:#bd8e27">Arquivo ativo:</b><br>
            {nome_arq}
        </div>
        """, unsafe_allow_html=True)

        if df_sessao is not None:
            st.markdown(f"""
            <div style="font-size:.75rem;color:#a09890;margin-top:4px">
            {len(df_sessao):,} linhas · {len(df_sessao.columns)} colunas
            </div>
            """.replace(",", "."), unsafe_allow_html=True)

        if txt_sessao is not None:
            st.markdown(f"""
            <div style="font-size:.75rem;color:#a09890;margin-top:2px">
            Texto: {len(txt_sessao):,} caracteres
            </div>
            """.replace(",", "."), unsafe_allow_html=True)

    else:
        st.markdown(
            '<div style="font-size:.78rem;color:#a09890">Nenhum arquivo carregado</div>',
            unsafe_allow_html=True
        )

    st.divider()
    st.markdown(
        '<div style="font-size:.7rem;color:#7a6e68;text-align:center">v0.1 · uso local</div>',
        unsafe_allow_html=True
    )

# ── Roteamento de seções ──────────────────────────────────────────────────────
render_header(secao_atual)

if chave == "carregar":
    tab_carregar.render()
elif chave == "limpar":
    tab_limpar.render()
elif chave == "explorar":
    tab_explorar.render()
elif chave == "visualizar":
    tab_visualizar.render()
elif chave == "mapas":
    tab_mapas.render()
elif chave == "texto":
    tab_texto.render()
elif chave == "comparador":
    tab_comparador.render()
