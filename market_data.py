# ============================================================
# market_data.py - Dados de mercado via yfinance
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd

from config import CACHE_TTL_MERCADO
from utils import safe_float, safe_div


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

@st.cache_data(ttl=CACHE_TTL_MERCADO, show_spinner=False)
def enriquecer_ativo(ticker: str) -> dict:
    """Busca dados de mercado de um ticker via yfinance.
    
    Args:
        ticker: Símbolo do ativo (ex: "AAPL", "ERIC")
    
    Returns:
        Dicionário com dados de mercado:
        {
            "preco_atual"  : float,
            "variacao_pct" : float,
            "div_yield"    : float,
            "div_anual"    : float,
            "setor"        : str,
            "nome"         : str,
            "moeda"        : str,
            "market_cap"   : float,
            "pe_ratio"     : float,
            "beta"         : float,
        }
    """
    resultado_vazio = {
        "preco_atual"  : 0.0,
        "variacao_pct" : 0.0,
        "div_yield"    : 0.0,
        "div_anual"    : 0.0,
        "setor"        : "",
        "nome"         : ticker,
        "moeda"        : "USD",
        "market_cap"   : 0.0,
        "pe_ratio"     : 0.0,
        "beta"         : 0.0,
    }

    if not ticker or ticker.strip() == "":
        return resultado_vazio

    try:
        ativo = yf.Ticker(ticker.strip().upper())
        info  = ativo.info or {}

        # --- Preço atual ---
        preco = (
            safe_float(info.get("currentPrice"))
            or safe_float(info.get("regularMarketPrice"))
            or safe_float(info.get("previousClose"))
            or 0.0
        )

        # --- Variação do dia ---
        preco_abertura = safe_float(info.get("open") or info.get("regularMarketOpen"))
        if preco > 0 and preco_abertura > 0:
            variacao = safe_div(preco - preco_abertura, preco_abertura) * 100
        else:
            variacao = safe_float(
                info.get("regularMarketChangePercent")
            )

        # --- Dividendos ---
        div_yield = safe_float(info.get("dividendYield"))     # ex: 0.0523
        div_anual = safe_float(info.get("trailingAnnualDividendRate"))  # por ação

        # Fallback: calcular div_anual a partir do yield e preço
        if div_anual == 0.0 and div_yield > 0 and preco > 0:
            div_anual = div_yield * preco

        # --- Informações gerais ---
        setor = (
            info.get("sector")
            or info.get("category")
            or info.get("fundFamily")
            or ""
        )
        nome       = info.get("shortName") or info.get("longName") or ticker
        moeda      = info.get("currency") or "USD"
        market_cap = safe_float(info.get("marketCap"))
        pe_ratio   = safe_float(info.get("trailingPE") or info.get("forwardPE"))
        beta       = safe_float(info.get("beta"))

        return {
            "preco_atual"  : preco,
            "variacao_pct" : variacao,
            "div_yield"    : div_yield,
            "div_anual"    : div_anual,
            "setor"        : setor,
            "nome"         : nome,
            "moeda"        : moeda,
            "market_cap"   : market_cap,
            "pe_ratio"     : pe_ratio,
            "beta"         : beta,
        }

    except Exception:
        return resultado_vazio


# ============================================================
# HISTÓRICO DE PREÇOS
# ============================================================

@st.cache_data(ttl=CACHE_TTL_MERCADO, show_spinner=False)
def historico_precos(ticker: str,
                     periodo: str = "1y",
                     intervalo: str = "1d") -> pd.DataFrame:
    """Busca histórico de preços de um ticker.
    
    Args:
        ticker   : Símbolo do ativo
        periodo  : "1mo", "3mo", "6mo", "1y", "2y", "5y"
        intervalo: "1d", "1wk", "1mo"
    
    Returns:
        DataFrame com colunas: Date, Open, High, Low, Close, Volume
    """
    try:
        ativo = yf.Ticker(ticker.strip().upper())
        df = ativo.history(period=periodo, interval=intervalo)

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        df.columns = [str(c).strip() for c in df.columns]
        return df

    except Exception:
        return pd.DataFrame()


# ============================================================
# MÚLTIPLOS TICKERS DE UMA VEZ
# ============================================================

@st.cache_data(ttl=CACHE_TTL_MERCADO, show_spinner=False)
def precos_em_lote(tickers: list) -> dict:
    """Busca preço atual de vários tickers de uma vez.
    
    Mais eficiente que chamar enriquecer_ativo() em loop
    quando só precisa do preço.
    
    Args:
        tickers: Lista de tickers (ex: ["AAPL", "MSFT", "ERIC"])
    
    Returns:
        Dicionário {ticker: preco_atual}
    """
    resultado = {t: 0.0 for t in tickers}

    if not tickers:
        return resultado

    try:
        tickers_str = " ".join([t.strip().upper() for t in tickers])
        dados = yf.download(
            tickers_str,
            period="2d",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )

        if dados.empty:
            return resultado

        # Extrai último preço de fechamento
        if isinstance(dados.columns, pd.MultiIndex):
            # Múltiplos tickers
            close = dados["Close"]
            for ticker in tickers:
                t = ticker.strip().upper()
                if t in close.columns:
                    ultimo = close[t].dropna()
                    if not ultimo.empty:
                        resultado[ticker] = safe_float(ultimo.iloc[-1])
        else:
            # Ticker único
            if len(tickers) == 1:
                ultimo = dados["Close"].dropna()
                if not ultimo.empty:
                    resultado[tickers[0]] = safe_float(ultimo.iloc[-1])

        return resultado

    except Exception:
        return resultado


# ============================================================
# VALIDAÇÃO DE TICKER
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def ticker_valido(ticker: str) -> bool:
    """Verifica se um ticker existe no yfinance.
    
    Args:
        ticker: Símbolo a verificar
    
    Returns:
        True se válido, False se não encontrado
    """
    try:
        ativo = yf.Ticker(ticker.strip().upper())
        info = ativo.info
        return bool(info and info.get("symbol"))
    except Exception:
        return False
