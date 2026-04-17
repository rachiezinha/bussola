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
    if len(cols_num) >= 2:
        return "Dispersão"
    if cols_num:
        return "Histograma"
    return "Barras"


def render():
    st.subheader("📈 Visualizar")

    df_base = _df_ativo()
    if df_base is None:
        st.warning("⚠️  Carregue um arquivo na aba **Carregar Dados** primeiro.")
        return

    df = df_base.copy()

    cols_num = df.select_dtypes("number").columns.tolist()
    cols_cat = df.select_dtypes("object").columns.tolist()
    cols_dt  = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    cols_todas = df.columns.tolist()

    sugestao = _sugerir_grafico(df)

    gc1, gc2 = st.columns([2,1])
    tipo_grafico = gc1.selectbox(
        "Tipo de gráfico",
        ["Barras","Linha","Dispersão","Histograma","Boxplot","Pizza"],
        index=["Barras","Linha","Dispersão","Histograma","Boxplot","Pizza"].index(sugestao),
        key="tipo_grafico"
    )
    gc2.markdown(f"<br><span style='color:#bd8e27;font-size:.85rem'>💡 Sugestão automática: **{sugestao}**</span>",
                 unsafe_allow_html=True)

    fig = None

    # ── Barras ────────────────────────────────────────────────────────────────
    if tipo_grafico == "Barras":
        c1,c2,c3 = st.columns(3)
        eixo_x  = c1.selectbox("Eixo X (categoria)", cols_cat or cols_todas, key="bar_x")
        eixo_y  = c2.selectbox("Eixo Y (valor)",     cols_num or cols_todas,  key="bar_y")
        agg     = c3.selectbox("Agregação", ["Soma","Contagem","Média"], key="bar_agg")
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
                     color_discrete_sequence=[OURO, MARROM, NEUTRO, "#e8b84b","#a67820"])
        fig.update_traces(marker_color=OURO if not cor else None)
        log_acao(f"Gráfico de barras: {eixo_x} × {eixo_y} ({agg})")

    # ── Linha ─────────────────────────────────────────────────────────────────
    elif tipo_grafico == "Linha":
        eixo_x_opts = cols_dt + cols_cat + cols_num
        c1,c2 = st.columns(2)
        eixo_x = c1.selectbox("Eixo X", eixo_x_opts, key="lin_x")
        eixo_y = c2.selectbox("Eixo Y", cols_num, key="lin_y")
        grp = df.groupby(eixo_x)[eixo_y].sum().reset_index().sort_values(eixo_x)
        fig = px.line(grp, x=eixo_x, y=eixo_y,
                      color_discrete_sequence=[OURO])
        fig.update_traces(line_color=OURO, line_width=2.5)
        log_acao(f"Gráfico de linha: {eixo_x} × {eixo_y}")

    # ── Dispersão ─────────────────────────────────────────────────────────────
    elif tipo_grafico == "Dispersão":
        c1,c2,c3 = st.columns(3)
        eixo_x  = c1.selectbox("Eixo X", cols_num, key="dis_x")
        eixo_y  = c2.selectbox("Eixo Y", cols_num[1:] if len(cols_num)>1 else cols_num, key="dis_y")
        cor_col = c3.selectbox("Cor por", ["—"] + cols_cat, key="dis_cor")
        cor = None if cor_col == "—" else cor_col
        fig = px.scatter(df, x=eixo_x, y=eixo_y, color=cor,
                         color_discrete_sequence=[OURO, MARROM, NEUTRO])
        log_acao(f"Dispersão: {eixo_x} × {eixo_y}")

    # ── Histograma ────────────────────────────────────────────────────────────
    elif tipo_grafico == "Histograma":
        col_hist = st.selectbox("Coluna", cols_num, key="hist_col")
        nbins = st.slider("Número de bins", 5, 100, 20)
        fig = px.histogram(df, x=col_hist, nbins=nbins,
                           color_discrete_sequence=[OURO])
        fig.update_traces(marker_color=OURO, marker_line_color=MARROM, marker_line_width=0.5)
        log_acao(f"Histograma: {col_hist}")

    # ── Boxplot ───────────────────────────────────────────────────────────────
    elif tipo_grafico == "Boxplot":
        c1,c2 = st.columns(2)
        col_bx_y = c1.selectbox("Valor",   cols_num, key="bx_y")
        col_bx_x = c2.selectbox("Grupo",   ["—"] + cols_cat, key="bx_x")
        x_col = None if col_bx_x == "—" else col_bx_x
        fig = px.box(df, x=x_col, y=col_bx_y,
                     color_discrete_sequence=[OURO])
        fig.update_traces(marker_color=OURO, line_color=MARROM)
        log_acao(f"Boxplot: {col_bx_y} por {col_bx_x}")

    # ── Pizza ─────────────────────────────────────────────────────────────────
    elif tipo_grafico == "Pizza":
        c1,c2 = st.columns(2)
        col_pz_names = c1.selectbox("Categoria", cols_cat, key="pz_names")
        col_pz_vals  = c2.selectbox("Valor",     cols_num,  key="pz_vals")
        grp_pz = df.groupby(col_pz_names)[col_pz_vals].sum().reset_index()
        grp_pz = grp_pz.sort_values(col_pz_vals, ascending=False).head(10)
        fig = px.pie(grp_pz, names=col_pz_names, values=col_pz_vals,
                     color_discrete_sequence=[OURO, "#e8b84b", "#a67820", MARROM, NEUTRO,
                                              "#c4b49a","#8a7a70","#6a5e55","#4a3f38","#2a2520"])
        log_acao(f"Pizza: {col_pz_names} × {col_pz_vals}")

    # ── Renderizar ────────────────────────────────────────────────────────────
    if fig:
        titulo = st.text_input("Título do gráfico", key="titulo_graf")
        if titulo:
            fig.update_layout(title=titulo)
        _aplicar_tema(fig)
        st.plotly_chart(fig, use_container_width=True)

        # Exportar imagem
        try:
            img_bytes = fig.to_image(format="png", width=1200, height=600, scale=2)
            st.download_button("⬇️  Exportar gráfico (PNG)", img_bytes,
                               "bussola_grafico.png", "image/png")
        except Exception:
            st.caption("💡 Instale `kaleido` para exportar gráficos: `pip install kaleido`")
