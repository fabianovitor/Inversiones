# ============================================================
# tabs/tab_ericsson.py - Aba Ericsson
# ============================================================

import streamlit as st
import pandas as pd

from utils import (
    formatar_moeda, formatar_pct, formatar_compacto,
    safe_float, emoji_tendencia
)
from data_loader import resumo_carteira
from market_data import enriquecer_ativo, historico_precos
from config import MOSTRAR_ERICSSON


def renderizar(df_ericsson: pd.DataFrame) -> None:
    """Renderiza a aba Ericsson."""

    st.markdown("## 🔵 Carteira Ericsson (ERIC)")

    if not MOSTRAR_ERICSSON:
        st.info("Carteira Ericsson desabilitada no config.py")
        return

    if df_ericsson is None or df_ericsson.empty:
        st.warning("⚠️ Nenhum dado encontrado para a carteira Ericsson.")
        return

    resumo = resumo_carteira(df_ericsson)

    # ── Dados de mercado ao vivo ──────────────────────────────
    with st.spinner("Buscando dados de mercado..."):
        mercado = enriquecer_ativo("ERIC")

    preco_atual   = mercado.get("preco_atual", 0)
    variacao_dia  = mercado.get("variacao_pct", 0)
    div_yield     = mercado.get("div_yield", 0)
    nome_ativo    = mercado.get("nome", "Ericsson")

    # ── Cabeçalho com preço ao vivo ───────────────────────────
    col_info, col_preco = st.columns([2, 1])

    with col_info:
        st.markdown(f"### {nome_ativo}")
        st.caption("Nasdaq: ERIC | Telecomunicações | Suécia")

    with col_preco:
        st.metric(
            "Preço Atual (ERIC)",
            formatar_moeda(preco_atual),
            delta=f"{variacao_dia:+.2f}% hoje {emoji_tendencia(variacao_dia)}",
            delta_color="normal",
        )

    st.divider()

    # ── Métricas da carteira ──────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "💼 Patrimônio",
        formatar_compacto(resumo.get("patrimonio_total", 0)),
    )
    col2.metric(
        "📈 Lucro/Prejuízo",
        formatar_moeda(resumo.get("lucro_total_usd", 0)),
        delta=formatar_pct(resumo.get("lucro_total_pct", 0)),
        delta_color="normal",
    )
    col3.metric(
        "💰 Renda Mensal",
        formatar_moeda(resumo.get("renda_mensal", 0)),
    )
    col4.metric(
        "🏦 DY Atual",
        formatar_pct(div_yield * 100 if div_yield < 1 else div_yield),
    )

    st.divider()

    # ── Tabela de posições ────────────────────────────────────
    st.markdown("### 📋 Posições ERIC")

    colunas_map = {
        "ticker"       : "Ticker",
        "qtd"          : "Qtd",
        "pm_usd"       : "PM (USD)",
        "preco_atual"  : "Preço Atual",
        "valor_atual"  : "Valor",
        "custo_total"  : "Custo",
        "lucro_usd"    : "Lucro USD",
        "lucro_pct"    : "Lucro %",
        "div_anual"    : "Div/Ação",
        "renda_mensal" : "Renda/Mês",
        "yoc"          : "YoC %",
    }

    cols_disp = [c for c in colunas_map if c in df_ericsson.columns]
    df_exib = (
        df_ericsson[cols_disp]
        .copy()
        .rename(columns={c: colunas_map[c] for c in cols_disp})
    )

    st.dataframe(
        df_exib,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PM (USD)"   : st.column_config.NumberColumn(format="$%.2f"),
            "Preço Atual": st.column_config.NumberColumn(format="$%.2f"),
            "Valor"      : st.column_config.NumberColumn(format="$%.2f"),
            "Custo"      : st.column_config.NumberColumn(format="$%.2f"),
            "Lucro USD"  : st.column_config.NumberColumn(format="$%.2f"),
            "Lucro %"    : st.column_config.NumberColumn(format="%.2f%%"),
            "Div/Ação"   : st.column_config.NumberColumn(format="$%.4f"),
            "Renda/Mês"  : st.column_config.NumberColumn(format="$%.2f"),
            "YoC %"      : st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    st.divider()

    # ── Histórico de preços ───────────────────────────────────
    st.markdown("### 📉 Histórico de Preços - ERIC")

    col_per, _ = st.columns([1, 3])
    with col_per:
        periodo = st.selectbox(
            "Período:",
            ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
            index=3,
            key="eric_periodo",
        )

    with st.spinner("Carregando histórico..."):
        df_hist = historico_precos("ERIC", periodo=periodo)

    if df_hist is not None and not df_hist.empty:
        # Garante coluna Date
        if "Date" in df_hist.columns:
            df_hist["Date"] = pd.to_datetime(df_hist["Date"])
            df_hist = df_hist.set_index("Date")

        if "Close" in df_hist.columns:
            st.line_chart(df_hist["Close"], use_container_width=True)

            # Mini resumo do período
            preco_inicio = safe_float(df_hist["Close"].iloc[0])
            preco_fim    = safe_float(df_hist["Close"].iloc[-1])
            variacao_per = ((preco_fim - preco_inicio) / preco_inicio * 100
                            if preco_inicio > 0 else 0)

            c1, c2, c3 = st.columns(3)
            c1.metric("Início do Período", formatar_moeda(preco_inicio))
            c2.metric("Preço Atual",       formatar_moeda(preco_fim))
            c3.metric(
                "Variação no Período",
                formatar_pct(variacao_per),
                delta_color="normal",
            )
    else:
        st.info("Histórico não disponível no momento.")
