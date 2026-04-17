import streamlit as st
import pandas as pd
import plotly.express as px
from helpers import log_acao, OURO, MARROM

# Mapeamento de UFs para códigos IBGE (para choropleth)
UF_PARA_SIGLA = {
    "ACRE": "AC","ALAGOAS": "AL","AMAPÁ": "AP","AMAZONAS": "AM",
    "BAHIA": "BA","CEARÁ": "CE","DISTRITO FEDERAL": "DF","ESPÍRITO SANTO": "ES",
    "GOIÁS": "GO","MARANHÃO": "MA","MATO GROSSO": "MT","MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG","PARÁ": "PA","PARAÍBA": "PB","PARANÁ": "PR",
    "PERNAMBUCO": "PE","PIAUÍ": "PI","RIO DE JANEIRO": "RJ","RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS","RONDÔNIA": "RO","RORAIMA": "RR","SANTA CATARINA": "SC",
    "SÃO PAULO": "SP","SERGIPE": "SE","TOCANTINS": "TO",
}

# Coordenadas aproximadas por UF (lat/lon)
COORDS_UF = {
    "AC":(-9.0,-70.8),"AL":(-9.6,-36.8),"AP":(1.4,-52.0),"AM":(-3.4,-65.0),
    "BA":(-12.9,-41.7),"CE":(-5.2,-39.5),"DF":(-15.8,-47.8),"ES":(-19.9,-40.5),
    "GO":(-15.8,-49.8),"MA":(-5.1,-45.3),"MT":(-12.7,-51.9),"MS":(-20.7,-54.8),
    "MG":(-18.5,-44.6),"PA":(-3.9,-52.2),"PB":(-7.2,-36.8),"PR":(-24.9,-51.5),
    "PE":(-8.3,-37.9),"PI":(-7.7,-42.7),"RJ":(-22.3,-43.2),"RN":(-5.8,-36.6),
    "RS":(-30.0,-53.2),"RO":(-10.9,-62.0),"RR":(1.9,-61.2),"SC":(-27.4,-50.7),
    "SP":(-22.3,-48.7),"SE":(-10.6,-37.4),"TO":(-10.2,-48.3),
}


def _detectar_col_uf(df):
    candidatos = [c for c in df.columns
                  if any(k in c.lower() for k in ("uf","estado","sigla","estado_uf"))]
    return candidatos[0] if candidatos else None


def _normalizar_uf(serie):
    """Tenta normalizar para sigla de 2 letras."""
    def _norm(v):
        v2 = str(v).strip().upper()
        if v2 in COORDS_UF:
            return v2
        if v2 in UF_PARA_SIGLA:
            return UF_PARA_SIGLA[v2]
        return v2
    return serie.map(_norm)


