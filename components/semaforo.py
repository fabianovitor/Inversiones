# ============================================================
# components/semaforo.py - Semáforo colorido para métricas
# ============================================================

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfigSemaforo:
    """Configuração de limites para semáforo."""
    vermelho_abaixo: float   # valor < este = vermelho
    amarelo_abaixo: float    # valor < este = amarelo, >= vermelho = amarelo
    # valor >= amarelo_abaixo = verde


def cor_semaforo(
    valor: float,
    config: ConfigSemaforo,
    inverso: bool = False
) -> str:
    """
    Retorna emoji de semáforo baseado no valor.
    inverso=True: maior é pior (ex: volatilidade, risco)
    """
    if inverso:
        if valor >= config.amarelo_abaixo:
            return "🔴"
        elif valor >= config.vermelho_abaixo:
            return "🟡"
        else:
            return "🟢"
    else:
        if valor < config.vermelho_abaixo:
            return "🔴"
        elif valor < config.amarelo_abaixo:
            return "🟡"
        else:
            return "🟢"


def css_semaforo(
    valor: float,
    config: ConfigSemaforo,
    inverso: bool = False
) -> str:
    """Retorna cor CSS para uso inline."""
    emoji = cor_semaforo(valor, config, inverso)
    mapa = {"🔴": "#e74c3c", "🟡": "#f39c12", "🟢": "#27ae60"}
    return mapa.get(emoji, "#ffffff")


# ── Configurações padrão ──────────────────────────────────────

SEMAFORO_YOC = ConfigSemaforo(
    vermelho_abaixo=2.0,   # YoC < 2% = vermelho
    amarelo_abaixo=4.0,    # YoC < 4% = amarelo
)

SEMAFORO_DY = ConfigSemaforo(
    vermelho_abaixo=1.5,
    amarelo_abaixo=3.0,
)

SEMAFORO_LUCRO_PCT = ConfigSemaforo(
    vermelho_abaixo=-5.0,   # perda > 5% = vermelho
    amarelo_abaixo=0.0,     # perda < 5% = amarelo
)

SEMAFORO_RENDA_MENSAL = ConfigSemaforo(
    vermelho_abaixo=50.0,   # < $50/mês = vermelho
    amarelo_abaixo=200.0,   # < $200/mês = amarelo
)
