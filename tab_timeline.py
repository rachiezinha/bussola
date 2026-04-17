import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from helpers import OURO, MARROM, log_acao


def _extrair_datas_texto(texto):
    """Extrai pares (data, trecho) de texto livre."""
    padrao = r"(\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b|\b\d{4}[\/\-]\d{2}[\/\-]\d{2}\b)"
    resultados = []
    for m in re.finditer(padrao, texto):
        inicio = max(0, m.start() - 100)
        fim    = min(len(texto), m.end() + 100)
        trecho = texto[inicio:fim].replace("\n", " ").strip()
        try:
            data = pd.to_datetime(m.group(), dayfirst=True, errors="coerce")
            if pd.notna(data):
                resultados.append({"Data": data, "Descrição": trecho, "Data_str": m.group()})
        except Exception:
            pass
    return resultados


def render():
    st.subheader("📅 Linha do Tempo")

    df_base  = st.session_state.get("df_limpo") or st.session_state.get("df")
    txt_base = st.session_state.get("texto_carregado", "")

    fonte = st.radio(
        "Fonte dos eventos",
        ["Tabela carregada", "Texto carregado", "Inserir manualmente"],
        horizontal=True, key="lt_fonte"
    )

    eventos = []

    # ── De tabela ─────────────────────────────────────────────────────────────
    if fonte == "Tabela carregada":
        if df_base is None:
            st.warning("⚠️  Carregue uma tabela na aba **Carregar Dados**.")
            return
        df = df_base.copy()
        cols_data = [c for c in df.columns
                     if "data" in c.lower() or "date" in c.lower() or "ano" in c.lower()
                     or pd.api.types.is_datetime64_any_dtype(df[c])]
        if not cols_data:
            cols_data = df.columns.tolist()
        c1, c2 = st.columns(2)
        col_data = c1.selectbox("Coluna de data", cols_data, key="lt_col_data")
        col_desc = c2.selectbox("Coluna de descrição", df.columns.tolist(), key="lt_col_desc")

        df["__data_parsed__"] = pd.to_datetime(df[col_data], dayfirst=True, errors="coerce")
        df_valid = df.dropna(subset=["__data_parsed__"]).copy()
        df_valid = df_valid.sort_values("__data_parsed__")

        for _, row in df_valid.iterrows():
            eventos.append({"Data": row["__data_parsed__"], "Descrição": str(row[col_desc])})

    # ── De texto ──────────────────────────────────────────────────────────────
    elif fonte == "Texto carregado":
        if not txt_base:
            st.warning("⚠️  Carregue um arquivo textual na aba **Carregar Dados** ou **Extrair de Texto**.")
            return
        extraidos = _extrair_datas_texto(txt_base)
        if not extraidos:
            st.info("Nenhuma data encontrada no texto.")
            return
        eventos = [{"Data": e["Data"], "Descrição": e["Descrição"]} for e in extraidos]
        st.info(f"🗓️  **{len(eventos)}** data(s) identificada(s) no texto.")

    # ── Manual ────────────────────────────────────────────────────────────────
    else:
        st.markdown("Adicione eventos manualmente:")
        n_eventos = st.number_input("Número de eventos", 1, 20, 3, key="lt_n_ev")
        for i in range(int(n_eventos)):
            with st.expander(f"Evento {i+1}", expanded=(i==0)):
                col_a, col_b = st.columns([1,2])
                data_ev = col_a.date_input(f"Data {i+1}", key=f"lt_data_{i}")
                desc_ev = col_b.text_input(f"Descrição {i+1}", key=f"lt_desc_{i}")
                if data_ev and desc_ev:
                    eventos.append({"Data": pd.Timestamp(data_ev), "Descrição": desc_ev})

    if not eventos:
        st.info("Nenhum evento para exibir.")
        return

    # ── Ordenar e renderizar ──────────────────────────────────────────────────
    df_ev = pd.DataFrame(eventos).sort_values("Data").drop_duplicates(subset=["Data","Descrição"])
    df_ev = df_ev.reset_index(drop=True)

    st.markdown(f"#### 🗓️  {len(df_ev)} evento(s) na linha do tempo")
    st.dataframe(
        df_ev.rename(columns={"Data": "Data", "Descrição": "Descrição"}),
        use_container_width=True, hide_index=True
    )

    # Plotly timeline
    fig = go.Figure()
    datas  = df_ev["Data"].tolist()
    descs  = df_ev["Descrição"].tolist()
    yvals  = [i % 2 for i in range(len(datas))]  # alterna alto/baixo

    for i, (d, desc, y) in enumerate(zip(datas, descs, yvals)):
        # linha vertical do ponto ao eixo
        fig.add_trace(go.Scatter(
            x=[d, d], y=[0, 0.6 if y else -0.6],
            mode="lines", line=dict(color=OURO, width=1.5, dash="dot"),
            showlegend=False, hoverinfo="skip"
        ))
        # ponto
        fig.add_trace(go.Scatter(
            x=[d], y=[0.65 if y else -0.65],
            mode="markers+text",
            marker=dict(size=10, color=OURO, line=dict(color=MARROM, width=1.5)),
            text=[d.strftime("%d/%m/%Y")],
            textposition="top center" if y else "bottom center",
            customdata=[[desc[:120]]],
            hovertemplate="<b>%{text}</b><br>%{customdata[0]}<extra></extra>",
            showlegend=False
        ))

    # Linha do tempo base
    fig.add_shape(type="line", x0=datas[0], x1=datas[-1], y0=0, y1=0,
                  line=dict(color=MARROM, width=2))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, title=""),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[-1.2, 1.2], title=""),
        height=340,
        margin=dict(l=20,r=20,t=30,b=20),
        hovermode="closest"
    )
    st.plotly_chart(fig, use_container_width=True)
    log_acao(f"Linha do tempo gerada: {len(df_ev)} eventos")
