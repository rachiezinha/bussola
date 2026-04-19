import streamlit as st
import pandas as pd
import numpy as np
from helpers import log_acao, df_to_csv_bytes, df_to_excel_bytes


MOEDAS = {
    "BRL": {"simbolo": "R$", "decimal": ",", "milhar": "."},
    "USD": {"simbolo": "$",  "decimal": ".", "milhar": ","},
    "EUR": {"simbolo": "€",  "decimal": ",", "milhar": "."},
    "GBP": {"simbolo": "£",  "decimal": ".", "milhar": ","},
}


def detectar_formato_moeda(serie):
    s = serie.dropna().astype(str).str.strip()
    if s.empty:
        return "NUMERO"

    amostra = s.head(20)

    if amostra.str.contains(r"R\$", regex=True, na=False).any():
        return "BRL"
    if amostra.str.contains("£", regex=False, na=False).any():
        return "GBP"
    if amostra.str.contains("€", regex=False, na=False).any():
        return "EUR"

    # dólar por símbolo
    if amostra.str.contains(r"\$", regex=True, na=False).any():
        return "USD"

    # sem símbolo: inferência pelo formato
    # 1.234,56 -> BRL/EUR
    # 1,234.56 -> USD/GBP
    padrao_brl = amostra.str.contains(r"^\s*-?\d{1,3}(\.\d{3})*,\d+\s*$", regex=True, na=False).any()
    padrao_usd = amostra.str.contains(r"^\s*-?\d{1,3}(,\d{3})*\.\d+\s*$", regex=True, na=False).any()

    if padrao_brl:
        return "BRL"
    if padrao_usd:
        return "USD"

    tem_virgula = amostra.str.contains(",", regex=False, na=False).any()
    tem_ponto = amostra.str.contains(".", regex=False, na=False).any()

    if tem_virgula and not tem_ponto:
        return "BRL"
    if tem_ponto and not tem_virgula:
        return "USD"

    return "NUMERO"


def moeda_texto_para_numero(serie, moeda="BRL"):
    conf = MOEDAS.get(moeda, MOEDAS["BRL"])
    simbolo = conf["simbolo"]
    decimal = conf["decimal"]
    milhar = conf["milhar"]

    s = serie.astype(str).str.strip()

    # limpa vazios comuns
    s = s.replace(["", "nan", "None", "NaN"], pd.NA)

    # remove símbolo e espaços
    s = (
        s.astype("string")
         .str.replace(simbolo, "", regex=False)
         .str.replace(" ", "", regex=False)
         .str.replace("\xa0", "", regex=False)
    )

    # remove separador de milhar
    if milhar:
        s = s.str.replace(milhar, "", regex=False)

    # troca separador decimal local por ponto
    if decimal != ".":
        s = s.str.replace(decimal, ".", regex=False)

    # remove qualquer lixo residual nas pontas
    s = s.str.strip()

    return pd.to_numeric(s, errors="coerce")


def numero_para_moeda(valor, moeda="BRL"):
    if pd.isna(valor):
        return None

    conf = MOEDAS.get(moeda, MOEDAS["BRL"])
    simbolo = conf["simbolo"]
    decimal = conf["decimal"]
    milhar = conf["milhar"]

    base = f"{float(valor):,.2f}"  # padrão Python: 1,234.56

    if milhar == "." and decimal == ",":
        base = base.replace(",", "X").replace(".", ",").replace("X", ".")
    elif milhar == "," and decimal == ".":
        pass
    else:
        base = base.replace(",", "X").replace(".", decimal).replace("X", milhar)

    return f"{simbolo} {base}"


