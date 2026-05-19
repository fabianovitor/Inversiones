# ============================================================
# market_data.py - Dados de mercado via yfinance
# ============================================================

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
    YFINANCE_OK = True
except ImportError:
    YFINANCE_OK = False


@st.cache_data(ttl=180)
def enriquecer_ativo(ticker: str) -> dict:
    """Busca dados de mercado de um ativo via yfinance."""
    if not YFINANCE_OK:
        return _dados_vazios()

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        preco_atual  = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        preco_ant    = info.get("previousClose") or preco_atual
        variacao_pct = ((preco_atual - preco_ant) / preco_ant * 100) if preco_ant else 0
        div_yield    = info.get("dividendYield") or 0
        nome         = info.get("longName") or info.get("shortName") or ticker

        return {
            "ticker"      : ticker,
            "nome"        : nome,
            "preco_atual" : float(preco_atual),
            "variacao_pct": float(variacao_pct),
            "div_yield"   : float(div_yield),
        }
    except Exception:
        return _dados_vazios(ticker)


@st.cache_data(ttl=180)
def historico_precos(ticker: str, periodo: str = "1y") -> pd.DataFrame:
    """Busca histórico de preços via yfinance."""
    if not YFINANCE_OK:
        return pd.DataFrame()

    try:
        t   = yf.Ticker(ticker)
        df  = t.history(period=periodo)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        return df[["Date", "Close"]].copy()
    except Exception:
        return pd.DataFrame()


def _dados_vazios(ticker: str = "") -> dict:
    return {
        "ticker"      : ticker,
        "nome"        : ticker or "N/A",
        "preco_atual" : 0.0,
        "variacao_pct": 0.0,
        "div_yield"   : 0.0,
    }
