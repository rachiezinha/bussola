import streamlit as st
from utils.helpers import get_historico, log_acao


def render_metodologia():
    st.subheader("📋 Metodologia")

    historico = get_historico()
    df_base   = st.session_state.get("df_limpo") or st.session_state.get("df")
    nome_arq  = st.session_state.get("nome_arquivo", "—")

    st.markdown(f"""
    Esta aba registra automaticamente as transformações realizadas na sessão atual.
    Use-a para documentar a **transparência metodológica** da apuração.
    """)

    # Dados da base
    if df_base is not None:
        st.markdown("#### 📁 Arquivo em uso")
        c1, c2, c3 = st.columns(3)
        c1.metric("Arquivo",  nome_arq)
        c2.metric("Linhas",   f"{len(df_base):,}".replace(",","."))
        c3.metric("Colunas",  len(df_base.columns))

        st.markdown("**Colunas presentes:**")
        st.write(", ".join(df_base.columns.tolist()))

    st.divider()
    st.markdown("#### 🕐 Histórico de ações")
    if historico:
        for i, acao in enumerate(historico, 1):
            st.markdown(f"**{i}.** {acao}")
    else:
        st.info("Nenhuma ação registrada ainda nesta sessão.")

    # Gerar texto de metodologia
    st.divider()
    st.markdown("#### 📝 Gerar texto de metodologia")
    nome_jornalista = st.text_input("Nome do jornalista/analista", key="met_nome")
    data_analise    = st.date_input("Data da análise", key="met_data")
    obs_adicionais  = st.text_area("Observações adicionais", key="met_obs")

    if st.button("Gerar texto", key="btn_met"):
        texto_met = f"""# Metodologia de Análise — Bússola

**Arquivo analisado:** {nome_arq}
**Responsável:** {nome_jornalista}
**Data:** {data_analise}

## Passos realizados
"""
        for i, acao in enumerate(historico, 1):
            texto_met += f"\n{i}. {acao}"
        if obs_adicionais:
            texto_met += f"\n\n## Observações\n{obs_adicionais}"
        texto_met += "\n\n---\n*Gerado pelo Bússola — Ferramenta de jornalismo de dados*"

        st.text_area("Texto gerado", texto_met, height=300, key="met_texto_gerado")
        st.download_button("⬇️  Baixar metodologia (.md)", texto_met.encode("utf-8"),
                           "bussola_metodologia.md", "text/markdown")


def render_notas():
    st.subheader("📓 Bloco de Notas da Pauta")

    st.markdown("""
    Use este espaço para anotar **hipóteses**, **achados**, **dúvidas** e **próximos passos**
    durante a apuração. As notas ficam salvas enquanto a sessão estiver ativa.
    """)

    if "notas_sessao" not in st.session_state:
        st.session_state["notas_sessao"] = {
            "leads":      "",
            "duvidas":    "",
            "checagem":   "",
            "contatos":   "",
            "livre":      "",
        }

    notas = st.session_state["notas_sessao"]

    tabs = st.tabs(["📌 Possíveis leads", "❓ Dúvidas", "✅ Checagem", "📞 Contatos", "📄 Notas livres"])

    with tabs[0]:
        notas["leads"] = st.text_area(
            "Anote possíveis leads e ângulos de pauta",
            value=notas["leads"], height=200, key="nota_leads"
        )

    with tabs[1]:
        notas["duvidas"] = st.text_area(
            "Perguntas em aberto e pontos que precisam ser esclarecidos",
            value=notas["duvidas"], height=200, key="nota_duvidas"
        )

    with tabs[2]:
        notas["checagem"] = st.text_area(
            "Informações que precisam ser verificadas/checadas",
            value=notas["checagem"], height=200, key="nota_checagem"
        )

    with tabs[3]:
        notas["contatos"] = st.text_area(
            "Fontes, contatos e órgãos a acionar",
            value=notas["contatos"], height=200, key="nota_contatos"
        )

    with tabs[4]:
        notas["livre"] = st.text_area(
            "Espaço livre para anotações",
            value=notas["livre"], height=200, key="nota_livre"
        )

    st.session_state["notas_sessao"] = notas

    st.divider()

    # Exportar todas as notas
    notas_export = f"""# Bloco de Notas — Bússola
Arquivo: {st.session_state.get("nome_arquivo", "—")}

## Possíveis leads
{notas["leads"]}

## Dúvidas em aberto
{notas["duvidas"]}

## Checagens pendentes
{notas["checagem"]}

## Contatos
{notas["contatos"]}

## Notas livres
{notas["livre"]}
"""
    st.download_button("⬇️  Exportar notas (.md)", notas_export.encode("utf-8"),
                       "bussola_notas.md", "text/markdown")
    log_acao("Bloco de notas atualizado")
