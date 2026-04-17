import pandas as pd
import numpy as np
import re
import io
import streamlit as st


# ── Paleta institucional ──────────────────────────────────────────────────────
OURO   = "#bd8e27"
MARROM = "#353330"
BEGE   = "#f8f6f2"
NEUTRO = "#7a7470"

PLOTLY_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="sans-serif", color="#1a1814"),
        colorway=[OURO, "#e8b84b", "#a67820", NEUTRO, "#5c5450", "#c4b49a"],
        title=dict(font=dict(color=MARROM, size=16)),
        xaxis=dict(gridcolor="#e0dbd4", linecolor="#ccc"),
        yaxis=dict(gridcolor="#e0dbd4", linecolor="#ccc"),
    )
)


# ── CSS global ────────────────────────────────────────────────────────────────
def inject_css():
    st.markdown("""
    <style>
    /* ---- tipografia & base ---- */
    @import url('https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    h1, h2, h3 { font-family: 'Merriweather', serif; color: #353330; }

    /* ---- sidebar ---- */
    section[data-testid="stSidebar"] {
        background: #353330 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #f0ead8 !important;
    }
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] .stSelectbox label {
        color: #bd8e27 !important;
        font-weight: 600;
    }

    /* ---- botões ---- */
    .stButton > button {
        background: #bd8e27 !important;
        color: #fff !important;
        border: none !important;
        border-radius: 4px !important;
        font-weight: 600;
        transition: opacity .2s;
    }
    .stButton > button:hover { opacity: .85; }

    /* ---- tabs ---- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 2px solid #bd8e27;
    }
    .stTabs [data-baseweb="tab"] {
        background: #ede9e0;
        border-radius: 4px 4px 0 0;
        color: #353330;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: #bd8e27 !important;
        color: #fff !important;
    }

    /* ---- cards métricas ---- */
    div[data-testid="metric-container"] {
        background: #fff;
        border-left: 4px solid #bd8e27;
        border-radius: 4px;
        padding: 12px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,.08);
    }

    /* ---- dataframe ---- */
    .stDataFrame { border: 1px solid #e0dbd4; border-radius: 4px; }

    /* ---- alertas / badges ---- */
    .badge-alerta {
        display:inline-block; background:#bd8e27; color:#fff;
        border-radius:12px; padding:2px 10px; font-size:.78rem; font-weight:600;
    }
    .badge-ok {
        display:inline-block; background:#5c8a5c; color:#fff;
        border-radius:12px; padding:2px 10px; font-size:.78rem;
    }

    /* ---- blocos de insight ---- */
    .insight-block {
        background:#fff; border-left:4px solid #bd8e27; border-radius:4px;
        padding:14px 18px; margin-bottom:12px;
        box-shadow:0 1px 3px rgba(0,0,0,.07);
    }
    .insight-block h4 { margin:0 0 6px; color:#353330; font-size:.95rem; }
    .insight-block p  { margin:0; font-size:.88rem; color:#444; }

    /* ---- header topo ---- */
    .bussola-header {
        background: linear-gradient(135deg,#353330 60%,#4a4440);
        color:#f0ead8; padding:18px 24px; border-radius:6px;
        margin-bottom:20px; display:flex; align-items:center; gap:16px;
    }
    .bussola-header h1 { color:#bd8e27 !important; margin:0; font-size:1.8rem; }
    .bussola-header p  { margin:0; font-size:.9rem; opacity:.8; }
    </style>
    """, unsafe_allow_html=True)


# ── Header padrão ─────────────────────────────────────────────────────────────
def render_header(subtitulo=""):
    st.markdown(f"""
    <div class="bussola-header">
        <div>
            <h1>🧭 Bússola</h1>
            <p>Ferramenta de jornalismo de dados · {subtitulo}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Detecção de tipo de arquivo ───────────────────────────────────────────────
def detectar_tipo(df: pd.DataFrame | None, nome_arquivo: str) -> str:
    ext = nome_arquivo.rsplit(".", 1)[-1].lower()
    if ext in ("txt", "html", "htm", "pdf"):
        return "textual"
    if df is not None and len(df.columns) > 1:
        return "tabular"
    return "semiestruturado"


# ── Inferência de tipos de coluna ─────────────────────────────────────────────
def inferir_tipos(df: pd.DataFrame) -> dict:
    tipos = {}
    for col in df.columns:
        s = df[col].dropna()
        if s.empty:
            tipos[col] = "vazio"
            continue
        # testa numérico
        tentativa = pd.to_numeric(s.astype(str).str.replace(r"[R$\s.,]", "", regex=True), errors="coerce")
        if tentativa.notna().mean() > 0.7:
            tipos[col] = "numérico"
            continue
        # testa data
        try:
            pd.to_datetime(s.astype(str).head(30), dayfirst=True, errors="raise")
            tipos[col] = "data"
            continue
        except Exception:
            pass
        tipos[col] = "texto"
    return tipos


# ── Exportar DataFrame ────────────────────────────────────────────────────────
def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


# ── Extrações simples de texto ────────────────────────────────────────────────
PADROES = {
    "Datas":    r"\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b|\b\d{4}[\/\-]\d{2}[\/\-]\d{2}\b",
    "Valores":  r"R\$\s?[\d.,]+|[\d.,]+\s?(mil(?:hões?)?|bilhões?)",
    "E-mails":  r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "URLs":     r"https?://[^\s]+",
    "CPF/CNPJ": r"\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}",
    "CEP":      r"\d{5}-\d{3}",
}

UF_LISTA = [
    "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA",
    "MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN",
    "RS","RO","RR","SC","SP","SE","TO",
]

def extrair_padroes(texto: str) -> dict:
    resultado = {}
    for nome, pat in PADROES.items():
        achados = list(set(re.findall(pat, texto, re.IGNORECASE)))
        if achados:
            resultado[nome] = achados
    # UFs
    ufs = [u for u in UF_LISTA if re.search(rf"\b{u}\b", texto)]
    if ufs:
        resultado["UFs"] = list(set(ufs))
    return resultado


# ── Histórico de ações (session_state) ───────────────────────────────────────
def log_acao(msg: str):
    if "historico" not in st.session_state:
        st.session_state["historico"] = []
    st.session_state["historico"].append(msg)


def get_historico() -> list:
    return st.session_state.get("historico", [])
