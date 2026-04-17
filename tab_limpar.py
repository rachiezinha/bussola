import streamlit as st
import pandas as pd
import numpy as np
from utils.helpers import log_acao, df_to_csv_bytes, df_to_excel_bytes


def render():
    st.subheader("🧹 Limpar e Preparar")

    df_orig = st.session_state.get("df")
    if df_orig is None:
        st.warning("⚠️  Carregue um arquivo na aba **Carregar Dados** primeiro.")
        return

    # Trabalha sempre com cópia editável
    if "df_limpo" not in st.session_state:
        st.session_state["df_limpo"] = df_orig.copy()

    df = st.session_state["df_limpo"]

    # ── Painel de saúde ───────────────────────────────────────────────────────
    st.markdown("#### 🩺 Diagnóstico do arquivo")
    nulos     = df.isnull().sum()
    dup       = df.duplicated().sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Linhas",       f"{len(df):,}".replace(",", "."))
    c2.metric("Duplicados",   int(dup))
    c3.metric("Valores nulos",int(nulos.sum()))

    nulos_df = nulos[nulos > 0].reset_index()
    nulos_df.columns = ["Coluna", "Nulos"]
    nulos_df["% nulos"] = (nulos_df["Nulos"] / len(df) * 100).round(1).astype(str) + "%"
    if not nulos_df.empty:
        with st.expander("🔴 Colunas com valores nulos"):
            st.dataframe(nulos_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── Renomear colunas ──────────────────────────────────────────────────────
    with st.expander("✏️  Renomear colunas"):
        novos_nomes = {}
        cols_grid = st.columns(min(3, len(df.columns)))
        for i, col in enumerate(df.columns):
            novo = cols_grid[i % 3].text_input(col, value=col, key=f"rename_{col}")
            if novo != col:
                novos_nomes[col] = novo
        if st.button("Aplicar renomeação", key="btn_rename") and novos_nomes:
            df = df.rename(columns=novos_nomes)
            st.session_state["df_limpo"] = df
            log_acao(f"Colunas renomeadas: {novos_nomes}")
            st.success(f"✅  {len(novos_nomes)} coluna(s) renomeada(s).")
            st.rerun()

    # ── Remover duplicados ────────────────────────────────────────────────────
    with st.expander("🗑️  Remover duplicados"):
        dup_count = df.duplicated().sum()
        st.write(f"**{dup_count}** linha(s) duplicada(s) encontrada(s).")
        if dup_count > 0:
            colunas_dup = st.multiselect(
                "Considerar apenas estas colunas (vazio = todas)",
                df.columns.tolist(), key="cols_dup"
            )
            if st.button("Remover duplicados", key="btn_dup"):
                subset = colunas_dup if colunas_dup else None
                antes = len(df)
                df = df.drop_duplicates(subset=subset)
                st.session_state["df_limpo"] = df
                log_acao(f"Duplicados removidos: {antes - len(df)} linhas excluídas")
                st.success(f"✅  {antes - len(df)} duplicado(s) removido(s).")
                st.rerun()

    # ── Tratar nulos ──────────────────────────────────────────────────────────
    with st.expander("🔧  Tratar valores nulos"):
        col_nula = st.selectbox("Coluna", df.columns, key="col_nula")
        acao_nulo = st.radio(
            "Ação",
            ["Preencher com valor fixo", "Preencher com média", "Preencher com mediana",
             "Preencher com moda", "Remover linhas com nulo"],
            key="acao_nulo"
        )
        valor_fixo = ""
        if acao_nulo == "Preencher com valor fixo":
            valor_fixo = st.text_input("Valor de preenchimento", key="val_fixo")

        if st.button("Aplicar", key="btn_nulo"):
            nulos_antes = df[col_nula].isnull().sum()
            if acao_nulo == "Preencher com valor fixo":
                df[col_nula] = df[col_nula].fillna(valor_fixo)
            elif acao_nulo == "Preencher com média":
                df[col_nula] = pd.to_numeric(df[col_nula], errors="coerce")
                df[col_nula] = df[col_nula].fillna(df[col_nula].mean())
            elif acao_nulo == "Preencher com mediana":
                df[col_nula] = pd.to_numeric(df[col_nula], errors="coerce")
                df[col_nula] = df[col_nula].fillna(df[col_nula].median())
            elif acao_nulo == "Preencher com moda":
                moda = df[col_nula].mode()
                if not moda.empty:
                    df[col_nula] = df[col_nula].fillna(moda[0])
            elif acao_nulo == "Remover linhas com nulo":
                df = df.dropna(subset=[col_nula])
            st.session_state["df_limpo"] = df
            log_acao(f"Nulos tratados em '{col_nula}': {nulos_antes} → {df[col_nula].isnull().sum()}")
            st.success("✅  Concluído.")
            st.rerun()

    # ── Converter tipos ───────────────────────────────────────────────────────
    with st.expander("🔄  Converter tipo de coluna"):
        col_conv = st.selectbox("Coluna", df.columns, key="col_conv")
        tipo_alvo = st.selectbox(
            "Converter para",
            ["Número (float)", "Número inteiro", "Texto", "Data", "Moeda → número"],
            key="tipo_alvo"
        )
        if st.button("Converter", key="btn_conv"):
            try:
                if tipo_alvo == "Número (float)":
                    df[col_conv] = pd.to_numeric(
                        df[col_conv].astype(str)
                            .str.replace(r"[R$\s]", "", regex=True)
                            .str.replace(".", "", regex=False)
                            .str.replace(",", ".", regex=False),
                        errors="coerce"
                    )
                elif tipo_alvo == "Número inteiro":
                    df[col_conv] = pd.to_numeric(
                        df[col_conv].astype(str)
                            .str.replace(r"[^\d]", "", regex=True),
                        errors="coerce"
                    ).astype("Int64")
                elif tipo_alvo == "Texto":
                    df[col_conv] = df[col_conv].astype(str)
                elif tipo_alvo == "Data":
                    df[col_conv] = pd.to_datetime(df[col_conv], dayfirst=True, errors="coerce")
                elif tipo_alvo == "Moeda → número":
                    df[col_conv] = (
                        df[col_conv].astype(str)
                            .str.replace(r"[R$\s\.]", "", regex=True)
                            .str.replace(",", ".", regex=False)
                    )
                    df[col_conv] = pd.to_numeric(df[col_conv], errors="coerce")
                st.session_state["df_limpo"] = df
                log_acao(f"Coluna '{col_conv}' convertida para {tipo_alvo}")
                st.success(f"✅  Coluna '{col_conv}' convertida.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

    # ── Padronizar texto ──────────────────────────────────────────────────────
    with st.expander("🔡  Padronizar texto"):
        col_txt = st.selectbox("Coluna de texto", df.select_dtypes("object").columns.tolist() or df.columns.tolist(), key="col_txt")
        acoes_txt = st.multiselect(
            "Operações",
            ["MAIÚSCULAS", "minúsculas", "Título", "Remover espaços extras", "Remover acentos"],
            key="acoes_txt"
        )
        if st.button("Aplicar padronização", key="btn_txt") and acoes_txt:
            s = df[col_txt].astype(str)
            if "MAIÚSCULAS" in acoes_txt:   s = s.str.upper()
            if "minúsculas" in acoes_txt:   s = s.str.lower()
            if "Título" in acoes_txt:       s = s.str.title()
            if "Remover espaços extras" in acoes_txt: s = s.str.strip().str.replace(r"\s+", " ", regex=True)
            if "Remover acentos" in acoes_txt:
                import unicodedata
                s = s.apply(lambda x: unicodedata.normalize("NFKD", x)
                               .encode("ascii", "ignore").decode("ascii"))
            df[col_txt] = s
            st.session_state["df_limpo"] = df
            log_acao(f"Padronização de texto em '{col_txt}': {acoes_txt}")
            st.success("✅  Padronização aplicada.")
            st.rerun()

    # ── Visualização atual ────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 👁️  Estado atual da base")
    st.dataframe(df.head(50), use_container_width=True)

    # ── Reset ─────────────────────────────────────────────────────────────────
    if st.button("↩️  Restaurar dados originais", key="btn_reset"):
        st.session_state["df_limpo"] = st.session_state["df"].copy()
        log_acao("Base restaurada para o original")
        st.success("Dados restaurados.")
        st.rerun()

    # ── Exportar ──────────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 💾 Exportar base tratada")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️  CSV", df_to_csv_bytes(df), "bussola_tratado.csv", "text/csv")
    with c2:
        st.download_button("⬇️  Excel", df_to_excel_bytes(df), "bussola_tratado.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
