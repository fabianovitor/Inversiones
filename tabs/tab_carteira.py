# ============================================================
# tabs/tab_carteira.py - Aba Carteira Principal
# ============================================================

import streamlit as st
import pandas as pd

from utils import (
    formatar_moeda, formatar_pct, formatar_compacto,
    safe_float, emoji_tendencia
)
from data_loader import resumo_carteira


def renderizar(df_principal: pd.DataFrame) -> None:
    """Renderiza a aba Carteira Principal."""

    st.markdown("## 📊 Carteira Principal")

    if df_principal is None or df_principal.empty:
        st.warning("⚠️ Nenhum ativo na carteira principal.")
        return

    resumo = resumo_carteira(df_principal)

    # ── Métricas ──────────────────────────────────────────
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
        "🏦 YoC Médio",
        formatar_pct(resumo.get("yoc_medio", 0)),
        delta=f"DY: {formatar_pct(resumo.get('dy_medio', 0))}",
        delta_color="off",
    )

    st.divider()

    # ── Tabela de posições ────────────────────────────────
    st.markdown("### 📋 Posições")

    colunas_map = {
        "ticker"       : "Ticker",
        "nome"         : "Nome",
        "categoria"    : "Categoria",
        "qtd"          : "Qtd",
        "pm_usd"       : "PM (USD)",
        "preco_atual"  : "Preço",
        "valor_atual"  : "Valor",
        "lucro_usd"    : "Lucro USD",
        "lucro_pct"    : "Lucro %",
        "yoc"          : "YoC %",
        "dy_atual"     : "DY %",
        "renda_mensal" : "Renda/Mês",
        "peso_pct"     : "Peso %",
    }

    cols_disp = [c for c in colunas_map if c in df_principal.columns]
    df_exib = (
        df_principal[cols_disp]
        .copy()
        .rename(columns={c: colunas_map[c] for c in cols_disp})
    )

    if "Valor" in df_exib.columns:
        df_exib = df_exib.sort_values("Valor", ascending=False)

    st.dataframe(
        df_exib,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PM (USD)"  : st.column_config.NumberColumn(format="$%.2f"),
            "Preço"     : st.column_config.NumberColumn(format="$%.2f"),
            "Valor"     : st.column_config.NumberColumn(format="$%.2f"),
            "Lucro USD" : st.column_config.NumberColumn(format="$%.2f"),
            "Lucro %"   : st.column_config.NumberColumn(format="%.2f%%"),
            "YoC %"     : st.column_config.NumberColumn(format="%.2f%%"),
            "DY %"      : st.column_config.NumberColumn(format="%.2f%%"),
            "Renda/Mês" : st.column_config.NumberColumn(format="$%.2f"),
            "Peso %"    : st.column_config.ProgressColumn(
                              format="%.1f%%", min_value=0, max_value=100
                          ),
        },
    )

    st.caption(f"Total: {len(df_principal)} ativos")

    st.divider()

    # ── Resumo por categoria ──────────────────────────────
    st.markdown("### 🏷️ Por Categoria")

    if "categoria" in df_principal.columns and "valor_atual" in df_principal.columns:
        cat = (
            df_principal
            .groupby("categoria")
            .agg(
                Ativos=("ticker", "count"),
                Valor=("valor_atual", "sum"),
                Renda_Mensal=("renda_mensal", "sum") if "renda_mensal" in df_principal.columns else ("valor_atual", "count"),
            )
            .sort_values("Valor", ascending=False)
            .reset_index()
        )
        cat.columns = ["Categoria", "Ativos", "Valor", "Renda/Mês"]
        total = cat["Valor"].sum()
        cat["Peso %"] = cat["Valor"] / total * 100

        st.dataframe(
            cat,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valor"     : st.column_config.NumberColumn(format="$%.2f"),
                "Renda/Mês" : st.column_config.NumberColumn(format="$%.2f"),
                "Peso %"    : st.column_config.ProgressColumn(
                                  format="%.1f%%", min_value=0, max_value=100
                              ),
            },
        )
