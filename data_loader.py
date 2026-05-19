# ============================================================
# data_loader.py - Carregamento e processamento de dados
# ============================================================

import pandas as pd
import streamlit as st
import re

from config import (
    GOOGLE_SHEETS_URL,
    MAPEAMENTO_COLUNAS_GS,
    TICKER_ERICSSON,
    CACHE_TTL_PLANILHA,
)
from utils import safe_float


def _limpar_numero(valor_str) -> float:
    """Limpa string numérica e converte para float. Tudo em USD."""
    if valor_str is None:
        return 0.0
    s = str(valor_str).strip()
    if s == "" or s.lower() in ("nan", "none", "-", "n/a", "#n/a", "#value!"):
        return 0.0
    # Remove símbolos de moeda e espaços (não deve ter BRL, mas limpa por segurança)
    s = re.sub(r"[R$\$€£¥\s]", "", s)
    # Trata formato 1.234,56 -> 1234.56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    s = s.replace("%", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


@st.cache_data(ttl=CACHE_TTL_PLANILHA)
def carregar_planilha() -> pd.DataFrame:
    """Carrega dados do Google Sheets. Todos os valores monetários são USD."""
    try:
        df = pd.read_csv(GOOGLE_SHEETS_URL)

        # Normaliza colunas
        df.columns = [c.strip().lower() for c in df.columns]

        # Renomeia colunas conforme mapeamento
        mapa = {k.lower(): v for k, v in MAPEAMENTO_COLUNAS_GS.items()}
        df = df.rename(columns=mapa)

        # Converte colunas numéricas (já em USD na planilha)
        numericas = [
            "qtd", "pm_usd", "div_anual", "yoc_planilha",
            "preco_atual_planilha", "valor_total_planilha",
            "peso_planilha", "objetivo_pct",
        ]
        for col in numericas:
            if col in df.columns:
                df[col] = df[col].apply(_limpar_numero)

        # Remove linhas com ticker vazio
        if "ticker" in df.columns:
            df = df[df["ticker"].notna()]
            df = df[df["ticker"].astype(str).str.strip() != ""]
            df = df[~df["ticker"].astype(str).str.strip().str.startswith("#")]

        return df.reset_index(drop=True)

    except Exception as e:
        st.error(f"❌ Erro ao carregar planilha: {e}")
        try:
            from debug_manager import debug
            debug.log_erro("carregar_planilha", e)
        except Exception:
            pass
        return pd.DataFrame()


def separar_carteiras(df: pd.DataFrame):
    """Separa carteira principal e Ericsson."""
    if df.empty:
        return df, pd.DataFrame()
    if "ticker" not in df.columns:
        return df, pd.DataFrame()

    mask_eric = (
        df["ticker"].astype(str).str.upper().str.strip()
        == TICKER_ERICSSON.upper()
    )
    df_ericsson  = df[mask_eric].copy().reset_index(drop=True)
    df_principal = df[~mask_eric].copy().reset_index(drop=True)

    return df_principal, df_ericsson


@st.cache_data(ttl=CACHE_TTL_PLANILHA)
def enriquecer_dados(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enriquece DataFrame com cálculos derivados.
    TODOS os valores monetários são mantidos em USD.
    A planilha já fornece dados em USD.
    """
    if df.empty:
        return df

    df = df.copy()

    # Preço atual (USD) — usa planilha diretamente
    if "preco_atual_planilha" in df.columns:
        df["preco_atual"] = df["preco_atual_planilha"].apply(safe_float)
    elif "pm_usd" in df.columns:
        df["preco_atual"] = df["pm_usd"].apply(safe_float)
    else:
        df["preco_atual"] = 0.0

    # Valor atual (USD) — usa planilha diretamente
    if "valor_total_planilha" in df.columns:
        df["valor_atual"] = df["valor_total_planilha"].apply(safe_float)
    elif "qtd" in df.columns and "preco_atual" in df.columns:
        df["valor_atual"] = (
            df["qtd"].apply(safe_float) * df["preco_atual"].apply(safe_float)
        )
    else:
        df["valor_atual"] = 0.0

    # Custo total (USD)
    if "qtd" in df.columns and "pm_usd" in df.columns:
        df["custo_total"] = (
            df["qtd"].apply(safe_float) * df["pm_usd"].apply(safe_float)
        )
    else:
        df["custo_total"] = df["valor_atual"].copy()

    # Lucro (USD)
    df["lucro_usd"] = df["valor_atual"] - df["custo_total"]
    df["lucro_pct"] = df.apply(
        lambda r: (r["lucro_usd"] / r["custo_total"] * 100)
        if safe_float(r.get("custo_total", 0)) > 0 else 0,
        axis=1,
    )

    # Renda mensal (USD) — div_anual já em USD na planilha
    if "div_anual" in df.columns and "qtd" in df.columns:
        df["renda_mensal"] = (
            df["qtd"].apply(safe_float)
            * df["div_anual"].apply(safe_float)
            / 12
        )
    else:
        df["renda_mensal"] = 0.0

    # YoC (%)
    if "yoc_planilha" in df.columns:
        df["yoc"] = df["yoc_planilha"].apply(safe_float)
    elif "div_anual" in df.columns and "pm_usd" in df.columns:
        df["yoc"] = df.apply(
            lambda r: (safe_float(r["div_anual"]) / safe_float(r["pm_usd"]) * 100)
            if safe_float(r.get("pm_usd", 0)) > 0 else 0,
            axis=1,
        )
    else:
        df["yoc"] = 0.0

    # DY atual (%)
    if "div_anual" in df.columns and "preco_atual" in df.columns:
        df["dy_atual"] = df.apply(
            lambda r: (safe_float(r["div_anual"]) / safe_float(r["preco_atual"]) * 100)
            if safe_float(r.get("preco_atual", 0)) > 0 else 0,
            axis=1,
        )
    else:
        df["dy_atual"] = 0.0

    # Peso % na carteira
    total = df["valor_atual"].sum()
    df["peso_pct"] = df["valor_atual"].apply(
        lambda v: (safe_float(v) / total * 100) if total > 0 else 0
    )

    return df


def resumo_carteira(df: pd.DataFrame) -> dict:
    """
    Calcula resumo da carteira.
    Todos os valores monetários em USD.
    """
    if df is None or df.empty:
        return {}

    patrimonio   = safe_float(df["valor_atual"].sum())  if "valor_atual"  in df.columns else 0
    custo_total  = safe_float(df["custo_total"].sum())  if "custo_total"  in df.columns else 0
    lucro_usd    = patrimonio - custo_total
    lucro_pct    = (lucro_usd / custo_total * 100) if custo_total > 0 else 0
    renda_mensal = safe_float(df["renda_mensal"].sum()) if "renda_mensal" in df.columns else 0
    renda_anual  = renda_mensal * 12
    yoc_medio    = safe_float(df["yoc"].mean())         if "yoc"          in df.columns else 0
    dy_medio     = (renda_anual / patrimonio * 100)     if patrimonio > 0 else 0
    num_ativos   = df["ticker"].nunique()               if "ticker"       in df.columns else 0

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
