# ============================================================
# moeda.py  — Módulo de suporte a múltiplas moedas
# Integra com session_state["formatos_colunas"]
# ============================================================

# ── Configuração por moeda ────────────────────────────────────
MOEDAS_CONFIG: dict[str, dict] = {
    "BRL": {"simbolo": "R$", "sep_milhar": ".", "sep_decimal": ",", "pos": "prefix"},
    "USD": {"simbolo": "$",  "sep_milhar": ",", "sep_decimal": ".", "pos": "prefix"},
    "EUR": {"simbolo": "€",  "sep_milhar": ".", "sep_decimal": ",", "pos": "prefix"},
    "GBP": {"simbolo": "£",  "sep_milhar": ",", "sep_decimal": ".", "pos": "prefix"},
}

MOEDAS_SUPORTADAS = list(MOEDAS_CONFIG.keys())


# ── 1. Limpeza: string → float ────────────────────────────────
def limpar_valor_monetario(valor) -> float | None:
    """
    Converte uma string monetária para float.

    Suporta:
      - Prefixos:  R$, $, €, £  (com ou sem espaço)
      - Formato BR:  1.234,56
      - Formato INT: 1,234.56
      - Já é float/int: retorna direto
    """
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    import re
    s = str(valor).strip()

    # Remove símbolos de moeda e espaços extras
    s = re.sub(r"[R$€£\$\s]", "", s)
    s = s.strip()

    if not s:
        return None

    # Detecta formato: BR (vírgula como decimal) vs INT (ponto como decimal)
    tem_ponto   = "." in s
    tem_virgula = "," in s

    if tem_virgula and tem_ponto:
        # Qual aparece por último é o separador decimal
        if s.rfind(",") > s.rfind("."):
            # BR: 1.234,56 → remove pontos, troca vírgula
            s = s.replace(".", "").replace(",", ".")
        else:
            # INT: 1,234.56 → só remove vírgula
            s = s.replace(",", "")
    elif tem_virgula and not tem_ponto:
        # Pode ser BR sem milhar: 1234,56
        s = s.replace(",", ".")
    # elif tem_ponto e not tem_virgula: já está ok (ou é milhar BR sem decimal)

    try:
        return float(s)
    except ValueError:
        return None


# ── 2. Formatação: float → string ────────────────────────────
def formatar_moeda(valor, moeda: str = "BRL") -> str:
    """
    Formata um número como string monetária conforme a moeda.

    Exemplos:
      formatar_moeda(1234.56, "BRL") → "R$ 1.234,56"
      formatar_moeda(1234.56, "USD") → "$1,234.56"
      formatar_moeda(1234.56, "EUR") → "€1.234,56"
      formatar_moeda(1234.56, "GBP") → "£1,234.56"
    """
    if valor is None:
        return ""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)

    cfg = MOEDAS_CONFIG.get(moeda.upper(), MOEDAS_CONFIG["BRL"])

    # Formata com separadores internacionais primeiro
    partes = f"{abs(v):,.2f}".split(".")
    inteiro = partes[0].replace(",", cfg["sep_milhar"])
    decimal = partes[1]
    numero  = f"{inteiro}{cfg['sep_decimal']}{decimal}"

    sinal   = "-" if v < 0 else ""
    simbolo = cfg["simbolo"]

    if moeda.upper() == "BRL":
        return f"{sinal}{simbolo} {numero}"
    else:
        return f"{sinal}{simbolo}{numero}"


# ── 3. Detecta colunas-moeda no session_state ─────────────────
def colunas_moeda(formatos: dict) -> dict[str, str]:
    """
    Retorna {nome_coluna: codigo_moeda} para colunas do tipo "moeda".

    Uso:
        formatos = st.session_state.get("formatos_colunas", {})
        mapa = colunas_moeda(formatos)
    """
    return {
        col: fmt["moeda"]
        for col, fmt in formatos.items()
        if isinstance(fmt, dict) and fmt.get("tipo") == "moeda"
    }


# ── 4. Aplica formatação visual em um DataFrame ───────────────
def aplicar_formatacao_visual(df, formatos: dict):
    """
    Retorna um DataFrame com colunas-moeda formatadas como string
    APENAS para exibição (st.dataframe).

    O DataFrame original permanece com dtype numérico — este retorna
    uma cópia com as colunas de moeda convertidas para string formatada.

    NÃO use o resultado para cálculos ou exportação.
    """
    import pandas as pd

    df_vis = df.copy()
    mapa   = colunas_moeda(formatos)

    for col, moeda in mapa.items():
        if col in df_vis.columns:
            df_vis[col] = df_vis[col].apply(
                lambda v: formatar_moeda(v, moeda) if pd.notna(v) else ""
            )

    return df_vis


# ── 5. Formata um valor escalar (para métricas) ───────────────
def formatar_metrica(valor, col: str, formatos: dict) -> str:
    """
    Retorna o valor formatado se a coluna for do tipo moeda,
    caso contrário retorna a formatação BR padrão.
    """
    fmt = formatos.get(col, {})
    if isinstance(fmt, dict) and fmt.get("tipo") == "moeda":
        return formatar_moeda(valor, fmt.get("moeda", "BRL"))
    # Fallback: número BR sem símbolo
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)
