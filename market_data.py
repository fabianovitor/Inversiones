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

# Taxa de conversão SEK -> USD (busca ao vivo ou fallback)
@st.cache_data(ttl=3600)
def get_sek_to_usd() -> float:
    """Busca taxa SEK/USD ao vivo."""
    if not YFINANCE_OK:
        return 0.092  # fallback aproximado
    try:
        ticker = yf.Ticker("SEKUSD=X")
        info = ticker.fast_info
        price = getattr(info, 'last_price', None)
        if price and price > 0:
            return float(price)
        # Tenta histórico
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 0.092  # fallback


def _to_usd(valor, currency: str) -> float:
    """Converte valor para USD se necessário."""
    if not valor or valor == 0:
        return 0.0
    currency = (currency or "USD").upper()
    if currency == "USD":
        return float(valor)
    elif currency == "SEK":
        rate = get_sek_to_usd()
        return float(valor) * rate
    else:
        # Para outras moedas, tenta buscar a taxa
        if YFINANCE_OK:
            try:
                ticker = yf.Ticker(f"{currency}USD=X")
                hist = ticker.history(period="1d")
                if not hist.empty:
                    rate = float(hist["Close"].iloc[-1])
                    return float(valor) * rate
            except Exception:
                pass
        return float(valor)  # fallback sem conversão


@st.cache_data(ttl=180)
def enriquecer_ativo(ticker: str) -> dict:
    """Busca dados de mercado de um ativo via yfinance. Retorna valores em USD."""
    if not YFINANCE_OK:
        return _dados_vazios(ticker)

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        # Detecta moeda do ativo
        currency = info.get("currency", "USD")

        preco_raw    = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        preco_ant    = info.get("previousClose") or preco_raw
        variacao_pct = ((preco_raw - preco_ant) / preco_ant * 100) if preco_ant else 0
        div_yield    = info.get("dividendYield") or 0
        nome         = info.get("longName") or info.get("shortName") or ticker

        # Converte preço para USD
        preco_usd = _to_usd(preco_raw, currency)
        preco_ant_usd = _to_usd(preco_ant, currency)
        variacao_pct_usd = ((preco_usd - preco_ant_usd) / preco_ant_usd * 100) if preco_ant_usd else 0

        return {
            "ticker"      : ticker,
            "nome"        : nome,
            "preco_atual" : preco_usd,
            "variacao_pct": float(variacao_pct_usd),
            "div_yield"   : float(div_yield),
            "currency"    : currency,
        }
    except Exception:
        return _dados_vazios(ticker)


@st.cache_data(ttl=180)
def historico_precos(ticker: str, periodo: str = "1y") -> pd.DataFrame:
    """Busca histórico de preços via yfinance. Retorna preços em USD."""
    if not YFINANCE_OK:
        return pd.DataFrame()

    try:
        t   = yf.Ticker(ticker)
        info = t.info or {}
        currency = info.get("currency", "USD")

        df  = t.history(period=periodo)
        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        result = df[["Date", "Close"]].copy()

        # Converte para USD se necessário
        if currency != "USD":
            rate = 1.0
            if currency == "SEK":
                rate = get_sek_to_usd()
            elif YFINANCE_OK:
                try:
                    fx = yf.Ticker(f"{currency}USD=X")
                    fx_hist = fx.history(period="1d")
                    if not fx_hist.empty:
                        rate = float(fx_hist["Close"].iloc[-1])
                except Exception:
                    pass
            result["Close"] = result["Close"] * rate

        return result
    except Exception:
        return pd.DataFrame()


def _dados_vazios(ticker: str = "") -> dict:
    return {
        "ticker"      : ticker,
        "nome"        : ticker or "N/A",
        "preco_atual" : 0.0,
        "variacao_pct": 0.0,
        "div_yield"   : 0.0,
        "currency"    : "USD",
    }
