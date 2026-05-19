# ============================================================
# utils.py - Funções utilitárias compartilhadas
# ============================================================

import pandas as pd


# ============================================================
# MATEMÁTICA SEGURA
# ============================================================

def safe_float(valor, padrao: float = 0.0) -> float:
    """Converte valor para float sem lançar exceção.
    
    Args:
        valor: Qualquer valor
        padrao: Valor padrão se conversão falhar
        
    Returns:
        float ou padrao
    """
    if valor is None or valor == "":
        return padrao
    try:
        resultado = float(valor)
        if pd.isna(resultado):
            return padrao
        return resultado
    except (ValueError, TypeError):
        return padrao


def safe_div(numerador, denominador, padrao: float = 0.0) -> float:
    """Divisão segura, evita ZeroDivisionError.
    
    Args:
        numerador: Numerador
        denominador: Denominador
        padrao: Valor padrão se divisão impossível
        
    Returns:
        Resultado da divisão ou padrao
    """
    try:
        num = float(numerador)
        den = float(denominador)
        if den == 0 or pd.isna(den) or pd.isna(num):
            return padrao
        return num / den
    except (ValueError, TypeError, ZeroDivisionError):
        return padrao


def safe_pct(valor, total, padrao: float = 0.0) -> float:
    """Calcula percentual de forma segura.
    
    Args:
        valor: Parte
        total: Total
        padrao: Valor padrão
        
    Returns:
        Percentual (0-100) ou padrao
    """
    return safe_div(valor, total, padrao) * 100


# ============================================================
# FORMATAÇÃO
# ============================================================

def formatar_moeda(valor: float, simbolo: str = "$") -> str:
    """Formata valor como moeda.
    
    Exemplos:
        1234.5  -> "$1,234.50"
        -500.0  -> "-$500.00"
    """
    try:
        v = float(valor)
        if v < 0:
            return f"-{simbolo}{abs(v):,.2f}"
        return f"{simbolo}{v:,.2f}"
    except (ValueError, TypeError):
        return f"{simbolo}0.00"


def formatar_pct(valor: float, casas: int = 2) -> str:
    """Formata valor como percentual.
    
    Exemplos:
        5.25  -> "5.25%"
        -2.1  -> "-2.10%"
    """
    try:
        return f"{float(valor):.{casas}f}%"
    except (ValueError, TypeError):
        return "0.00%"


def formatar_numero(valor: float, casas: int = 2) -> str:
    """Formata número com separador de milhar.
    
    Exemplos:
        1234567.89  -> "1,234,567.89"
    """
    try:
        return f"{float(valor):,.{casas}f}"
    except (ValueError, TypeError):
        return "0.00"


def formatar_compacto(valor: float, simbolo: str = "$") -> str:
    """Formata valor grande de forma compacta.
    
    Exemplos:
        1_500_000  -> "$1.50M"
        250_000    -> "$250.0K"
        999        -> "$999.00"
    """
    try:
        v = float(valor)
        sinal = "-" if v < 0 else ""
        v = abs(v)

        if v >= 1_000_000:
            return f"{sinal}{simbolo}{v/1_000_000:.2f}M"
        elif v >= 1_000:
            return f"{sinal}{simbolo}{v/1_000:.1f}K"
        else:
            return f"{sinal}{simbolo}{v:.2f}"
    except (ValueError, TypeError):
        return f"{simbolo}0.00"


# ============================================================
# CORES DINÂMICAS
# ============================================================

def cor_valor(valor: float,
              cor_positivo: str = "#00C853",
              cor_negativo: str = "#FF1744",
              cor_neutro: str   = "#9E9E9E") -> str:
    """Retorna cor baseada no sinal do valor.
    
    Args:
        valor: Valor numérico
        cor_positivo: Cor para valores > 0
        cor_negativo: Cor para valores < 0
        cor_neutro: Cor para valor == 0
        
    Returns:
        String de cor hex
    """
    try:
        v = float(valor)
        if v > 0:
            return cor_positivo
        elif v < 0:
            return cor_negativo
        return cor_neutro
    except (ValueError, TypeError):
        return cor_neutro


def emoji_tendencia(valor: float) -> str:
    """Retorna emoji de tendência baseado no valor.
    
    Exemplos:
        5.0  -> "🟢"
        -2.0 -> "🔴"
        0.0  -> "⚪"
    """
    try:
        v = float(valor)
        if v > 0:
            return "🟢"
        elif v < 0:
            return "🔴"
        return "⚪"
    except (ValueError, TypeError):
        return "⚪"


def seta_tendencia(valor: float) -> str:
    """Retorna seta de tendência.
    
    Exemplos:
        5.0  -> "▲"
        -2.0 -> "▼"
        0.0  -> "━"
    """
    try:
        v = float(valor)
        if v > 0:
            return "▲"
        elif v < 0:
            return "▼"
        return "━"
    except (ValueError, TypeError):
        return "━"


# ============================================================
# DATAFRAME HELPERS
# ============================================================

def garantir_coluna(df: pd.DataFrame,
                    coluna: str,
                    valor_padrao=0.0) -> pd.DataFrame:
    """Garante que coluna existe no DataFrame.
    
    Args:
        df: DataFrame
        coluna: Nome da coluna
        valor_padrao: Valor se coluna não existir
        
    Returns:
        DataFrame com coluna garantida
    """
    if coluna not in df.columns:
        df[coluna] = valor_padrao
    return df


def colunas_numericas_para_float(df: pd.DataFrame,
                                  colunas: list) -> pd.DataFrame:
    """Converte lista de colunas para float de forma segura."""
    for col in colunas:
        if col in df.columns:
            df[col] = df[col].apply(safe_float)
    return df
