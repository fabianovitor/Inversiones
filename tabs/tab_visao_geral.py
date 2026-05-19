# ============================================================
# tabs/tab_visao_geral.py - Aba Visão Geral
# ============================================================

import streamlit as st
import pandas as pd

from utils import formatar_moeda, formatar_pct, formatar_compacto
from data_loader import resumo_carteira
from debug_manager import debug


def renderizar(df_principal: pd.DataFrame,
               df_ericsson: pd.DataFrame) -> None:

    st.markdown("## Visão Geral do Portfólio")

    # ── Calcular resumos ──────────────────────────────────────
    resumo_p = resumo_carteira(df_principal)
    resumo_e = resumo_carteira(df_ericsson) if (
        df_ericsson is not None and not df_ericsson.empty
    ) else {}

    debug.log("visao_geral", "resumo_principal", resumo_p)
    debug.log("visao_geral", "resumo_ericsson", resumo_e)

    # ── Totais consolidados (USD) ─────────────────────────────
    patrimonio_total = (
        resumo_p.get("patrimonio_total", 0)
        + resumo_e.get("patrimonio_total", 0)
    )
    custo_total = (
        resumo_p.get("custo_total", 0)
        + resumo_e.get("custo_total", 0)
    )
    lucro_total = patrimonio_total - custo_total
    lucro_pct   = (lucro_total / custo_total * 100) if custo_total > 0 else 0
    renda_mensal = (
        resumo_p.get("renda_mensal", 0)
        + resumo_e.get("renda_mensal", 0)
    )
    renda_anual = renda_mensal * 12

    debug.log("visao_geral", "patrimonio_total_usd", patrimonio_total)
    debug.log("visao_geral", "renda_mensal_usd",     renda_mensal)
    debug.log("visao_geral", "lucro_total_usd",      lucro_total)

    # ── Métricas principais ───────────────────────────────────
    st.markdown("### 💼 Consolidado (USD)")
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "💰 Patrimônio Total",
        formatar_compacto(patrimonio_total),
        help="Valor total da carteira a preço atual (USD)",
    )
    c2.metric(
        "📈 Lucro/Prejuízo",
        formatar_moeda(lucro_total),
        delta=formatar_pct(lucro_pct),
        delta_color="normal",
        help="Diferença entre valor atual e custo total investido (USD)",
    )
    c3.metric(
        "💵 Renda Mensal",
        formatar_moeda(renda_mensal),
        help="Estimativa de dividendos mensais - Dividendos TTM ÷ 12 (USD)",
    )
    c4.metric(
        "🏦 Renda Anual",
        formatar_moeda(renda_anual),
        help="Estimativa de dividendos anuais (USD)",
    )

    st.divider()

    # ── Detalhes por carteira ─────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📊 Carteira Principal")
        r = resumo_p
        if r:
            m1, m2 = st.columns(2)
            m1.metric("Patrimônio",   formatar_compacto(r.get("patrimonio_total", 0)))
            m2.metric("Custo Total",  formatar_compacto(r.get("custo_total", 0)))
            m3, m4 = st.columns(2)
            m3.metric("Renda Mensal", formatar_moeda(r.get("renda_mensal", 0)))
            m4.metric("Renda Anual",  formatar_moeda(r.get("renda_anual", 0)))
            m5, m6 = st.columns(2)
            m5.metric("YoC Médio",    formatar_pct(r.get("yoc_medio", 0)))
            m6.metric("DY Médio",     formatar_pct(r.get("dy_medio", 0)))
            st.metric("Nº de Ativos", r.get("num_ativos", 0))
        else:
            st.info("Sem dados da carteira principal")

    with col2:
        st.markdown("### 🔵 Carteira Ericsson")
        e = resumo_e
        if e:
            m1, m2 = st.columns(2)
            m1.metric("Patrimônio",   formatar_compacto(e.get("patrimonio_total", 0)))
            m2.metric("Custo Total",  formatar_compacto(e.get("custo_total", 0)))
            m3, m4 = st.columns(2)
            m3.metric("Renda Mensal", formatar_moeda(e.get("renda_mensal", 0)))
            m4.metric("Renda Anual",  formatar_moeda(e.get("renda_anual", 0)))
            m5, m6 = st.columns(2)
            m5.metric("YoC Médio",    formatar_pct(e.get("yoc_medio", 0)))
            m6.metric("DY Médio",     formatar_pct(e.get("dy_medio", 0)))
        else:
            st.info("Sem dados Ericsson")

    st.divider()

    # ── Distribuição por categoria ────────────────────────────
    if not df_principal.empty and "categoria" in df_principal.columns:
        st.markdown("### 🗂️ Distribuição por Categoria (USD)")
        try:
            cat = (
                df_principal.groupby("categoria")["valor_atual"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            cat.columns = ["Categoria", "Valor (USD)"]
            cat["Valor (USD)"] = cat["Valor (USD)"].apply(
                lambda v: float(v) if v else 0.0
            )
            total_cat = cat["Valor (USD)"].sum()
            cat["Peso %"] = cat["Valor (USD)"].apply(
                lambda v: f"{v / total_cat * 100:.1f}%" if total_cat > 0 else "0%"
            )
            cat["Valor (USD)"] = cat["Valor (USD)"].apply(formatar_moeda)
            st.dataframe(cat, use_container_width=True, hide_index=True)
        except Exception as ex:
            debug.log_erro("visao_geral_categorias", ex)
            st.warning("Não foi possível calcular distribuição por categoria.")
