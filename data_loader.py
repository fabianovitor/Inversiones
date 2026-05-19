# ============================================================
# data_loader.py - Carregamento e processamento de dados
# ============================================================

import pandas as pd
import streamlit as st

from config import (
    GOOGLE_SHEETS_URL,
    MAPEAMENTO_COLUNAS_GS,
    TICKER_ERICSSON,
    CACHE_TTL_PLANILHA,
)
from utils import safe_float


@st.cache_data(ttl=CACHE_TTL_PLANILHA)
def carregar_planilha() -> pd.DataFrame:
    """Carrega dados do Google Sheets."""
    try:
        df = pd.read_csv(GOOGLE_SHEETS_URL)
        df.columns = [c.strip().lower() for c in df.columns]

        # Renomear colunas
        mapa = {k.lower(): v for k, v in MAPEAMENTO_COLUNAS_GS.items()}
        df = df.rename(columns=mapa)

        # Colunas numéricas
        numericas = [
            "qtd", "pm_usd", "div_anual", "yoc_planilha",
            "preco_atual_planilha", "valor_total_planilha",
            "peso_planilha", "objetivo_pct",
        ]
        for col in numericas:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str)
                    .str.replace(",", ".", regex=False)
                    .str.replace("%", "", regex=False)
                    .str.strip(),
                    errors="coerce",
                ).fillna(0)

        return df
    except Exception as e:
        st.error(f"❌ Erro ao carregar planilha: {e}")
        return pd.DataFrame()


def separar_carteiras(df: pd.DataFrame):
    """Separa carteira principal e Ericsson."""
    if df.empty:
        return df, pd.DataFrame()

    if "ticker" not in df.columns:
        return df, pd.DataFrame()

    mask_eric = df["ticker"].astype(str).str.upper() == TICKER_ERICSSON.upper()
    df_ericsson  = df[mask_eric].copy().reset_index(drop=True)
    df_principal = df[~mask_eric].copy().reset_index(drop=True)

    return df_principal, df_ericsson


@st.cache_data(ttl=CACHE_TTL_PLANILHA)
def enriquecer_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Enriquece DataFrame com cálculos derivados."""
    if df.empty:
        return df

    df = df.copy()

    # Preço atual
    if "preco_atual_planilha" in df.columns:
        df["preco_atual"] = df["preco_atual_planilha"]
    elif "pm_usd" in df.columns:
        df["preco_atual"] = df["pm_usd"]
    else:
        df["preco_atual"] = 0.0

    # Valor atual
    if "valor_total_planilha" in df.columns:
        df["valor_atual"] = df["valor_total_planilha"]
    elif "qtd" in df.columns and "preco_atual" in df.columns:
        df["valor_atual"] = df["qtd"] * df["preco_atual"]
    else:
        df["valor_atual"] = 0.0

    # Custo total
    if "qtd" in df.columns and "pm_usd" in df.columns:
        df["custo_total"] = df["qtd"] * df["pm_usd"]
    else:
        df["custo_total"] = df["valor_atual"].copy()

    # Lucro
    df["lucro_usd"] = df["valor_atual"] - df["custo_total"]
    df["lucro_pct"] = df.apply(
        lambda r: (r["lucro_usd"] / r["custo_total"] * 100)
        if safe_float(r.get("custo_total", 0)) > 0 else 0,
        axis=1,
    )

    # Renda mensal
    if "div_anual" in df.columns and "qtd" in df.columns:
        df["renda_mensal"] = df["qtd"] * df["div_anual"] / 12
    else:
        df["renda_mensal"] = 0.0

    # YoC
    if "yoc_planilha" in df.columns:
        df["yoc"] = df["yoc_planilha"]
    elif "div_anual" in df.columns and "pm_usd" in df.columns:
        df["yoc"] = df.apply(
            lambda r: (r["div_anual"] / r["pm_usd"] * 100)
            if safe_float(r.get("pm_usd", 0)) > 0 else 0,
            axis=1,
        )
    else:
        df["yoc"] = 0.0

    # DY atual
    if "div_anual" in df.columns and "preco_atual" in df.columns:
        df["dy_atual"] = df.apply(
            lambda r: (r["div_anual"] / r["preco_atual"] * 100)
            if safe_float(r.get("preco_atual", 0)) > 0 else 0,
            axis=1,
        )
    else:
        df["dy_atual"] = 0.0

    # Peso %
    total = df["valor_atual"].sum()
    df["peso_pct"] = df["valor_atual"].apply(
        lambda v: (v / total * 100) if total > 0 else 0
    )

    return df


def resumo_carteira(df: pd.DataFrame) -> dict:
    """Calcula resumo da carteira."""
    if df is None or df.empty:
        return {}

    patrimonio   = safe_float(df["valor_atual"].sum()) if "valor_atual" in df.columns else 0
    custo_total  = safe_float(df["custo_total"].sum()) if "custo_total" in df.columns else 0
    lucro_usd    = patrimonio - custo_total
    lucro_pct    = (lucro_usd / custo_total * 100) if custo_total > 0 else 0
    renda_mensal = safe_float(df["renda_mensal"].sum()) if "renda_mensal" in df.columns else 0
    renda_anual  = renda_mensal * 12
    yoc_medio    = safe_float(df["yoc"].mean()) if "yoc" in df.columns else 0
    dy_medio     = (renda_anual / patrimonio * 100) if patrimonio > 0 else 0
    num_ativos   = df["ticker"].nunique() if "ticker" in df.columns else 0

    return {
        "patrimonio_total" : patrimonio,
        "custo_total"      : custo_total,
        "lucro_total_usd"  : lucro_usd,
        "lucro_total_pct"  : lucro_pct,
        "renda_mensal"     : renda_mensal,
        "renda_anual"      : renda_anual,
        "yoc_medio"        : yoc_medio,
        "dy_medio"         : dy_medio,
        "num_ativos"       : num_ativos,
    }
