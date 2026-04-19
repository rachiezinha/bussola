import streamlit as st
import pandas as pd
import plotly.express as px
from helpers import log_acao, OURO, MARROM

# Mapeamento de UFs para siglas
UF_PARA_SIGLA = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPÁ": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARÁ": "CE", "DISTRITO FEDERAL": "DF", "ESPÍRITO SANTO": "ES",
    "GOIÁS": "GO", "MARANHÃO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARÁ": "PA", "PARAÍBA": "PB", "PARANÁ": "PR",
    "PERNAMBUCO": "PE", "PIAUÍ": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDÔNIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC",
    "SÃO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO",
}

# Coordenadas por UF
COORDS_UF = {
    "AC": (-9.0, -70.8), "AL": (-9.6, -36.8), "AP": (1.4, -52.0), "AM": (-3.4, -65.0),
    "BA": (-12.9, -41.7), "CE": (-5.2, -39.5), "DF": (-15.8, -47.8), "ES": (-19.9, -40.5),
    "GO": (-15.8, -49.8), "MA": (-5.1, -45.3), "MT": (-12.7, -51.9), "MS": (-20.7, -54.8),
    "MG": (-18.5, -44.6), "PA": (-3.9, -52.2), "PB": (-7.2, -36.8), "PR": (-24.9, -51.5),
    "PE": (-8.3, -37.9), "PI": (-7.7, -42.7), "RJ": (-22.3, -43.2), "RN": (-5.8, -36.6),
    "RS": (-30.0, -53.2), "RO": (-10.9, -62.0), "RR": (1.9, -61.2), "SC": (-27.4, -50.7),
    "SP": (-22.3, -48.7), "SE": (-10.6, -37.4), "TO": (-10.2, -48.3),
}

_GEOJSON_URL = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"


def _detectar_col_uf(df):
    candidatos = [c for c in df.columns if any(k in c.lower() for k in ("uf", "estado"))]
    return candidatos[0] if candidatos else None


def _normalizar_uf(serie):
    def _norm(v):
        v2 = str(v).strip().upper()
        if v2 in COORDS_UF:
            return v2
        if v2 in UF_PARA_SIGLA:
            return UF_PARA_SIGLA[v2]
        return v2
    return serie.map(_norm)


def render():
    st.subheader("🗺️ Mapas")

    with st.expander("💡 Qual mapa usar?", expanded=False):
        st.markdown("""
| Tipo | Quando usar |
|---|---|
| **Mapa de bolhas (Por Estado)** | Ver rapidamente onde valores são maiores |
| **Choropleth** | Comparar estados com base em cor (ranking) |
        """)

    df = st.session_state.get("df_limpo")
    if df is None:
        df = st.session_state.get("df")

    if df is None or df.empty:
        st.warning("Carregue um dataset primeiro.")
        return

    df = df.copy()

    cols_num = df.select_dtypes("number").columns.tolist()
    cols_cat = df.select_dtypes("object").columns.tolist()

    if not cols_num or not cols_cat:
        st.warning("Dataset precisa de colunas numéricas e categóricas.")
        return

    col_uf_auto = _detectar_col_uf(df)
    idx_uf = cols_cat.index(col_uf_auto) if col_uf_auto in cols_cat else 0

    modo = st.radio("Modo de mapa", ["Por Estado (UF)", "Choropleth"], horizontal=True)

    # 🫧 MAPA DE BOLHAS (AGORA BONITO)
    if modo == "Por Estado (UF)":
        col_uf = st.selectbox("Coluna de UF", cols_cat, index=idx_uf)
        col_val = st.selectbox("Valor", cols_num)
        agg = st.radio("Agregação", ["Soma", "Contagem", "Média"], horizontal=True)

        df["UF"] = _normalizar_uf(df[col_uf])

        if agg == "Soma":
            grp = df.groupby("UF")[col_val].sum().reset_index()
        elif agg == "Contagem":
            grp = df.groupby("UF")[col_val].count().reset_index()
        else:
            grp = df.groupby("UF")[col_val].mean().reset_index()

        grp.columns = ["UF", "Valor"]
        grp["lat"] = grp["UF"].map(lambda u: COORDS_UF.get(u, (None, None))[0])
        grp["lon"] = grp["UF"].map(lambda u: COORDS_UF.get(u, (None, None))[1])
        grp = grp.dropna()

        import requests
        geojson = requests.get(_GEOJSON_URL, timeout=10).json()

        fig = px.choropleth(
            grp,
            geojson=geojson,
            locations="UF",
            featureidkey="properties.sigla",
        )

        fig.update_traces(
            marker_line_color="#2a2a2a",
            marker_line_width=0.6,
            marker_opacity=0
        )

        tamanho = (grp["Valor"] / grp["Valor"].max()) * 35 + 5

        fig.add_scattergeo(
            lon=grp["lon"],
            lat=grp["lat"],
            mode="markers",
            marker=dict(
                size=tamanho,
                color=grp["Valor"],
                colorscale=["#f0ead8", OURO, MARROM],
                showscale=True,
                opacity=0.85,
                line=dict(width=0.8, color="#111")
            ),
            text=grp["UF"] + "<br>" + grp["Valor"].astype(str),
            hoverinfo="text"
        )

        fig.update_geos(fitbounds="locations", visible=False)

        st.plotly_chart(fig, use_container_width=True)
        log_acao("Mapa bolhas bonito")

    # 🗺️ CHOROPLETH
    else:
        col_uf = st.selectbox("Coluna de UF", cols_cat, index=idx_uf)
        col_val = st.selectbox("Valor", cols_num)

        df["UF"] = _normalizar_uf(df[col_uf])
        grp = df.groupby("UF")[col_val].sum().reset_index()

        import requests
        geojson = requests.get(_GEOJSON_URL, timeout=10).json()

        fig = px.choropleth(
            grp,
            geojson=geojson,
            locations="UF",
            featureidkey="properties.sigla",
            color=col_val,
            scope="south america",
            color_continuous_scale=["#f0ead8", OURO, MARROM],
        )

        fig.update_geos(fitbounds="locations", visible=False)

        coords_labels = pd.DataFrame(
            [{"UF": uf, "lat": lat, "lon": lon} for uf, (lat, lon) in COORDS_UF.items()]
        )

        fig.add_scattergeo(
            lon=coords_labels["lon"],
            lat=coords_labels["lat"],
            text=coords_labels["UF"],
            mode="text",
            textfont=dict(size=10, color="black"),
            showlegend=False,
            hoverinfo="skip"
        )

        st.plotly_chart(fig, use_container_width=True)
        log_acao("Choropleth")
