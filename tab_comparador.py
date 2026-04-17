import streamlit as st
import pandas as pd
import difflib
import io
from utils.helpers import log_acao


def _diff_texto(texto_a, texto_b):
    """Retorna diff linha a linha como HTML colorido."""
    linhas_a = texto_a.splitlines()
    linhas_b = texto_b.splitlines()
    diff = list(difflib.unified_diff(linhas_a, linhas_b, lineterm="", n=2))
    blocos = []
    for linha in diff:
        if linha.startswith("+++") or linha.startswith("---") or linha.startswith("@@"):
            blocos.append(f'<div style="color:#888;font-size:.8rem;padding:2px 6px">{linha}</div>')
        elif linha.startswith("+"):
            blocos.append(f'<div style="background:#e6f4ea;border-left:3px solid #5c8a5c;padding:3px 8px;font-family:monospace;font-size:.85rem">{linha[1:]}</div>')
        elif linha.startswith("-"):
            blocos.append(f'<div style="background:#fce8e6;border-left:3px solid #c0392b;padding:3px 8px;font-family:monospace;font-size:.85rem">{linha[1:]}</div>')
        else:
            blocos.append(f'<div style="padding:2px 8px;font-family:monospace;font-size:.85rem;color:#444">{linha}</div>')
    return "".join(blocos) or '<div style="color:green">✅ Nenhuma diferença encontrada.</div>'


def _diff_tabelas(df_a, df_b):
    """Compara dois DataFrames linha a linha."""
    resultados = {
        "linhas_adicionadas": pd.DataFrame(),
        "linhas_removidas":   pd.DataFrame(),
        "linhas_alteradas":   pd.DataFrame(),
    }
    # Linhas em B mas não em A
    merged = df_b.merge(df_a, how="left", indicator=True)
    resultados["linhas_adicionadas"] = df_b[~df_b.apply(tuple, axis=1).isin(df_a.apply(tuple, axis=1))]
    resultados["linhas_removidas"]   = df_a[~df_a.apply(tuple, axis=1).isin(df_b.apply(tuple, axis=1))]

    # Colunas em comum — verificar alterações por índice
    cols_comuns = [c for c in df_a.columns if c in df_b.columns]
    if cols_comuns:
        min_len = min(len(df_a), len(df_b))
        diffs = []
        for i in range(min_len):
            for col in cols_comuns:
                va = df_a.iloc[i][col]
                vb = df_b.iloc[i][col]
                if str(va) != str(vb):
                    diffs.append({"Linha": i+1, "Coluna": col, "Valor A": va, "Valor B": vb})
        resultados["linhas_alteradas"] = pd.DataFrame(diffs)

    return resultados


def _ler_arquivo_comparador(uploaded):
    if uploaded is None:
        return None, None
    conteudo = uploaded.read()
    ext = uploaded.name.rsplit(".",1)[-1].lower()
    if ext == "csv":
        for enc in ("utf-8-sig","latin-1","cp1252"):
            try:
                return pd.read_csv(io.BytesIO(conteudo), encoding=enc), None
            except Exception:
                pass
    if ext in ("xlsx","xls"):
        try:
            return pd.read_excel(io.BytesIO(conteudo)), None
        except Exception as e:
            return None, str(e)
    if ext in ("txt","html","htm"):
        return None, conteudo.decode("utf-8", errors="replace")
    return None, None


