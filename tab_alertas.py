import streamlit as st
import pandas as pd
import numpy as np
from utils.helpers import log_acao


def render():
    st.subheader("⚠️  Inconsistências e Alertas")

    df_base = st.session_state.get("df_limpo") or st.session_state.get("df")
    if df_base is None:
        st.warning("⚠️  Carregue um arquivo na aba **Carregar Dados** primeiro.")
        return

    df = df_base.copy()
    alertas = []

    st.markdown("""
    O Bússola verifica automaticamente os dados em busca de pontos que **merecem apuração humana**.
    Nenhuma das sinalizações abaixo representa afirmação de erro ou irregularidade.
    """)

    st.divider()

    # ── 1. Duplicados ──────────────────────────────────────────────────────────
    dup_total = df.duplicated().sum()
    with st.expander(f"🔁 Linhas duplicadas ({dup_total})"):
        if dup_total > 0:
            alertas.append(f"{dup_total} linha(s) completamente duplicada(s)")
            st.dataframe(df[df.duplicated(keep=False)].head(50), use_container_width=True)
        else:
            st.success("Nenhuma linha 100% duplicada.")

    # ── 2. Nulos em excesso ───────────────────────────────────────────────────
    nulos_perc = df.isnull().mean()
    colunas_nulas = nulos_perc[nulos_perc > 0.2]
    with st.expander(f"🔴 Colunas com muitos nulos ({len(colunas_nulas)})"):
        if not colunas_nulas.empty:
            for col, perc in colunas_nulas.items():
                alertas.append(f"'{col}' tem {perc*100:.1f}% de valores nulos")
            df_n = pd.DataFrame({"Coluna": colunas_nulas.index,
                                 "% Nulos": (colunas_nulas*100).round(1)})
            st.dataframe(df_n, use_container_width=True, hide_index=True)
        else:
            st.success("Nenhuma coluna com mais de 20% de nulos.")

    # ── 3. Outliers em numéricas ──────────────────────────────────────────────
    cols_num = df.select_dtypes("number").columns.tolist()
    outliers_encontrados = {}
    for col in cols_num:
        s = df[col].dropna()
        if len(s) < 4:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        limite_inf = q1 - 3 * iqr
        limite_sup = q3 + 3 * iqr
        out = df[(df[col] < limite_inf) | (df[col] > limite_sup)]
        if not out.empty:
            outliers_encontrados[col] = out

    with st.expander(f"📊 Outliers extremos ({len(outliers_encontrados)} coluna(s))"):
        if outliers_encontrados:
            for col, out_df in outliers_encontrados.items():
                alertas.append(f"'{col}' tem {len(out_df)} valor(es) muito fora da distribuição")
                st.markdown(f"**{col}** — {len(out_df)} outlier(s):")
                st.dataframe(out_df[[col]].head(20), use_container_width=True)
        else:
            st.success("Nenhum outlier extremo detectado.")

    # ── 4. Valores negativos suspeitos ────────────────────────────────────────
    negativos = {}
    for col in cols_num:
        neg = df[df[col] < 0]
        if not neg.empty:
            negativos[col] = len(neg)
    with st.expander(f"➖ Valores negativos ({len(negativos)} coluna(s))"):
        if negativos:
            for col, n in negativos.items():
                alertas.append(f"'{col}' tem {n} valor(es) negativo(s)")
            st.dataframe(pd.DataFrame({"Coluna":list(negativos.keys()),
                                       "Qtd negativos":list(negativos.values())}),
                         use_container_width=True, hide_index=True)
        else:
            st.success("Nenhum valor negativo encontrado.")

    # ── 5. Colunas com tipos misturados ───────────────────────────────────────
    mistura = []
    for col in df.select_dtypes("object").columns:
        s = df[col].dropna()
        num_mask = pd.to_numeric(s, errors="coerce").notna()
        if num_mask.mean() > 0.1 and num_mask.mean() < 0.9:
            mistura.append({"Coluna": col, "% numérico": f"{num_mask.mean()*100:.1f}%"})
    with st.expander(f"🔀 Colunas com tipos misturados ({len(mistura)})"):
        if mistura:
            for m in mistura:
                alertas.append(f"'{m['Coluna']}' mistura texto e números ({m['% numérico']} numérico)")
            st.dataframe(pd.DataFrame(mistura), use_container_width=True, hide_index=True)
        else:
            st.success("Nenhuma mistura de tipos detectada.")

    # ── 6. Datas impossíveis ──────────────────────────────────────────────────
    cols_data = [c for c in df.columns if "data" in c.lower() or "date" in c.lower()]
    datas_imp = []
    for col in cols_data:
        try:
            parsed = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            futuro = (parsed > pd.Timestamp.now()).sum()
            antigo = (parsed < pd.Timestamp("1900-01-01")).sum()
            if futuro > 0:
                datas_imp.append({"Coluna": col, "Problema": f"{futuro} data(s) no futuro"})
                alertas.append(f"'{col}' tem {futuro} data(s) no futuro")
            if antigo > 0:
                datas_imp.append({"Coluna": col, "Problema": f"{antigo} data(s) antes de 1900"})
        except Exception:
            pass
    with st.expander(f"📅 Datas suspeitas ({len(datas_imp)})"):
        if datas_imp:
            st.dataframe(pd.DataFrame(datas_imp), use_container_width=True, hide_index=True)
        else:
            st.success("Nenhuma data claramente impossível detectada.")

    # ── 7. Concentração suspeita ──────────────────────────────────────────────
    cols_cat = df.select_dtypes("object").columns.tolist()
    concentracao = []
    for col in cols_cat:
        vc = df[col].value_counts(normalize=True)
        if not vc.empty and vc.iloc[0] > 0.5:
            concentracao.append({
                "Coluna": col,
                "Valor dominante": vc.index[0],
                "% do total": f"{vc.iloc[0]*100:.1f}%"
            })
            alertas.append(f"'{col}': valor '{vc.index[0]}' representa {vc.iloc[0]*100:.1f}% dos registros")
    with st.expander(f"🎯 Concentração suspeita ({len(concentracao)} coluna(s))"):
        if concentracao:
            st.dataframe(pd.DataFrame(concentracao), use_container_width=True, hide_index=True)
        else:
            st.success("Nenhuma concentração acima de 50% detectada.")

    # ── Resumo de alertas ─────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📋 Resumo dos alertas")
    if alertas:
        st.warning(f"**{len(alertas)} ponto(s) merecem atenção:**")
        for i, alerta in enumerate(alertas, 1):
            st.markdown(f"<div class='insight-block'><h4>⚠️  #{i}</h4><p>{alerta}</p></div>",
                        unsafe_allow_html=True)
    else:
        st.success("✅  Nenhum ponto crítico detectado automaticamente nos dados.")

    log_acao(f"Análise de inconsistências: {len(alertas)} alerta(s)")
