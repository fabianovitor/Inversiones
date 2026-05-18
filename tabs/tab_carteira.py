# ============================================================
# tabs/tab_carteira.py - Aba Carteira Principal
# ============================================================

import streamlit as st
import pandas as pd
import plotly.express as px
from utils import fmt_usd, fmt_pct, fmt_pct_dy, fmt_qtd, aplicar_estilo_df
from data_loader import calcular_metricas
from config import TOOLTIPS, CORES


def renderizar(df_principal):
    """Renderiza a aba Carteira Principal.
    
    Args:
        df_principal: DataFrame com a carteira principal (sem Ericsson)
    """
    st.header("📊 Carteira Principal")
    
    if df_principal is None or df_principal.empty:
        st.warning("⚠️ Nenhum ativo na carteira principal.")
        return
    
    # ----- MÉTRICAS PRINCIPAIS -----
    metricas = calcular_metricas(df_principal)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Patrimônio",
            value=fmt_usd(metricas["patrimonio"]),
            delta=fmt_pct(metricas["lucro_pct"]),
            help=TOOLTIPS["patrimonio"],
        )
    
    with col2:
        st.metric(
            label="📈 Lucro/Prejuízo",
            value=fmt_usd(metricas["lucro_usd"]),
            delta=fmt_pct(metricas["lucro_pct"]),
        )
    
    with col3:
        st.metric(
            label="💵 Renda Mensal Estimada",
            value=fmt_usd(metricas["renda_mensal"]),
            help=TOOLTIPS["renda_mensal"],
        )
    
    with col4:
        st.metric(
            label="📊 DY Médio",
            value=f"{metricas['dy_medio']:.2f}%",
            help=TOOLTIPS["dy"],
        )
    
    # Linha 2 de métricas
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric(
            label="💼 Custo Total",
            value=fmt_usd(metricas["custo_total"]),
        )
    
    with col6:
        st.metric(
            label="📅 Renda Anual",
            value=fmt_usd(metricas["renda_anual"]),
        )
    
    with col7:
        st.metric(
            label="🎯 YoC Médio",
            value=f"{metricas['yoc_medio']:.2f}%",
            help=TOOLTIPS["yoc"],
        )
    
    with col8:
        st.metric(
            label="🏢 Nº de Ativos",
            value=metricas["num_ativos"],
        )
    
    st.divider()
    
    # ----- TABELA DETALHADA -----
    st.subheader("📋 Detalhamento dos Ativos")
    
    # Prepara DataFrame para exibição
    df_display = df_principal.copy()
    df_display = df_display.sort_values("valor_atual", ascending=False).reset_index(drop=True)
    
    # Seleciona e renomeia colunas
    colunas_exibir = {
        "ticker": "Ticker",
        "nome": "Nome",
        "setor": "Setor",
        "qtd": "Qtd",
        "pm_usd": "PM (USD)",
        "preco_atual": "Preço Atual",
        "variacao_pct": "Var %",
        "custo_total": "Custo Total",
        "valor_atual": "Valor Atual",
        "lucro_usd": "Lucro USD",
        "lucro_pct": "Lucro %",
        "div_yield": "DY",
        "yoc": "YoC %",
        "renda_mensal": "Renda/Mês",
        "peso_pct": "Peso %",
    }
    
    df_tabela = df_display[list(colunas_exibir.keys())].rename(columns=colunas_exibir)
    
    # Formata valores
    formatters = {
        "Qtd": fmt_qtd,
        "PM (USD)": fmt_usd,
        "Preço Atual": fmt_usd,
        "Var %": fmt_pct,
        "Custo Total": fmt_usd,
        "Valor Atual": fmt_usd,
        "Lucro USD": fmt_usd,
        "Lucro %": fmt_pct,
        "DY": fmt_pct_dy,
        "YoC %": lambda x: f"{x:.2f}%" if pd.notna(x) else "-",
        "Renda/Mês": fmt_usd,
        "Peso %": lambda x: f"{x:.2f}%" if pd.notna(x) else "-",
    }
    
    styled = df_tabela.style.format(formatters)
    
    # Aplica cores em colunas de lucro/variação
    colunas_cor = ["Var %", "Lucro USD", "Lucro %"]
    styled = aplicar_estilo_df(styled, colunas_cor)
    
    st.dataframe(styled, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # ----- GRÁFICOS -----
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        st.subheader("🥧 Distribuição por Ativo")
        fig_pizza = px.pie(
            df_display,
            values="valor_atual",
            names="ticker",
            hole=0.4,
        )
        fig_pizza.update_traces(textposition="inside", textinfo="percent+label")
        fig_pizza.update_layout(showlegend=True, height=400)
        st.plotly_chart(fig_pizza, use_container_width=True)
    
    with col_g2:
        st.subheader("🏭 Distribuição por Setor")
        df_setor = df_display.groupby("setor", as_index=False)["valor_atual"].sum()
        df_setor = df_setor.sort_values("valor_atual", ascending=False)
        fig_setor = px.pie(
            df_setor,
            values="valor_atual",
            names="setor",
            hole=0.4,
        )
        fig_setor.update_traces(textposition="inside", textinfo="percent+label")
        fig_setor.update_layout(showlegend=True, height=400)
        st.plotly_chart(fig_setor, use_container_width=True)
    
    # Gráfico de barras: Lucro/Prejuízo por ativo
    st.subheader("📊 Lucro/Prejuízo por Ativo")
    df_lucro = df_display.sort_values("lucro_usd", ascending=True)
    fig_barras = px.bar(
        df_lucro,
        x="lucro_usd",
        y="ticker",
        orientation="h",
        color="lucro_usd",
        color_continuous_scale=["red", "gray", "green"],
        color_continuous_midpoint=0,
        labels={"lucro_usd": "Lucro/Prejuízo (USD)", "ticker": "Ativo"},
    )
    fig_barras.update_layout(height=max(400, len(df_lucro) * 30), showlegend=False)
    st.plotly_chart(fig_barras, use_container_width=True)
    
    # Gráfico de barras: Renda mensal por ativo
    st.subheader("💵 Renda Mensal por Ativo")
    df_renda = df_display[df_display["renda_mensal"] > 0].sort_values("renda_mensal", ascending=True)
    if not df_renda.empty:
        fig_renda = px.bar(
            df_renda,
            x="renda_mensal",
            y="ticker",
            orientation="h",
            color="renda_mensal",
            color_continuous_scale="Greens",
            labels={"renda_mensal": "Renda Mensal (USD)", "ticker": "Ativo"},
        )
        fig_renda.update_layout(height=max(400, len(df_renda) * 30), showlegend=False)
        st.plotly_chart(fig_renda, use_container_width=True)
    else:
        st.info("Nenhum ativo com renda de dividendos no momento.")