def render():
    st.subheader("🔄 Comparador de Versões")

    st.markdown("""
    Compare duas tabelas ou dois textos para identificar o que mudou.
    Útil para comparar **relatórios**, **orçamentos**, **editais** ou qualquer documento em diferentes versões.
    """)

    tipo_comp = st.radio("O que comparar?", ["Tabelas (CSV/Excel)", "Textos (TXT/HTML)"],
                         horizontal=True, key="comp_tipo")

    col_a, col_b = st.columns(2)

    # ── Tabelas ───────────────────────────────────────────────────────────────
    if tipo_comp == "Tabelas (CSV/Excel)":
        with col_a:
            st.markdown("**📄 Arquivo A (versão antiga)**")
            arq_a = st.file_uploader("Arquivo A", type=["csv","xlsx","xls"], key="comp_arq_a")
        with col_b:
            st.markdown("**📄 Arquivo B (versão nova)**")
            arq_b = st.file_uploader("Arquivo B", type=["csv","xlsx","xls"], key="comp_arq_b")

        if not arq_a or not arq_b:
            st.info("⬆️  Carregue os dois arquivos para comparar.")
            return

        df_a, _ = _ler_arquivo_comparador(arq_a)
        df_b, _ = _ler_arquivo_comparador(arq_b)

        if df_a is None or df_b is None:
            st.error("Erro ao ler um dos arquivos.")
            return

        st.divider()
        c1,c2,c3 = st.columns(3)
        c1.metric("Arquivo A — linhas", len(df_a))
        c2.metric("Arquivo B — linhas", len(df_b))
        c3.metric("Diferença",          len(df_b) - len(df_a),
                  delta_color="off" if len(df_b)==len(df_a) else "normal")

        resultado = _diff_tabelas(df_a, df_b)

        with st.expander(f"🟢 Linhas adicionadas ({len(resultado['linhas_adicionadas'])})"):
            if resultado["linhas_adicionadas"].empty:
                st.success("Nenhuma linha nova.")
            else:
                st.dataframe(resultado["linhas_adicionadas"], use_container_width=True)

        with st.expander(f"🔴 Linhas removidas ({len(resultado['linhas_removidas'])})"):
            if resultado["linhas_removidas"].empty:
                st.success("Nenhuma linha removida.")
            else:
                st.dataframe(resultado["linhas_removidas"], use_container_width=True)

        with st.expander(f"🟡 Valores alterados ({len(resultado['linhas_alteradas'])})"):
            if resultado["linhas_alteradas"].empty:
                st.success("Nenhum valor alterado nas linhas comparadas.")
            else:
                st.dataframe(resultado["linhas_alteradas"], use_container_width=True)

        log_acao(f"Comparação de tabelas: A={len(df_a)} linhas, B={len(df_b)} linhas")

    # ── Textos ────────────────────────────────────────────────────────────────
    else:
        with col_a:
            st.markdown("**📄 Texto A (versão antiga)**")
            arq_a = st.file_uploader("Arquivo A", type=["txt","html","htm"], key="comp_txt_a")
            txt_a = st.text_area("…ou cole o texto A", height=150, key="txt_manual_a")
        with col_b:
            st.markdown("**📄 Texto B (versão nova)**")
            arq_b = st.file_uploader("Arquivo B", type=["txt","html","htm"], key="comp_txt_b")
            txt_b = st.text_area("…ou cole o texto B", height=150, key="txt_manual_b")

        texto_a, texto_b = txt_a, txt_b
        if arq_a:
            _, conteudo = _ler_arquivo_comparador(arq_a)
            if conteudo:
                texto_a = conteudo
        if arq_b:
            _, conteudo = _ler_arquivo_comparador(arq_b)
            if conteudo:
                texto_b = conteudo

        if not texto_a or not texto_b:
            st.info("⬆️  Forneça os dois textos para comparar.")
            return

        st.divider()
        c1,c2 = st.columns(2)
        c1.metric("Texto A — caracteres", len(texto_a))
        c2.metric("Texto B — caracteres", len(texto_b))

        st.markdown("#### Diferenças (🟢 adicionado · 🔴 removido)")
        html_diff = _diff_texto(texto_a, texto_b)
        st.markdown(
            f'<div style="border:1px solid #e0dbd4;border-radius:4px;padding:10px;'
            f'max-height:500px;overflow-y:auto;background:#fff">{html_diff}</div>',
            unsafe_allow_html=True
        )
        log_acao("Comparação de textos realizada")
