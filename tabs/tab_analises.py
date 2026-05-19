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
            ) if "renda_mensal" in df.columns else (
                df[["ticker", "nome", "yoc"]]
                .sort_values("yoc", ascending=False)
                .head(5)
                .reset_index(drop=True)
            )
            top_yoc.index += 1
            st.dataframe(
                top_yoc,
                use_container_width=True,
                column_config={
                    "yoc": st.column_config.NumberColumn(
                        "YoC %", format="%.2f%%"
                    ),
                    "renda_mensal": st.column_config.NumberColumn(
                        "Renda/Mês", format="$%.2f"
                    ),
                },
            )

    st.divider()

    col3, col4 = st.columns(2)

    # --- Top 5 por lucro % ---
    with col3:
        st.markdown("#### 📈 Top 5 Maior Lucro %")
        if "ticker" in df.columns and "lucro_pct" in df.columns:
            top_lucro = (
                df[["ticker", "nome", "lucro_pct", "lucro_usd"]]
                .sort_values("lucro_pct", ascending=False)
                .head(5)
                .reset_index(drop=True)
            ) if "lucro_usd" in df.columns else (
                df[["ticker", "nome", "lucro_pct"]]
                .sort_values("lucro_pct", ascending=False)
                .head(5)
                .reset_index(drop=True)
            )
            top_lucro.index += 1
            st.dataframe(
                top_lucro,
                use_container_width=True,
                column_config={
                    "lucro_pct": st.column_config.NumberColumn(
                        "Lucro %", format="%.2f%%"
                    ),
                    "lucro_usd": st.column_config.NumberColumn(
                        "Lucro USD", format="$%.2f"
                    ),
                },
            )

    # --- Bottom 5 por lucro % ---
    with col4:
        st.markdown("#### 📉 Top 5 Menor Lucro %")
        if "ticker" in df.columns and "lucro_pct" in df.columns:
            bottom_lucro = (
                df[["ticker", "nome", "lucro_pct", "lucro_usd"]]
                .sort_values("lucro_pct", ascending=True)
                .head(5)
                .reset_index(drop=True)
            ) if "lucro_usd" in df.columns else (
                df[["ticker", "nome", "lucro_pct"]]
                .sort_values("lucro_pct", ascending=True)
                .head(5)
                .reset_index(drop=True)
            )
            bottom_lucro.index += 1
            st.dataframe(
                bottom_lucro,
                use_container_width=True,
                column_config={
                    "lucro_pct": st.column_config.NumberColumn(
                        "Lucro %", format="%.2f%%"
                    ),
                    "lucro_usd": st.column_config.NumberColumn(
                        "Lucro USD", format="$%.2f"
                    ),
                },
            )

    st.divider()

    # --- Top por renda mensal ---
    st.markdown("#### 💸 Top 10 por Renda Mensal")
    if "ticker" in df.columns and "renda_mensal" in df.columns:
        top_renda = (
            df[["ticker", "nome", "qtd", "renda_mensal", "yoc"]]
            .sort_values("renda_mensal", ascending=False)
            .head(10)
            .reset_index(drop=True)
        ) if "qtd" in df.columns and "yoc" in df.columns else (
            df[["ticker", "nome", "renda_mensal"]]
            .sort_values("renda_mensal", ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        top_renda.index += 1
        st.dataframe(
            top_renda,
            use_container_width=True,
            column_config={
                "renda_mensal": st.column_config.NumberColumn(
                    "Renda/Mês", format="$%.2f"
                ),
                "yoc": st.column_config.NumberColumn(
                    "YoC %", format="%.2f%%"
                ),
            },
        )


# ============================================================
# SUBTAB 3: ALOCAÇÃO VS OBJETIVO
# ============================================================

def _analise_alocacao(df: pd.DataFrame) -> None:
    """Análise de alocação atual versus objetivo."""

    st.markdown("### ⚖️ Alocação Atual vs Objetivo")

    if df.empty:
        st.info("Sem dados disponíveis.")
        return

    colunas_map = {
        "ticker"       : "Ticker",
        "nome"         : "Nome",
        "categoria"    : "Categoria",
        "valor_atual"  : "Valor Atual",
        "peso_pct"     : "Peso Atual %",
        "objetivo_pct" : "Objetivo %",
        "gap_objetivo" : "Gap %",
    }

    cols_disp = [c for c in colunas_map if c in df.columns]

    if len(cols_disp) < 3:
        st.info(
            "Colunas de objetivo não encontradas na planilha. "
            "Adicione 'objetivo_pct' para usar esta análise."
        )

        # Exibe alocação atual mesmo sem objetivo
        if "ticker" in df.columns and "valor_atual" in df.columns:
            st.markdown("#### 📌 Alocação Atual")
            aloc = (
                df[["ticker", "nome", "valor_atual"]]
                .copy()
                .sort_values("valor_atual", ascending=False)
                .reset_index(drop=True)
            ) if "nome" in df.columns else (
                df[["ticker", "valor_atual"]]
                .copy()
                .sort_values("valor_atual", ascending=False)
                .reset_index(drop=True)
            )
            total = aloc["valor_atual"].sum()
            aloc["Peso %"] = aloc["valor_atual"] / total * 100
            st.dataframe(
                aloc,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "valor_atual": st.column_config.NumberColumn(
                        "Valor", format="$%.2f"
                    ),
                    "Peso %": st.column_config.ProgressColumn(
                        format="%.1f%%", min_value=0, max_value=100
                    ),
                },
            )
        return

    df_aloc = (
        df[cols_disp]
        .copy()
        .rename(columns={c: colunas_map[c] for c in cols_disp})
    )

    if "Valor Atual" in df_aloc.columns:
        df_aloc = df_aloc.sort_values("Valor Atual", ascending=False)

    st.dataframe(
        df_aloc,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor Atual": st.column_config.NumberColumn(format="$%.2f"),
            "Peso Atual %": st.column_config.ProgressColumn(
                format="%.1f%%", min_value=0, max_value=100
            ),
            "Objetivo %": st.column_config.NumberColumn(format="%.1f%%"),
            "Gap %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    # --- Ativos que precisam de aporte ---
    if "gap_objetivo" in df.columns:
        st.divider()
        st.markdown("#### 🎯 Ativos que precisam de aporte")
        df_gap = df[df["gap_objetivo"] < 0].copy() if "gap_objetivo" in df.columns else pd.DataFrame()

        if not df_gap.empty:
            df_gap = df_gap.sort_values("gap_objetivo", ascending=True)
            for _, row in df_gap.iterrows():
                ticker = row.get("ticker", "")
                gap    = safe_float(row.get("gap_objetivo", 0))
                st.write(
                    f"🔴 **{ticker}** — Gap: {formatar_pct(abs(gap))} abaixo do objetivo"
                )
        else:
            st.success("✅ Todos os ativos estão dentro ou acima do objetivo!")


# ============================================================
# SUBTAB 4: RESUMO COMPLETO
# ============================================================

def _resumo_completo(resumo_p: dict, resumo_e: dict) -> None:
    """Resumo financeiro completo do portfólio."""

    st.markdown("### 📋 Resumo Financeiro Completo")

    patrimonio_total = (
        resumo_p.get("patrimonio_total", 0)
        + resumo_e.get("patrimonio_total", 0)
    )
    custo_total = (
        resumo_p.get("custo_total", 0)
        + resumo_e.get("custo_total", 0)
    )
    lucro_total = (
        resumo_p.get("lucro_total_usd", 0)
        + resumo_e.get("lucro_total_usd", 0)
    )
    renda_mensal = (
        resumo_p.get("renda_mensal", 0)
        + resumo_e.get("renda_mensal", 0)
    )
    renda_anual  = renda_mensal * 12
    lucro_pct    = (lucro_total / custo_total * 100) if custo_total > 0 else 0
    yield_atual  = (renda_anual / patrimonio_total * 100) if patrimonio_total > 0 else 0

    # --- Portfólio Total ---
    st.markdown("#### 🌐 Portfólio Total (Principal + Ericsson)")

    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimônio Total",  formatar_compacto(patrimonio_total))
    c2.metric("Custo Total",       formatar_moeda(custo_total))
    c3.metric(
        "Lucro/Prejuízo",
        formatar_moeda(lucro_total),
        delta=formatar_pct(lucro_pct),
        delta_color="normal",
    )

    c4, c5, c6 = st.columns(3)
    c4.metric("Renda Mensal USD",  formatar_moeda(renda_mensal))
    c5.metric("Renda Mensal BRL",  f"R$ {renda_mensal * BRL_USD:,.2f}")
    c6.metric("Yield sobre Patrim.", formatar_pct(yield_atual))

    st.divider()

    # --- Carteira Principal ---
    st.markdown("#### 📊 Carteira Principal")

    r = resumo_p
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patrimônio",    formatar_compacto(r.get("patrimonio_total", 0)))
    c2.metric("Lucro/Prejuízo",
              formatar_moeda(r.get("lucro_total_usd", 0)),
              delta=formatar_pct(r.get("lucro_total_pct", 0)),
              delta_color="normal")
    c3.metric("Renda Mensal",  formatar_moeda(r.get("renda_mensal", 0)))
    c4.metric("YoC Médio",     formatar_pct(r.get("yoc_medio", 0)))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Num. Ativos",   r.get("num_ativos", 0))
    c6.metric("DY Médio",      formatar_pct(r.get("dy_medio", 0)))
    c7.metric("Custo Total",   formatar_moeda(r.get("custo_total", 0)))
    c8.metric("Renda Anual",   formatar_moeda(r.get("renda_anual", 0)))

    # --- Carteira Ericsson ---
    if resumo_e:
        st.divider()
        st.markdown("#### 🔵 Carteira Ericsson")

        e = resumo_e
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Patrimônio",    formatar_compacto(e.get("patrimonio_total", 0)))
        d2.metric("Lucro/Prejuízo",
                  formatar_moeda(e.get("lucro_total_usd", 0)),
                  delta=formatar_pct(e.get("lucro_total_pct", 0)),
                  delta_color="normal")
        d3.metric("Renda Mensal",  formatar_moeda(e.get("renda_mensal", 0)))
        d4.metric("YoC Médio",     formatar_pct(e.get("yoc_medio", 0)))

    st.divider()

    # --- Equivalências em BRL ---
    st.markdown("#### 💱 Equivalências em BRL")
    st.caption(f"Câmbio usado: R$ {BRL_USD:.2f} por USD")

    b1, b2, b3 = st.columns(3)
    b1.metric("Patrimônio em BRL", f"R$ {patrimonio_total * BRL_USD:,.2f}")
    b2.metric("Renda Mensal BRL",  f"R$ {renda_mensal * BRL_USD:,.2f}")
    b3.metric("Renda Anual BRL",   f"R$ {renda_anual * BRL_USD:,.2f}")
