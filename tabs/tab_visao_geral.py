# ============================================================
# tabs/tab_visao_geral.py - Aba Visão Geral
# ============================================================

import streamlit as st
import pandas as pd

from utils import formatar_moeda, formatar_pct, formatar_compacto
from data_loader import resumo_carteira
from config import BRL_USD


def renderizar(df_principal: pd.DataFrame,
               df_ericsson: pd.DataFrame) -> None:

    st.markdown("## 📊 Visão Geral do Portfólio")

    resumo_p = resumo_carteira(df_principal)
    resumo_e = resumo_carteira(df_ericsson) if (
        df_ericsson is not None and not df_ericsson.empty
    ) else {}

    patrimonio_total = (
        resumo_p.get("patrimonio_total", 0)
        + resumo_e.get("patrimonio_total", 0)
    )
    renda_mensal = (
        resumo_p.get("renda_mensal", 0)
        + resumo_e.get("renda_mensal", 0)
    )
    lucro_total = (
        resumo_p.get("lucro_total_usd", 0)
        + resumo_e.get("lucro_total_usd", 0)
    )
    custo_total = (
        resumo_p.get("custo_total", 0)
        + resumo_e.get("custo_total", 0)
    )
    lucro_pct = (lucro_total / custo_total * 100) if custo_total > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💼 Patrimônio Total", formatar_compacto(patrimonio_total))
    c2.metric("📈 Lucro/Prejuízo",   formatar_moeda(lucro_total),
              delta=formatar_pct(lucro_pct), delta_color="normal")
    c3.metric("💰 Renda Mensal",     formatar_moeda(renda_mensal))
    c4.metric("🏦 Renda Anual",      formatar_moeda(renda_mensal * 12))

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📊 Carteira Principal")
        r = resumo_p
        st.metric("Patrimônio",   formatar_compacto(r.get("patrimonio_total", 0)))
        st.metric("Renda Mensal", formatar_moeda(r.get("renda_mensal", 0)))
        st.metric("YoC Médio",    formatar_pct(r.get("yoc_medio", 0)))
        st.metric("Ativos",       r.get("num_ativos", 0))

    with col2:
        st.markdown("### 🔵 Carteira Ericsson")
        e = resumo_e
        if e:
            st.metric("Patrimônio",   formatar_compacto(e.get("patrimonio_total", 0)))
            st.metric("Renda Mensal", formatar_moeda(e.get("renda_mensal", 0)))
            st.metric("YoC Médio",    formatar_pct(e.get("yoc_medio", 0)))
        else:
            st.info("Sem dados Ericsson")

    st.divider()
   
