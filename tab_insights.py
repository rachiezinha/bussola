import streamlit as st
import pandas as pd
import numpy as np
from helpers import log_acao, df_to_csv_bytes


def _formatar_valor(v):
    try:
        return f"{float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    except Exception:
        return str(v)


def render():
    st.subheader("💡 Insights de Pauta")

    df_base = st.session_state.get("df_limpo") or st.session_state.get("df")
    if df_base is None:
        st.warning("⚠️  Carregue um arquivo na aba **Carregar Dados** primeiro.")
        return

    df = df_base.copy()
    nome_arq = st.session_state.get("nome_arquivo", "arquivo")

    cols_num = df.select_dtypes("number").columns.tolist()
    cols_cat = df.select_dtypes("object").columns.tolist()
    nulos = df.isnull().mean()

    insights       = []
    investigar     = []
    limitacoes     = []
    ganchos        = []

    # ── Principais achados ────────────────────────────────────────────────────
    if cols_num:
        for col in cols_num[:3]:
            s = df[col].dropna()
            if s.empty:
                continue
            idx_max = s.idxmax()
            idx_min = s.idxmin()
            total   = s.sum()
            media   = s.mean()

            # Maior valor
            if cols_cat:
                cat_ref = cols_cat[0]
                try:
                    label_max = df.loc[idx_max, cat_ref]
                    label_min = df.loc[idx_min, cat_ref]
                    insights.append(
                        f"**{label_max}** lidera em **{col}** com {_formatar_valor(s.max())}."
                    )
                    insights.append(
                        f"**{label_min}** tem o menor valor em **{col}**: {_formatar_valor(s.min())}."
                    )
                except Exception:
                    pass

            # Concentração
            if cols_cat:
                for cat in cols_cat[:2]:
                    try:
                        grp = df.groupby(cat)[col].sum()
                        if grp.empty or total == 0:
                            continue
                        top1 = grp.idxmax()
                        perc = grp.max() / total * 100
                        if perc > 30:
                            ganchos.append(
                                f"**{top1}** concentra {perc:.1f}% do total de {col}."
                            )
                    except Exception:
                        pass

    # ── Variações ─────────────────────────────────────────────────────────────
    cols_data = [c for c in df.columns if "data" in c.lower() or "ano" in c.lower()
                 or pd.api.types.is_datetime64_any_dtype(df[c])]
    if cols_data and cols_num:
        col_dt = cols_data[0]
        col_vl = cols_num[0]
        try:
            df["__dt__"] = pd.to_datetime(df[col_dt], dayfirst=True, errors="coerce")
            df["__ano__"] = df["__dt__"].dt.year
            anual = df.groupby("__ano__")[col_vl].sum()
            if len(anual) >= 2:
                var = (anual.iloc[-1] - anual.iloc[-2]) / anual.iloc[-2] * 100
                sinal = "crescimento" if var > 0 else "queda"
                insights.append(
                    f"Entre {anual.index[-2]} e {anual.index[-1]}, houve **{sinal} de {abs(var):.1f}%** em {col_vl}."
                )
                if abs(var) > 50:
                    investigar.append(
                        f"Variação de **{var:+.1f}%** em {col_vl} entre {anual.index[-2]} e {anual.index[-1]} é expressiva e merece apuração."
                    )
        except Exception:
            pass

    # ── Categorias mais recorrentes ───────────────────────────────────────────
    for col in cols_cat[:3]:
        vc = df[col].value_counts()
        if vc.empty:
            continue
        top1_val = vc.index[0]
        top1_cnt = vc.iloc[0]
        perc = top1_cnt / len(df) * 100
        insights.append(
            f"**{top1_val}** é o valor mais frequente em **{col}** ({top1_cnt:,} ocorrências, {perc:.1f}% do total).".replace(",",".")
        )
        if perc > 40:
            investigar.append(
                f"**{top1_val}** aparece em {perc:.1f}% dos registros da coluna '{col}' — concentração incomum."
            )

    # ── Limitações ────────────────────────────────────────────────────────────
    cols_nulas_excessivas = nulos[nulos > 0.3]
    if not cols_nulas_excessivas.empty:
        for col, perc in cols_nulas_excessivas.items():
            limitacoes.append(f"A coluna **{col}** tem {perc*100:.1f}% de valores ausentes.")

    if not cols_data:
        limitacoes.append("A base não possui coluna de data identificada, limitando análises temporais.")

    if len(df) < 100:
        limitacoes.append(f"A base tem apenas {len(df)} linhas, o que pode limitar conclusões estatísticas.")

    # ── Renderização ──────────────────────────────────────────────────────────
    st.markdown(f"**Base:** `{nome_arq}` — {len(df):,} linhas · {len(df.columns)} colunas".replace(",","."))
    st.divider()

    st.markdown("### 🔍 Principais achados")
    if insights:
        for item in insights:
            st.markdown(f'<div class="insight-block"><p>{item}</p></div>', unsafe_allow_html=True)
    else:
        st.info("Nenhum achado automático gerado. Verifique se há colunas numéricas e categóricas.")

    st.markdown("### 🕵️ O que investigar")
    if investigar:
        for item in investigar:
            st.markdown(f'<div class="insight-block" style="border-color:#c0392b"><p>⚠️  {item}</p></div>',
                        unsafe_allow_html=True)
    else:
        st.info("Nenhum ponto de investigação automático identificado.")

    st.markdown("### 🗞️ Possíveis ganchos de pauta")
    if ganchos:
        for item in ganchos:
            st.markdown(f'<div class="insight-block" style="border-color:#1a6a9a"><p>📰 {item}</p></div>',
                        unsafe_allow_html=True)
    else:
        st.info("Nenhum gancho automático identificado — explore a aba **Explorar Dados** para mais pistas.")

    st.markdown("### ⚠️ Limitações dos dados")
    if limitacoes:
        for item in limitacoes:
            st.markdown(f'<div class="insight-block" style="border-color:#7a7470"><p>ℹ️  {item}</p></div>',
                        unsafe_allow_html=True)
    else:
        st.success("Nenhuma limitação crítica detectada automaticamente.")

    # Exportar resumo
    st.divider()
    resumo_txt = f"# Insights de Pauta — Bússola\n\nArquivo: {nome_arq}\n\n"
    resumo_txt += "## Principais achados\n" + "\n".join(f"- {i}" for i in insights) + "\n\n"
    resumo_txt += "## O que investigar\n"   + "\n".join(f"- {i}" for i in investigar) + "\n\n"
    resumo_txt += "## Ganchos de pauta\n"   + "\n".join(f"- {i}" for i in ganchos) + "\n\n"
    resumo_txt += "## Limitações\n"         + "\n".join(f"- {i}" for i in limitacoes)

    st.download_button("⬇️  Exportar resumo (Markdown)", resumo_txt.encode("utf-8"),
                       "bussola_insights.md", "text/markdown")
    log_acao("Insights de pauta gerados")
