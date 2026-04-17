import streamlit as st
import pandas as pd
import json
import io
from helpers import detectar_tipo, inferir_tipos, log_acao, OURO, MARROM


def ler_arquivo(uploaded, separador=",", aba_excel=0):
    nome = uploaded.name
    ext  = nome.rsplit(".", 1)[-1].lower()
    conteudo = uploaded.read()

    if ext == "csv":
        for enc in ("utf-8-sig", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(io.BytesIO(conteudo), sep=separador, encoding=enc, low_memory=False)
                return df, None, "tabular"
            except Exception:
                continue
        return None, "Não foi possível ler o CSV. Tente outro separador ou encoding.", "erro"

    if ext in ("xlsx", "xls"):
        try:
            xls = pd.ExcelFile(io.BytesIO(conteudo))
            abas = xls.sheet_names
            df = pd.read_excel(io.BytesIO(conteudo), sheet_name=abas[aba_excel])
            return df, abas, "tabular"
        except Exception as e:
            return None, str(e), "erro"

    if ext == "json":
        try:
            obj = json.loads(conteudo)
            if isinstance(obj, list):
                df = pd.DataFrame(obj)
            elif isinstance(obj, dict):
                df = pd.DataFrame([obj]) if not any(isinstance(v, list) for v in obj.values()) \
                     else pd.DataFrame(obj)
            else:
                return None, "JSON em formato não suportado.", "erro"
            return df, None, "tabular"
        except Exception as e:
            return None, str(e), "erro"

    if ext in ("txt", "html", "htm"):
        texto = conteudo.decode("utf-8", errors="replace")
        return None, texto, "textual"

    if ext == "pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
                texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
            return None, texto, "textual"
        except ImportError:
            return None, "pdfplumber não instalado. Instale com: pip install pdfplumber", "erro"
        except Exception as e:
            return None, str(e), "erro"

    return None, "Formato não reconhecido.", "erro"


def render():
    st.subheader("📂 Carregar Dados")
    st.caption("Faça upload de arquivos para começar a explorar.")

    col_up, col_sep = st.columns([3, 1])
    with col_up:
        uploaded = st.file_uploader(
            "Selecione um arquivo",
            type=["csv", "xlsx", "xls", "json", "txt", "html", "htm", "pdf"],
            key="upload_principal"
        )
    with col_sep:
        separador = st.selectbox("Separador CSV", [",", ";", "|", "\\t"], key="sep_csv")
        if separador == "\\t":
            separador = "\t"

    if not uploaded:
        st.info("⬆️  Nenhum arquivo carregado ainda. Envie um CSV, Excel, JSON, TXT, HTML ou PDF.")
        return

    # ---- Excel: escolha de aba ----
    aba_idx = 0
    ext = uploaded.name.rsplit(".", 1)[-1].lower()
    if ext in ("xlsx", "xls"):
        try:
            conteudo_peek = uploaded.read()
            uploaded.seek(0)
            xls_peek = pd.ExcelFile(io.BytesIO(conteudo_peek))
            abas_disp = xls_peek.sheet_names
            if len(abas_disp) > 1:
                aba_sel = st.selectbox("Selecionar aba da planilha", abas_disp)
                aba_idx = abas_disp.index(aba_sel)
        except Exception:
            pass

    uploaded.seek(0)
    resultado, extra, tipo = ler_arquivo(uploaded, separador, aba_idx)

    if tipo == "erro":
        st.error(f"❌ Erro ao ler o arquivo: {extra}")
        return

    # ---- Textual ----
    if tipo == "textual":
        st.success("✅ Arquivo textual carregado.")
        st.session_state["texto_carregado"] = extra
        st.session_state["nome_arquivo"]    = uploaded.name

        st.markdown("#### Raio-X do arquivo")
        c1, c2 = st.columns(2)
        c1.metric("Tipo detectado", "Textual")
        c2.metric("Caracteres", f"{len(extra):,}".replace(",", "."))

        with st.expander("👁️  Prévia do conteúdo (primeiros 3.000 caracteres)"):
            st.text(extra[:3000])

        log_acao(f"Arquivo textual carregado: {uploaded.name}")
        return

    # ---- Tabular ----
    df = resultado
    st.session_state["df"]           = df
    st.session_state["df_original"]  = df.copy()
    st.session_state["nome_arquivo"] = uploaded.name
    if "df_limpo" in st.session_state:
        del st.session_state["df_limpo"]

    tipos_col = inferir_tipos(df)
    tipo_arq  = detectar_tipo(df, uploaded.name)

    st.success(f"✅  **{uploaded.name}** carregado com sucesso.")

    # ---- Raio-X ----
    st.markdown("#### 🔍 Raio-X do arquivo")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Linhas",   f"{len(df):,}".replace(",", "."))
    c2.metric("Colunas",  len(df.columns))
    c3.metric("Tipo",     tipo_arq.capitalize())
    nulos = int(df.isnull().sum().sum())
    c4.metric("Valores nulos", f"{nulos:,}".replace(",", "."))

    # Abas de Excel disponíveis
    if isinstance(extra, list) and len(extra) > 1:
        st.info(f"📋 Planilha com **{len(extra)} abas**: {', '.join(extra)}")

    # ---- Colunas e tipos ----
    st.markdown("#### 📋 Colunas detectadas")
    info_cols = pd.DataFrame({
        "Coluna":        df.columns,
        "Tipo Pandas":   [str(df[c].dtype) for c in df.columns],
        "Tipo inferido": [tipos_col.get(c, "—") for c in df.columns],
        "Nulos":         [int(df[c].isnull().sum()) for c in df.columns],
        "% nulos":       [f"{df[c].isnull().mean()*100:.1f}%" for c in df.columns],
        "Exemplo":       [str(df[c].dropna().iloc[0]) if df[c].dropna().shape[0] > 0 else "—"
                          for c in df.columns],
    })
    st.dataframe(info_cols, use_container_width=True, hide_index=True)

    # ---- Amostra ----
    st.markdown("#### 📄 Amostra dos dados (primeiras 100 linhas)")
    n_linhas = st.slider("Linhas para exibir", 5, min(100, len(df)), 20, key="slider_amostra")
    st.dataframe(df.head(n_linhas), use_container_width=True)

    log_acao(f"Arquivo tabular carregado: {uploaded.name} — {len(df)} linhas, {len(df.columns)} colunas")