def normalizar_para_numero_generico(serie):
    formato = detectar_formato_moeda(serie)
    if formato in MOEDAS:
        return moeda_texto_para_numero(serie, moeda=formato)

    # fallback para números "puros" ou colunas meio bagunçadas
    s = serie.astype(str).str.strip()
    s = (
        s.str.replace("R$", "", regex=False)
         .str.replace("$", "", regex=False)
         .str.replace("€", "", regex=False)
         .str.replace("£", "", regex=False)
         .str.replace(" ", "", regex=False)
         .str.replace("\xa0", "", regex=False)
    )

    # se tiver vírgula, assume decimal BR
    tem_virgula = s.str.contains(",", regex=False, na=False)
    s.loc[tem_virgula] = (
        s.loc[tem_virgula]
         .str.replace(".", "", regex=False)
         .str.replace(",", ".", regex=False)
    )

    return pd.to_numeric(s, errors="coerce")


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
    nulos = df.isnull().sum()
    dup = df.duplicated().sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Linhas", f"{len(df):,}".replace(",", "."))
    c2.metric("Duplicados", int(dup))
    c3.metric("Valores nulos", int(nulos.sum()))

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
                df.columns.tolist(),
                key="cols_dup"
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
            [
                "Preencher com valor fixo",
                "Preencher com média",
                "Preencher com mediana",
                "Preencher com moda",
                "Remover linhas com nulo"
            ],
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
                df[col_nula] = normalizar_para_numero_generico(df[col_nula])
                df[col_nula] = df[col_nula].fillna(df[col_nula].mean())

            elif acao_nulo == "Preencher com mediana":
                df[col_nula] = normalizar_para_numero_generico(df[col_nula])
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
with st.expander("🔄  Corrigir tipo da coluna"):
    col_conv = st.selectbox("Coluna", df.columns, key="col_conv")

    tipo_alvo = st.selectbox(
        "Converter para",
        [
            "Número (float)",
            "Número inteiro",
            "Texto",
            "Data",
            "Moeda/texto → número",
        ],
        key="tipo_alvo"
    )

    formato_detectado = detectar_formato_moeda(df[col_conv])

    if formato_detectado != "NUMERO":
        st.info(f"Formato detectado automaticamente: {formato_detectado}")
    else:
        st.caption("Formato detectado: número puro / sem moeda explícita")

    moeda_origem = None

    if tipo_alvo == "Moeda/texto → número":
        moedas_lista = list(MOEDAS.keys())
        indice_origem = moedas_lista.index(formato_detectado) if formato_detectado in moedas_lista else 0
        moeda_origem = st.selectbox(
            "Moeda de origem",
            moedas_lista,
            index=indice_origem,
            key="moeda_origem_conv"
        )

    st.caption(f"Tipo atual: `{df[col_conv].dtype}`")

    if st.button("Converter", key="btn_conv"):
        try:
            tipo_antes = str(df[col_conv].dtype)

            if tipo_alvo == "Número (float)":
                df[col_conv] = normalizar_para_numero_generico(df[col_conv])

            elif tipo_alvo == "Número inteiro":
                df[col_conv] = normalizar_para_numero_generico(df[col_conv]).astype("Int64")

            elif tipo_alvo == "Texto":
                df[col_conv] = df[col_conv].astype(str)

            elif tipo_alvo == "Data":
                df[col_conv] = pd.to_datetime(df[col_conv], dayfirst=True, errors="coerce")

            elif tipo_alvo == "Moeda/texto → número":
                df[col_conv] = moeda_texto_para_numero(df[col_conv], moeda=moeda_origem)

            st.session_state["df_limpo"] = df
            tipo_depois = str(df[col_conv].dtype)

            log_acao(f"Coluna '{col_conv}' convertida para {tipo_alvo}")
            st.success(f"✅ Conversão feita! Tipo: {tipo_antes} → {tipo_depois}")
            st.rerun()

        except Exception as e:
            st.error(f"Erro: {e}")

    # ── Padronizar texto ──────────────────────────────────────────────────────
    with st.expander("🔡  Padronizar texto"):
        colunas_texto = df.select_dtypes(include=["object", "string"]).columns.tolist()
        col_txt = st.selectbox(
            "Coluna de texto",
            colunas_texto or df.columns.tolist(),
            key="col_txt"
        )

        acoes_txt = st.multiselect(
            "Operações",
            ["MAIÚSCULAS", "minúsculas", "Título", "Remover espaços extras", "Remover acentos"],
            key="acoes_txt"
        )

        if st.button("Aplicar padronização", key="btn_txt") and acoes_txt:
            s = df[col_txt].astype(str)

            if "MAIÚSCULAS" in acoes_txt:
                s = s.str.upper()
            if "minúsculas" in acoes_txt:
                s = s.str.lower()
            if "Título" in acoes_txt:
                s = s.str.title()
            if "Remover espaços extras" in acoes_txt:
                s = s.str.strip().str.replace(r"\s+", " ", regex=True)
            if "Remover acentos" in acoes_txt:
                import unicodedata
                s = s.apply(
                    lambda x: unicodedata.normalize("NFKD", x)
                    .encode("ascii", "ignore")
                    .decode("ascii")
                )

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
        st.download_button(
            "⬇️  CSV",
            df_to_csv_bytes(df),
            "bussola_tratado.csv",
            "text/csv"
        )

    with c2:
        st.download_button(
            "⬇️  Excel",
            df_to_excel_bytes(df),
            "bussola_tratado.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
