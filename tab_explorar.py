import streamlit as st
import pandas as pd
import numpy as np
from utils.helpers import log_acao, df_to_csv_bytes, df_to_excel_bytes


def _df_ativo() -> pd.DataFrame | None:
    return st.session_state.get("df_limpo") or st.session_state.get("df")


def render():
    st.subheader("🔎 Explorar Dados")

    df_base = _df_ativo()
    if df_base is None:
        st.warning("⚠️  Carregue um arquivo na aba **Carregar Dados** primeiro.")
        return

    df = df_base.copy()

    # ── Filtros interativos ───────────────────────────────────────────────────
    with st.expander("🔽  Filtros", expanded=True):
        colunas_filtro = st.multiselect("Filtrar por colunas", df.columns.tolist(), key="cols_filtro")
        for col in colunas_filtro:
            if pd.api.types.is_numeric_dtype(df[col]):
                vmin, vmax = float(df[col].min()), float(df[col].max())
                intervalo = st.slider(f"{col}", vmin, vmax, (vmin, vmax), key=f"flt_{col}")
                df = df[df[col].between(*intervalo)]
            else:
                opts = sorted(df[col].dropna().unique().tolist())
                sel  = st.multiselect(f"{col}", opts, key=f"flt_{col}")
                if sel:
                    df = df[df[col].isin(sel)]

        busca = st.text_input("🔍 Busca textual (em todas as colunas de texto)", key="busca_global")
        if busca:
            mask = pd.Series(False, index=df.index)
            for c in df.select_dtypes("object").columns:
                mask |= df[c].astype(str).str.contains(busca, case=False, na=False)
            df = df[mask]

    st.caption(f"**{len(df):,}** linhas após filtros.".replace(",", "."))
    st.dataframe(df.head(200), use_container_width=True)

    st.divider()

    # ── Estatísticas automáticas ──────────────────────────────────────────────
    st.markdown("#### 📊 Estatísticas automáticas")
    cols_num = df.select_dtypes("number").columns.tolist()
    if cols_num:
        col_stat = st.selectbox("Coluna numérica", cols_num, key="col_stat")
        s = df[col_stat].dropna()
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        c1.metric("Contagem", f"{len(s):,}".replace(",","."))
        c2.metric("Soma",     f"{s.sum():,.2f}".replace(",","X").replace(".",",").replace("X","."))
        c3.metric("Média",    f"{s.mean():,.2f}".replace(",","X").replace(".",",").replace("X","."))
        c4.metric("Mediana",  f"{s.median():,.2f}".replace(",","X").replace(".",",").replace("X","."))
        c5.metric("Mín",      f"{s.min():,.2f}".replace(",","X").replace(".",",").replace("X","."))
        c6.metric("Máx",      f"{s.max():,.2f}".replace(",","X").replace(".",",").replace("X","."))

    st.divider()

    # ── Rankings ──────────────────────────────────────────────────────────────
    st.markdown("#### 🏆 Rankings")
    cols_cat = df.select_dtypes("object").columns.tolist()
    if cols_cat and cols_num:
        rc1, rc2, rc3 = st.columns(3)
        col_rank_cat = rc1.selectbox("Categoria (quem)", cols_cat, key="rank_cat")
        col_rank_val = rc2.selectbox("Valor (quanto)", cols_num,  key="rank_val")
        n_rank       = rc3.selectbox("Top N", [5,10,20,50],        key="rank_n")
        agg_func     = st.radio("Agregação", ["Soma","Contagem","Média"], horizontal=True, key="rank_agg")

        if agg_func == "Soma":
            ranking = df.groupby(col_rank_cat)[col_rank_val].sum().nlargest(n_rank).reset_index()
        elif agg_func == "Contagem":
            ranking = df.groupby(col_rank_cat)[col_rank_val].count().nlargest(n_rank).reset_index()
        else:
            ranking = df.groupby(col_rank_cat)[col_rank_val].mean().nlargest(n_rank).reset_index()

        ranking.columns = ["Categoria", "Valor"]
        ranking.index   = range(1, len(ranking)+1)
        st.dataframe(ranking, use_container_width=True)
        log_acao(f"Ranking gerado: top {n_rank} de '{col_rank_cat}' por {agg_func} de '{col_rank_val}'")

    st.divider()

    # ── Distribuição por categoria ────────────────────────────────────────────
    st.markdown("#### 📂 Distribuição por categoria")
    if cols_cat:
        col_dist = st.selectbox("Coluna categórica", cols_cat, key="col_dist")
        dist = df[col_dist].value_counts().reset_index()
        dist.columns = ["Valor", "Contagem"]
        dist["% do total"] = (dist["Contagem"]/len(df)*100).round(1).astype(str) + "%"
        st.dataframe(dist.head(30), use_container_width=True, hide_index=True)

    st.divider()

    # ── Análise temporal ──────────────────────────────────────────────────────
    cols_data = [c for c in df.columns
                 if pd.api.types.is_datetime64_any_dtype(df[c])
                 or "data" in c.lower() or "date" in c.lower() or "ano" in c.lower()]
    if cols_data:
        st.markdown("#### 📅 Análise temporal")
        col_data = st.selectbox("Coluna de data", cols_data, key="col_data_exp")
        try:
            df[col_data] = pd.to_datetime(df[col_data], dayfirst=True, errors="coerce")
            df_t = df.dropna(subset=[col_data]).copy()
            df_t["ano"] = df_t[col_data].dt.year
            contagem_ano = df_t.groupby("ano").size().reset_index(name="Contagem")
            st.bar_chart(contagem_ano.set_index("ano"))
        except Exception:
            st.info("Não foi possível gerar a análise temporal.")

    st.divider()

    # ── Cruzamento simples ────────────────────────────────────────────────────
    st.markdown("#### ✖️  Cruzamento entre variáveis")
    if cols_cat and cols_num:
        cr1, cr2 = st.columns(2)
        col_cruzA = cr1.selectbox("Variável A (linhas)", cols_cat, key="cruzA")
        col_cruzB = cr2.selectbox("Variável B (colunas)", cols_cat if len(cols_cat)>1 else cols_num, key="cruzB")
        if col_cruzA != col_cruzB:
            pivot = pd.crosstab(df[col_cruzA], df[col_cruzB])
            st.dataframe(pivot, use_container_width=True)
        else:
            st.info("Selecione colunas diferentes para o cruzamento.")

    st.divider()

    # ── Exportar resultado filtrado ───────────────────────────────────────────
    st.markdown("#### 💾 Exportar resultado filtrado")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️  CSV", df_to_csv_bytes(df), "bussola_filtrado.csv", "text/csv")
    with c2:
        st.download_button("⬇️  Excel", df_to_excel_bytes(df), "bussola_filtrado.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
