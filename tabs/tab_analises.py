# ============================================================
# tabs/tab_analises.py - Aba Análises
# ============================================================

import streamlit as st
import pandas as pd

from utils import (
    formatar_moeda, formatar_pct, formatar_compacto,
    safe_float, emoji_tendencia
)
from data_loader import resumo_carteira
from config import BRL_USD


def renderizar(df_principal: pd.DataFrame,
               df_ericsson: pd.DataFrame) -> None:
    """Renderiza a aba Análises."""

    st.markdown("## 🔍 Análises do Portfólio")

    if df_principal is None or df_principal.empty:
        st.warning("⚠️ Sem dados para análise.")
        return

    # Combina as duas carteiras para análise geral
    frames = [df_principal]
    if df_ericsson is not None and not df_ericsson.empty:
        frames.append(df_ericsson)
    df_total = pd.concat(frames, ignore_index=True)

    resumo_p = resumo_carteira(df_principal)
    resumo_e = resumo_carteira(df_ericsson) if (
        df_ericsson is not None and not df_ericsson.empty
    ) else {}

    # ── Subtabs ────────────────────────────────────────────────────
    subtab1, subtab2, subtab3, subtab4 = st.tabs([
        "📊 Diversificação",
        "🏆 Rankings",
        "⚖️ Alocação vs Objetivo",
        "📋 Resumo Completo",
    ])

    with subtab1:
        _analise_diversificacao(df_total)

    with subtab2:
        _analise_rankings(df_total)

    with subtab3:
        _analise_alocacao(df_principal)

    with subtab4:
        _resumo_completo(resumo_p, resumo_e)


# ============================================================
# SUBTAB 1: DIVERSIFICAÇÃO
# ============================================================

def _analise_diversificacao(df: pd.DataFrame) -> None:
    """Análise de diversificação da carteira."""

    st.markdown("### 📊 Diversificação da Carteira")

    if df.empty:
        st.info("Sem dados disponíveis.")
        return

    col1, col2 = st.columns(2)

    # --- Por Categoria ---
    with col1:
        st.markdown("#### 🏷️ Por Categoria")
        if "categoria" in df.columns and "valor_atual" in df.columns:
            cat = (
                df.groupby("categoria")["valor_atual"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            cat.columns = ["Categoria", "Valor"]
            total = cat["Valor"].sum()
            cat["Peso %"] = cat["Valor"] / total * 100

            st.dataframe(
                cat,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor": st.column_config.NumberColumn(format="$%.2f"),
                    "Peso %": st.column_config.ProgressColumn(
                        format="%.1f%%", min_value=0, max_value=100
                    ),
                },
            )

            # Concentração
            top1 = cat["Peso %"].iloc[0] if len(cat) > 0 else 0
            top3 = cat["Peso %"].head(3).sum()
            st.caption(
                f"Top 1 categoria: **{top1:.1f}%** | "
                f"Top 3 categorias: **{top3:.1f}%**"
            )
        else:
            st.info("Coluna 'categoria' não encontrada.")

    # --- Por Ativo (concentração) ---
    with col2:
        st.markdown("#### 📌 Concentração por Ativo")
        if "ticker" in df.columns and "valor_atual" in df.columns:
            ativos = (
                df.groupby("ticker")["valor_atual"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            ativos.columns = ["Ticker", "Valor"]
            total = ativos["Valor"].sum()
            ativos["Peso %"] = ativos["Valor"] / total * 100

            st.dataframe(
                ativos,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor": st.column_config.NumberColumn(format="$%.2f"),
                    "Peso %": st.column_config.ProgressColumn(
                        format="%.1f%%", min_value=0, max_value=100
                    ),
                },
            )

            top1_a = ativos["Peso %"].iloc[0] if len(ativos) > 0 else 0
            top5_a = ativos["Peso %"].head(5).sum()
            st.caption(
                f"Top 1 ativo: **{top1_a:.1f}%** | "
                f"Top 5 ativos: **{top5_a:.1f}%**"
            )
        else:
            st.info("Dados de ativos não encontrados.")

    st.divider()

    # --- Métricas de diversificação ---
    st.markdown("#### 🎯 Indicadores de Diversificação")

    num_ativos     = df["ticker"].nunique() if "ticker" in df.columns else 0
    num_categorias = df["categoria"].nunique() if "categoria" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de Ativos",     num_ativos)
    c2.metric("Categorias",          num_categorias)

    if "valor_atual" in df.columns and num_ativos > 0:
        total_val  = df["valor_atual"].sum()
        media_ativo = total_val / num_ativos
        maior_pos   = df.groupby("ticker")["valor_atual"].sum().max()
        conc_maior  = maior_pos / total_val * 100 if total_val > 0 else 0

        c3.metric("Média por Ativo",   formatar_moeda(media_ativo))
        c4.metric("Maior Concentração", formatar_pct(conc_maior))


# ============================================================
# SUBTAB 2: RANKINGS
# ============================================================

def _analise_rankings(df: pd.DataFrame) -> None:
    """Rankings de ativos por diferentes métricas."""

    st.markdown("### 🏆 Rankings de Ativos")

    if df.empty:
        st.info("Sem dados disponíveis.")
        return

    col1, col2 = st.columns(2)

    # --- Top 5 por valor ---
    with col1:
        st.markdown("#### 💰 Top 5 por Valor")
        if "ticker" in df.columns and "valor_atual" in df.columns:
            top_valor = (
                df[["ticker", "nome", "valor_atual"]]
                .sort_values("valor_atual", ascending=False)
                .head(5)
                .reset_index(drop=True)
            )
            top_valor.index += 1
            st.dataframe(
                top_valor,
                use_container_width=True,
                column_config={
                    "valor_atual": st.column_config.NumberColumn(
                        "Valor", format="$%.2f"
                    ),
                },
            )

    # --- Top 5 por YoC ---
    with col2:
        st.markdown("#### 🏦 Top 5 por YoC %")
        if "ticker" in df.columns and "yoc" in df.columns:
            top_yoc = (
                df[["ticker", "nome", "yoc", "renda_mensal"]]
                .sort_values("yoc", ascending=False)
                .head(5)
                .reset_index(drop=True)
            ) if "renda_mensal" in df.
