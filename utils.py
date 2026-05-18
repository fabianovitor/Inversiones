# ============================================================
# utils.py - Funções utilitárias de formatação e estilização
# ============================================================

import pandas as pd


# ============================================================
# FUNÇÕES DE FORMATAÇÃO
# ============================================================

def fmt_usd(valor):
    """Formata valor como USD com 2 casas decimais.
    
    Exemplos:
        fmt_usd(1234.5)  -> '$1,234.50'
        fmt_usd(None)    -> '-'
        fmt_usd(0)       -> '$0.00'
    """
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        return f"${float(valor):,.2f}"
    except (ValueError, TypeError):
        return "-"


def fmt_pct(valor):
    """Formata valor como percentual com 2 casas decimais e sinal.
    
    Exemplos:
        fmt_pct(5.25)   -> '+5.25%'
        fmt_pct(-3.10)  -> '-3.10%'
        fmt_pct(None)   -> '-'
    """
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        return f"{float(valor):+.2f}%"
    except (ValueError, TypeError):
        return "-"


def fmt_pct_dy(valor):
    """Formata Dividend Yield como percentual (sem sinal).
    
    Aceita valores em formato decimal (0.05) ou percentual (5.0).
    
    Exemplos:
        fmt_pct_dy(0.0525)  -> '5.25%'
        fmt_pct_dy(5.25)    -> '5.25%'
        fmt_pct_dy(None)    -> '-'
    """
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        v = float(valor)
        # Se valor for menor que 1, assume que está em decimal (0.05 = 5%)
        if v < 1:
            v = v * 100
        return f"{v:.2f}%"
    except (ValueError, TypeError):
        return "-"


def fmt_qtd(valor):
    """Formata quantidade removendo zeros desnecessários.
    
    Exemplos:
        fmt_qtd(10.0000)   -> '10'
        fmt_qtd(10.5000)   -> '10.5'
        fmt_qtd(10.1234)   -> '10.1234'
        fmt_qtd(None)      -> '-'
    """
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        return f"{float(valor):.4f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return "-"


def fmt_numero(valor, decimais=2):
    """Formata número genérico com separador de milhares.
    
    Exemplos:
        fmt_numero(1234567.89)     -> '1,234,567.89'
        fmt_numero(1234.5, 0)      -> '1,235'
    """
    if pd.isna(valor) or valor is None:
        return "-"
    try:
        return f"{float(valor):,.{decimais}f}"
    except (ValueError, TypeError):
        return "-"


# ============================================================
# FUNÇÕES DE ESTILIZAÇÃO (cores em DataFrames)
# ============================================================

def colorir_lucro(val):
    """Aplica cor verde/vermelho baseado no valor.
    
    - Verde: valores positivos
    - Vermelho: valores negativos
    - Cinza: zero ou nulo
    
    Usado em: Var %, Lucro/Prejuízo, Lucro %
    """
    if pd.isna(val) or val is None:
        return "color: gray"
    try:
        v = float(val)
        if v > 0:
            return "color: #00C853; font-weight: bold"
        elif v < 0:
            return "color: #D50000; font-weight: bold"
        return "color: gray"
    except (ValueError, TypeError):
        return ""


def aplicar_estilo_df(styled_df, colunas_cor):
    """Aplica colorir_lucro nas colunas especificadas.
    
    Compatível com pandas novo (.map) e antigo (.applymap).
    
    Args:
        styled_df: DataFrame.style já formatado
        colunas_cor: lista de nomes de colunas para colorir
    
    Returns:
        DataFrame.style com cores aplicadas
    """
    try:
        # Pandas >= 2.1.0
        return styled_df.map(colorir_lucro, subset=colunas_cor)
    except AttributeError:
        # Pandas < 2.1.0
        return styled_df.applymap(colorir_lucro, subset=colunas_cor)


# ============================================================
# FUNÇÕES DE VALIDAÇÃO
# ============================================================

def safe_float(valor, default=0.0):
    """Converte para float com segurança, retornando default se falhar.
    
    Exemplos:
        safe_float("10.5")    -> 10.5
        safe_float("abc")     -> 0.0
        safe_float(None, -1)  -> -1
    """
    if pd.isna(valor) or valor is None:
        return default
    try:
        return float(valor)
    except (ValueError, TypeError):
        return default


def safe_div(numerador, denominador, default=0.0):
    """Divisão segura, retornando default se denominador for zero/nulo.
    
    Exemplos:
        safe_div(10, 2)     -> 5.0
        safe_div(10, 0)     -> 0.0
        safe_div(10, None)  -> 0.0
    """
    try:
        n = safe_float(numerador)
        d = safe_float(denominador)
        if d == 0:
            return default
        return n / d
    except Exception:
        return default