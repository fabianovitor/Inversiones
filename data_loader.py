# ============================================================
# data_loader.py - Orquestrador de dados
# Busca da fonte configurada + enriquece com mercado
# ============================================================

import streamlit as st
import pandas as pd

from data_sources import get_data_source
from market_data import enriquecer_ativo
from utils import safe_float, safe_div


# ============================================================
# FUNÇÃO PRINCIPAL - usada pelo app.py
# ============================================================

def carregar_carteira() -> pd.DataFrame:
    """Carrega carteira da fonte configurada em config.py.
    
    Fluxo:
        1. Detecta fonte ativa (Google Sheets, IBKR, etc.)
        2. Carrega dados brutos
        3. Enriquece com dados de mercado (yfinance)
        4. Calcula métricas derivadas
    
    Returns:
        DataFrame completo pronto para o dashboard
    """
    # 1. Obtém a fonte configurada
    fonte = get_data_source()

    with st.spinner(f"📊 Carregando dados de {fonte.nome_fonte()}..."):
        df = fonte.carregar()

    if df is None or df.empty:
        st.error(
            f"❌ Nenhum dado retornado de {fonte.nome_fonte()}.\n\n"
            "Verifique as configurações no config.py."
        )
        return pd.DataFrame()

    # 2. Enriquece com dados de mercado
    df = enriquecer_carteira(df)

    return df


# ============================================================
# ENRIQUECIMENTO COM DADOS DE MERCADO
# ============================================================

def enriquecer_carteira(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona cotações e calcula métricas derivadas.
    
    Args:
        df: DataFrame normalizado da fonte de dados
    
    Returns:
        DataFrame enriquecido com métricas calculadas
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # Inicializa colunas de mercado
    df["preco_atual"]  = 0.0
    df["variacao_pct"] = 0.0
    df["div_yield"]    = 0.0
    df["setor"]        = ""

    # Busca dados de mercado para cada ticker
    total = len(df)
    progress = st.progress(0, text="🌐 Buscando cotações...")

    for i, row in df.iterrows():
        ticker = row["ticker"]
        progresso_pct = (i + 1) / total
        progress.progress(progresso_pct, text=f"📈 Buscando {ticker}...")

        dados = enriquecer_ativo(ticker)

        # --- Preço atual ---
        # Prioridade: planilha > yfinance
        preco_planilha = safe_float(row.get("preco_atual_planilha", 0))
        if preco_planilha > 0:
            df.at[i, "preco_atual"] = preco_planilha
        else:
            df.at[i, "preco_atual"] = safe_float(dados.get("preco_atual"))

        # --- Variação do dia (sempre do yfinance) ---
        df.at[i, "variacao_pct"] = safe_float(dados.get("variacao_pct"))

        # --- Setor ---
        setor_yf = dados.get("setor") or ""
        df.at[i, "setor"] = setor_yf if setor_yf else row.get("categoria", "Outros")

        # --- Dividend Yield ---
        # Prioridade: planilha > yfinance
        yoc_planilha = safe_float(row.get("yoc_planilha", 0))
        if yoc_planilha > 0:
            df.at[i, "div_yield"] = yoc_planilha / 100
        else:
            df.at[i, "div_yield"] = safe_float(dados.get("div_yield"))

        # --- Dividendos anuais por ação ---
        div_planilha = safe_float(row.get("div_anual", 0))
        if div_planilha > 0:
            df.at[i, "div_anual"] = div_planilha
        else:
            df.at[i, "div_anual"] = safe_float(dados.get("div_anual"))

    progress.empty()

    # ----------------------------------------------------------
    # CÁLCULOS DERIVADOS
    # ----------------------------------------------------------
    df = calcular_metricas(df)

    return df


# ============================================================
# CÁLCULO DE MÉTRICAS
# ============================================================

def calcular_metricas(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula todas as métricas derivadas do portfolio.
    
    Args:
        df: DataFrame com preços e dados base
    
    Returns:
        DataFrame com métricas calculadas
    """
    df = df.copy()

    # --- Valores base ---
    df["custo_total"]  = df["qtd"] * df["pm_usd"]
    df["valor_atual"]  = df["qtd"] * df["preco_atual"]

    # --- Lucro / Prejuízo ---
    df["lucro_usd"] = df["valor_atual"] - df["custo_total"]
    df["lucro_pct"] = df.apply(
        lambda r: safe_div(r["lucro_usd"], r["custo_total"]) * 100,
        axis=1
    )

    # --- Renda de dividendos ---
    df["div_recebido_anual"] = df["qtd"] * df["div_anual"].fillna(0)
    df["renda_mensal"]       = df["div_recebido_anual"] / 12

    # --- Yield on Cost ---
    df["yoc"] = df.apply(
        lambda r: safe_div(r["div_recebido_anual"], r["custo_total"]) * 100,
        axis=1
    )

    # --- Dividend Yield (sobre preço atual) ---
    df["dy_atual"] = df.apply(
        lambda r: safe_div(r["div_recebido_anual"], r["valor_atual"]) * 100,
        axis=1
    )

    # --- Peso % na carteira (recalculado) ---
    total_carteira = df["valor_atual"].sum()
    df["peso_pct"] = df.apply(
        lambda r: safe_div(r["valor_atual"], total_carteira) * 100,
        axis=1
    )

    # --- Diferença objetivo vs atual ---
    df["gap_objetivo"] = df.apply(
        lambda r: r.get("objetivo_pct", 0) - r["peso_pct"],
        axis=1
    )

    return df


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def separar_carteiras(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa carteira principal da carteira Ericsson.
    
    Args:
        df: DataFrame completo
    
    Returns:
        Tupla (df_principal, df_ericsson)
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_principal = df[df["tipo"] == "principal"].copy()
    df_ericsson  = df[df["tipo"] == "ericsson"].copy()

    return df_principal, df_ericsson


def resumo_carteira(df: pd.DataFrame) -> dict:
    """Retorna métricas resumidas da carteira.
    
    Args:
        df: DataFrame da carteira
    
    Returns:
        Dicionário com métricas principais
    """
    if df is None or df.empty:
        return {}

    return {
        "patrimonio_total"  : df["valor_atual"].sum(),
        "custo_total"       : df["custo_total"].sum(),
        "lucro_total_usd"   : df["lucro_usd"].sum(),
        "lucro_total_pct"   : safe_div(
                                df["lucro_usd"].sum(),
                                df["custo_total"].sum()
                              ) * 100,
        "renda_mensal"      : df["renda_mensal"].sum(),
        "renda_anual"       : df["div_recebido_anual"].sum(),
        "num_ativos"        : len(df),
        "yoc_medio"         : safe_div(
                                df["div_recebido_anual"].sum(),
                                df["custo_total"].sum()
                              ) * 100,
        "dy_medio"          : safe_div(
                                df["div_recebido_anual"].sum(),
                                df["valor_atual"].sum()
                              ) * 100,
    }