def render():
    st.subheader("🗺️  Mapas")

    df_base = st.session_state.get("df_limpo") or st.session_state.get("df")
    if df_base is None:
        st.warning("⚠️  Carregue um arquivo na aba **Carregar Dados** primeiro.")
        return

    df = df_base.copy()

    st.markdown("""
    Visualize seus dados no mapa por **estado** ou por **coordenadas geográficas** (lat/lon).
    O sistema detecta automaticamente colunas de UF, latitude e longitude.
    """)

    cols_num = df.select_dtypes("number").columns.tolist()
    cols_cat = df.select_dtypes("object").columns.tolist()

    modo = st.radio("Modo de mapa", ["Por Estado (UF)", "Por Coordenadas (lat/lon)"],
                    horizontal=True, key="modo_mapa")

    # ── Por Estado ────────────────────────────────────────────────────────────
    if modo == "Por Estado (UF)":
        col_uf_auto = _detectar_col_uf(df)
        col_uf = st.selectbox(
            "Coluna de UF/Estado",
            cols_cat,
            index=cols_cat.index(col_uf_auto) if col_uf_auto and col_uf_auto in cols_cat else 0,
            key="mapa_col_uf"
        )
        col_val = st.selectbox("Coluna de valor (métrica)", cols_num, key="mapa_col_val")
        agg_mapa = st.radio("Agregação", ["Soma","Contagem","Média"], horizontal=True, key="mapa_agg")

        df["__uf_norm__"] = _normalizar_uf(df[col_uf])

        if agg_mapa == "Soma":
            grp = df.groupby("__uf_norm__")[col_val].sum().reset_index()
        elif agg_mapa == "Contagem":
            grp = df.groupby("__uf_norm__")[col_val].count().reset_index()
        else:
            grp = df.groupby("__uf_norm__")[col_val].mean().reset_index()
        grp.columns = ["UF", "Valor"]

        # Adiciona coordenadas
        grp["lat"] = grp["UF"].map(lambda u: COORDS_UF.get(u, (None,None))[0])
        grp["lon"] = grp["UF"].map(lambda u: COORDS_UF.get(u, (None,None))[1])
        grp_geo = grp.dropna(subset=["lat","lon"])

        if grp_geo.empty:
            st.warning("Não foi possível mapear as UFs encontradas. Verifique se a coluna contém siglas (SP, RJ...) ou nomes completos.")
            st.dataframe(grp, use_container_width=True, hide_index=True)
            return

        fig = px.scatter_geo(
            grp_geo, lat="lat", lon="lon",
            size="Valor", color="Valor", hover_name="UF",
            hover_data={"Valor": True, "lat": False, "lon": False},
            color_continuous_scale=["#f0ead8", OURO, MARROM],
            size_max=50,
            scope="south america",
            title=f"{agg_mapa} de {col_val} por Estado"
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            geo=dict(bgcolor="rgba(0,0,0,0)", showland=True, landcolor="#ede9e0",
                     showocean=True, oceancolor="#d6eaf8",
                     showcoastlines=True, coastlinecolor="#aaa",
                     showcountries=True, countrycolor="#ccc",
                     showsubunits=True, subunitcolor="#bbb"),
            coloraxis_colorbar=dict(title=col_val)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Tabela por estado")
        grp_show = grp.drop(columns=["lat","lon"]).sort_values("Valor", ascending=False)
        grp_show.index = range(1, len(grp_show)+1)
        st.dataframe(grp_show, use_container_width=True)

        log_acao(f"Mapa por estado: {col_val} ({agg_mapa})")

    # ── Por Coordenadas ───────────────────────────────────────────────────────
    else:
        candidatos_lat = [c for c in df.columns if "lat" in c.lower()]
        candidatos_lon = [c for c in df.columns if any(k in c.lower() for k in ("lon","lng"))]

        col_lat = st.selectbox("Coluna de Latitude",  cols_num,
                               index=cols_num.index(candidatos_lat[0]) if candidatos_lat else 0,
                               key="mapa_lat")
        col_lon = st.selectbox("Coluna de Longitude", cols_num,
                               index=cols_num.index(candidatos_lon[0]) if candidatos_lon else min(1,len(cols_num)-1),
                               key="mapa_lon")
        col_label = st.selectbox("Rótulo (hover)", ["—"] + cols_cat, key="mapa_label")
        col_tam   = st.selectbox("Tamanho do ponto", ["—"] + cols_num,  key="mapa_tam")

        df_geo = df.dropna(subset=[col_lat, col_lon])
        label_col = None if col_label == "—" else col_label
        size_col  = None if col_tam   == "—" else col_tam

        fig = px.scatter_mapbox(
            df_geo, lat=col_lat, lon=col_lon,
            hover_name=label_col, size=size_col,
            color_discrete_sequence=[OURO],
            zoom=4, height=500,
            mapbox_style="carto-positron"
        )
        fig.update_traces(marker=dict(color=OURO, opacity=0.75))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)
        log_acao(f"Mapa por coordenadas: {col_lat} / {col_lon}")
