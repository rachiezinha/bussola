import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
from helpers import OURO, MARROM, NEUTRO, PLOTLY_TEMPLATE, log_acao

def _df_ativo():
    return st.session_state.get("df_limpo") or st.session_state.get("df")

def _aplicar_tema(fig):
    fig.update_layout(**PLOTLY_TEMPLATE["layout"])
    return fig

def _sugerir_grafico(df):
    cols_num = df.select_dtypes("number").columns.tolist()
    cols_cat = df.select_dtypes("object").columns.tolist()
    cols_dt  = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    if cols_dt and cols_num:
        return "Linha"
    if cols_cat and cols_num:
        return "Barras"
    if cols_num:
        return "Barras"
    return "Barras"

# Captions contextuais por tipo
_CAPTIONS = {
    "Barras":          "📊 Compare valores entre diferentes categorias.",
    "Linha":           "📈 Mostre como um valor evolui ao longo do tempo.",
    "Pizza":           "🥧 Exiba a proporção de cada parte no total.",
    "Área":            "🌊 Como a linha, mas destaca o volume acumulado.",
    "Barra Empilhada": "🗂️ Veja a composição de cada grupo lado a lado.",
    "Ranking":         "🏆 Ordene do maior para o menor valor.",
}

def render():
    st.subheader("📈 Visualizar")

    # ── Guia de uso ────────────────────────────────────────────────────────
    with st.expander("💡 Qual gráfico usar? (guia rápido)", expanded=False):
        st.markdown("""
**Gráficos disponíveis**

| Tipo | Quando usar |
|---|---|
| **Barras** | Comparar valores entre grupos ou categorias |
| **Ranking** | Mostrar os maiores ou menores de uma lista |
| **Linha** | Ver como um valor muda ao longo do tempo |
| **Área** | Evolução no tempo + sensação de volume acumulado |
| **Pizza** | Mostrar proporção — evite muitas categorias (máx. ~6) |
| **Barra Empilhada** | Ver a composição dentro de cada grupo |

**⚠️ Dicas rápidas**
- Dados no tempo → **Linha** ou **Área**
- Comparação entre grupos → **Barras** ou **Ranking**
- Proporção do total → **Pizza** ou **Barra Empilhada**
        """)

    df_base = _df_ativo()
    if df_base is None:
        st.warning("⚠️ Carregue um arquivo na aba **Carregar Dados** primeiro.")
        return

    df = df_base.copy()

    cols_num  = df.select_dtypes("number").columns.tolist()
    cols_cat  = df.select_dtypes("object").columns.tolist()
    cols_dt   = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    cols_todas = df.columns.tolist()

    sugestao = _sugerir_grafico(df)

    TIPOS = ["Barras", "Linha", "Pizza", "Área", "Barra Empilhada", "Ranking"]
    # Garante que a sugestão esteja na lista (fallback para Barras)
    idx_sugestao = TIPOS.index(sugestao) if sugestao in TIPOS else 0

    gc1, gc2 = st.columns([2, 1])
    tipo_grafico = gc1.selectbox(
        "Tipo de gráfico",
        TIPOS,
        index=idx_sugestao,
        key="tipo_grafico",
    )
    gc2.markdown(f"💡 Sugestão automática: **{sugestao}**", unsafe_allow_html=True)

    # Caption contextual
    st.caption(_CAPTIONS.get(tipo_grafico, ""))

    fig = None

    # ── Barras ────────────────────────────────────────────────────────────
    if tipo_grafico == "Barras":
        if not cols_cat and not cols_num:
            st.warning("O arquivo não possui colunas suficientes para este gráfico.")
            return
        c1, c2, c3 = st.columns(3)
        eixo_x = c1.selectbox("Eixo X (categoria)", cols_cat or cols_todas, key="bar_x")
        eixo_y = c2.selectbox("Eixo Y (valor)", cols_num or cols_todas, key="bar_y")
        agg    = c3.selectbox("Agregação", ["Soma", "Contagem", "Média"], key="bar_agg")
        cor_col = st.selectbox("Cor por (opcional)", ["—"] + cols_cat, key="bar_cor")

        if agg == "Soma":
            grp = df.groupby(eixo_x)[eixo_y].sum().reset_index()
        elif agg == "Contagem":
            grp = df.groupby(eixo_x)[eixo_y].count().reset_index()
        else:
            grp = df.groupby(eixo_x)[eixo_y].mean().reset_index()
        grp = grp.sort_values(eixo_y, ascending=False).head(30)

        cor = None if cor_col == "—" else cor_col
        fig = px.bar(grp, x=eixo_x, y=eixo_y, color=cor,
                     color_discrete_sequence=[OURO, MARROM, NEUTRO, "#e8b84b", "#a67820"])
        if not cor:
            fig.update_traces(marker_color=OURO)
        log_acao(f"Gráfico de barras: {eixo_x} × {eixo_y} ({agg})")

    # ── Linha ─────────────────────────────────────────────────────────────
    elif tipo_grafico == "Linha":
        if not cols_num:
            st.warning("O arquivo não possui colunas numéricas para o eixo Y.")
            return
        eixo_x_opts = cols_dt + cols_cat + cols_num
        c1, c2 = st.columns(2)
        eixo_x = c1.selectbox("Eixo X", eixo_x_opts, key="lin_x")
        eixo_y = c2.selectbox("Eixo Y", cols_num, key="lin_y")
        grp = df.groupby(eixo_x)[eixo_y].sum().reset_index().sort_values(eixo_x)
        fig = px.line(grp, x=eixo_x, y=eixo_y,
                      color_discrete_sequence=[OURO])
        fig.update_traces(line_color=OURO, line_width=2.5)
        log_acao(f"Gráfico de linha: {eixo_x} × {eixo_y}")

    # ── Pizza ─────────────────────────────────────────────────────────────
    elif tipo_grafico == "Pizza":
        if not cols_cat or not cols_num:
            st.warning("Necessário ao menos uma coluna de texto (categoria) e uma numérica.")
            return
        c1, c2 = st.columns(2)
        col_pz_names = c1.selectbox("Categoria", cols_cat, key="pz_names")
        col_pz_vals  = c2.selectbox("Valor", cols_num, key="pz_vals")
        grp_pz = df.groupby(col_pz_names)[col_pz_vals].sum().reset_index()
        grp_pz = grp_pz.sort_values(col_pz_vals, ascending=False).head(10)
        n_cat = len(grp_pz)
        if n_cat > 6:
            st.warning(f"⚠️ Há {n_cat} categorias — pizza fica difícil de ler com muitas fatias. Considere **Barras** ou **Ranking**.")
        fig = px.pie(grp_pz, names=col_pz_names, values=col_pz_vals,
                     color_discrete_sequence=[OURO, "#e8b84b", "#a67820", MARROM, NEUTRO,
                                              "#c4b49a", "#8a7a70", "#6a5e55", "#4a3f38", "#2a2520"])
        log_acao(f"Pizza: {col_pz_names} × {col_pz_vals}")

    # ── Área ──────────────────────────────────────────────────────────────
    elif tipo_grafico == "Área":
        if not cols_num:
            st.warning("O arquivo não possui colunas numéricas para o eixo Y.")
            return
        eixo_x_opts = cols_dt + cols_cat + cols_num
        c1, c2 = st.columns(2)
        eixo_x = c1.selectbox("Eixo X (tempo ou categoria)", eixo_x_opts, key="area_x")
        eixo_y = c2.selectbox("Eixo Y (valor)", cols_num, key="area_y")
        grp = df.groupby(eixo_x)[eixo_y].sum().reset_index().sort_values(eixo_x)
        grp[eixo_y] = grp[eixo_y].fillna(0)
        fig = px.area(grp, x=eixo_x, y=eixo_y,
                      color_discrete_sequence=[OURO])
        fig.update_traces(line_color=OURO, fillcolor=f"rgba(212,175,55,0.25)")
        log_acao(f"Gráfico de área: {eixo_x} × {eixo_y}")

    # ── Barra Empilhada ───────────────────────────────────────────────────
    elif tipo_grafico == "Barra Empilhada":
        if len(cols_cat) < 2 or not cols_num:
            st.warning("Necessário ao menos **duas colunas de texto** (categoria + segmentação) e uma numérica.")
            return
        c1, c2, c3 = st.columns(3)
        eixo_x  = c1.selectbox("Eixo X (categoria)", cols_cat, key="stack_x")
        seg_col = c2.selectbox("Segmentação (cor)", [c for c in cols_cat if c != eixo_x], key="stack_seg")
        eixo_y  = c3.selectbox("Valor", cols_num, key="stack_y")

        grp = df.groupby([eixo_x, seg_col])[eixo_y].sum().reset_index()
        grp[eixo_y] = grp[eixo_y].fillna(0)
        fig = px.bar(grp, x=eixo_x, y=eixo_y, color=seg_col, barmode="stack",
                     color_discrete_sequence=[OURO, "#e8b84b", "#a67820", MARROM, NEUTRO,
                                              "#c4b49a", "#8a7a70"])
        log_acao(f"Barra empilhada: {eixo_x} / {seg_col} × {eixo_y}")

    # ── Ranking ───────────────────────────────────────────────────────────
    elif tipo_grafico == "Ranking":
        if not cols_cat or not cols_num:
            st.warning("Necessário ao menos uma coluna de texto (categoria) e uma numérica.")
            return
        c1, c2, c3 = st.columns(3)
        col_cat = c1.selectbox("Categoria", cols_cat, key="rank_cat")
        col_val = c2.selectbox("Valor", cols_num, key="rank_val")
        agg_r   = c3.selectbox("Agregação", ["Soma", "Contagem", "Média"], key="rank_agg")

        top_n = st.slider("Mostrar top N", min_value=3, max_value=50, value=10, key="rank_topn")

        if agg_r == "Soma":
            grp = df.groupby(col_cat)[col_val].sum().reset_index()
        elif agg_r == "Contagem":
            grp = df.groupby(col_cat)[col_val].count().reset_index()
        else:
            grp = df.groupby(col_cat)[col_val].mean().reset_index()

        grp = grp.dropna(subset=[col_val])
        grp = grp.sort_values(col_val, ascending=False).head(top_n)
        grp = grp.sort_values(col_val, ascending=True)  # plotly inverte eixo y

        # Formatar valores no hover
        grp["_label"] = grp[col_val].apply(
            lambda v: f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"
        )

        fig = px.bar(grp, x=col_val, y=col_cat, orientation="h",
                     text="_label",
                     color_discrete_sequence=[OURO])
        fig.update_traces(marker_color=OURO, textposition="outside")
        fig.update_layout(yaxis_title="", xaxis_title=col_val)
        log_acao(f"Ranking: {col_cat} por {col_val} ({agg_r}), top {top_n}")

    # ── Renderizar ────────────────────────────────────────────────────────
    if fig:
        titulo = st.text_input("Título do gráfico", key="titulo_graf")
        if titulo:
            fig.update_layout(title=titulo)
        _aplicar_tema(fig)
        st.plotly_chart(fig, use_container_width=True)

        # Exportar imagem
        try:
            img_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
            st.download_button("⬇️ Exportar gráfico (PNG)", img_bytes,
                               "bussola_grafico.png", "image/png")
        except Exception:
            st.caption("💡 Instale `kaleido` para exportar gráficos: `pip install kaleido`")
