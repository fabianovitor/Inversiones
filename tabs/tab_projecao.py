# ============================================================
# tabs/tab_projecao.py - Aba Projeção de Renda
# ============================================================

import streamlit as st
import pandas as pd

from utils import formatar_moeda, formatar_pct, formatar_compacto, safe_float
from data_loader import resumo_carteira
from config import BRL_USD


def renderizar(df_principal: pd.DataFrame,
               df_ericsson: pd.DataFrame) -> None:
    """Renderiza a aba Projeção de Renda."""

    st.markdown("## 🎯 Projeção de Renda por Dividendos")

    # ── Dados base ──────────────────────────────────────────────
    resumo_p = resumo_carteira(df_principal)
    resumo_e = resumo_carteira(df_ericsson) if (
        df_ericsson is not None and not df_ericsson.empty
    ) else {}

    renda_mensal_atual = (
        resumo_p.get("renda_mensal", 0)
        + resumo_e.get("renda_mensal", 0)
    )
    patrimonio_total = (
        resumo_p.get("patrimonio_total", 0)
        + resumo_e.get("patrimonio_total", 0)
    )

    # ── Parâmetros do simulador ─────────────────────────────────
    st.markdown("### ⚙️ Parâmetros da Simulação")

    col1, col2, col3 = st.columns(3)

    with col1:
        aporte_mensal = st.number_input(
            "💵 Aporte Mensal (USD)",
            min_value=0.0,
            max_value=100_000.0,
            value=500.0,
            step=100.0,
            format="%.2f",
        )

    with col2:
        anos = st.slider(
            "📅 Horizonte (anos)",
            min_value=1,
            max_value=30,
            value=10,
        )

    with col3:
        crescimento_dividendo = st.number_input(
            "📈 Crescimento anual dividendos (%)",
            min_value=0.0,
            max_value=30.0,
            value=5.0,
            step=0.5,
            format="%.1f",
        )

    col4, col5 = st.columns(2)

    with col4:
        yield_estimado = st.number_input(
            "🏦 Yield médio estimado (%)",
            min_value=0.1,
            max_value=30.0,
            value=6.0,
            step=0.5,
            format="%.1f",
        )

    with col5:
        reinvestir = st.checkbox(
            "🔄 Reinvestir dividendos?",
            value=True,
        )

    st.divider()

    # ── Simulação ───────────────────────────────────────────────
    st.markdown("### 📊 Projeção Ano a Ano")

    tabela = _simular_projecao(
        patrimonio_inicial=patrimonio_total,
        renda_mensal_inicial=renda_mensal_atual,
        aporte_mensal=aporte_mensal,
        anos=anos,
        yield_pct=yield_estimado,
        crescimento_pct=crescimento_dividendo,
        reinvestir=reinvestir,
    )

    st.dataframe(
        tabela,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ano"              : st.column_config.NumberColumn(format="%d"),
            "Patrimônio (USD)" : st.column_config.NumberColumn(format="$%.2f"),
            "Patrimônio (BRL)" : st.column_config.NumberColumn(format="R$ %.2f"),
            "Renda Mensal (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Renda Mensal (BRL)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Renda Anual (USD)": st.column_config.NumberColumn(format="$%.2f"),
            "Aporte Acumulado" : st.column_config.NumberColumn(format="$%.2f"),
            "Yield Real %"     : st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    st.divider()

    # ── Metas de renda ──────────────────────────────────────────
    st.markdown("### 🏆 Metas de Renda Mensal")

    metas_usd = [500, 1_000, 2_000, 3_000, 5_000, 10_000]

    cols = st.columns(len(metas_usd))
    for i, meta in enumerate(metas_usd):
        patrimonio_necessario = (meta * 12) / (yield_estimado / 100)
        faltam = max(0, patrimonio_necessario - patrimonio_total)
        progresso = min(100, patrimonio_total / patrimonio_necessario * 100)

        cols[i].metric(
            f"${meta:,.0f}/mês",
            f"{progresso:.1f}%",
            delta=f"Faltam {formatar_compacto(faltam)}",
            delta_color="off",
        )

    st.divider()

    # ── Resumo atual ────────────────────────────────────────────
    st.markdown("### 📌 Situação Atual")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patrimônio Total",  formatar_compacto(patrimonio_total))
    c2.metric("Renda Mensal USD",  formatar_moeda(renda_mensal_atual))
    c3.metric("Renda Mensal BRL",  f"R$ {renda_mensal_atual * BRL_USD:,.2f}")
    c4.metric(
        "Yield Atual",
        formatar_pct(
            (renda_mensal_atual * 12 / patrimonio_total * 100)
            if patrimonio_total > 0 else 0
        ),
    )


# ============================================================
# FUNÇÃO AUXILIAR: SIMULAÇÃO
# ============================================================

def _simular_projecao(
    patrimonio_inicial: float,
    renda_mensal_inicial: float,
    aporte_mensal: float,
    anos: int,
    yield_pct: float,
    crescimento_pct: float,
    reinvestir: bool,
) -> pd.DataFrame:
    """Simula crescimento do patrimônio e renda ao longo dos anos."""

    registros = []
    patrimonio    = patrimonio_inicial
    renda_mensal  = renda_mensal_inicial
    aporte_acumulado = 0.0

    for ano in range(1, anos + 1):
        # Aportes do ano
        aportes_ano       = aporte_mensal * 12
        aporte_acumulado += aportes_ano

        # Dividendos do ano
        renda_anual = renda_mensal * 12

        # Cresce patrimônio
        if reinvestir:
            patrimonio = patrimonio + aportes_ano + renda_anual
        else:
            patrimonio = patrimonio + aportes_ano

        # Recalcula renda com base no yield e crescimento
        renda_yield    = patrimonio * (yield_pct / 100)
        renda_crescida = renda_anual * (1 + crescimento_pct / 100)
        renda_anual    = max(renda_yield, renda_crescida)
        renda_mensal   = renda_anual / 12

        yield_real = (renda_anual / patrimonio * 100) if patrimonio > 0 else 0

        registros.append({
            "Ano"              : ano,
            "Patrimônio (USD)" : patrimonio,
            "Patrimônio (BRL)" : patrimonio * BRL_USD,
            "Renda Mensal (USD)": renda_mensal,
            "Renda Mensal (BRL)": renda_mensal * BRL_USD,
            "Renda Anual (USD)": renda_anual,
            "Aporte Acumulado" : aporte_acumulado,
            "Yield Real %"     : yield_real,
        })

    return pd.DataFrame(registros)
