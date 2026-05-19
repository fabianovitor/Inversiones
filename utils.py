# ============================================================
# utils.py - Funções utilitárias
# ============================================================


def safe_float(value) -> float:
    """Converte valor para float com segurança."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def formatar_moeda(valor, simbolo: str = "USD") -> str:
    """Formata valor monetário em USD."""
    try:
        v = float(valor)
        if v >= 0:
            return f"${v:,.2f}"
        else:
            return f"-${abs(v):,.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def formatar_pct(valor) -> str:
    """Formata percentual."""
    try:
        v = float(valor)
        return f"{v:.2f}%"
    except (ValueError, TypeError):
        return "0.00%"


def formatar_compacto(valor) -> str:
    """Formata valor compacto (K, M, B)."""
    try:
        v = float(valor)
        negativo = v < 0
        v = abs(v)
        if v >= 1_000_000_000:
            resultado = f"${v / 1_000_000_000:.2f}B"
        elif v >= 1_000_000:
            resultado = f"${v / 1_000_000:.2f}M"
        elif v >= 1_000:
            resultado = f"${v / 1_000:.1f}K"
        else:
            resultado = f"${v:.2f}"
        return f"-{resultado}" if negativo else resultado
    except (ValueError, TypeError):
        return "$0.00"
