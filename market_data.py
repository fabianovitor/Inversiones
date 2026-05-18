# ============================================================
# market_data.py - Busca de cotações e dividendos via yfinance
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
from config import CACHE_TTL_COTACOES, CACHE_TTL_DIVIDENDOS


# ============================================================
# BUSCAR COTAÇÕES ATUAIS
# ============================================================

@st.cache_data(ttl=CACHE_TTL_COTACOES, show_spinner=False)
def buscar_cotacao(ticker):
    """Busca cotação atual de um ticker.
    
    Args:
        ticker: símbolo da ação (ex: 'AAPL', 'ERIC')
    
    Returns:
        dict com: preco_atual, variacao_pct, moeda
        ou None se falhar
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        # Tenta diferentes campos para preço atual
        preco = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        
        if preco is None:
            # Fallback: pega último fechamento do histórico
            hist = t.history(period="5d")
            if not hist.empty:
                preco = float(hist["Close"].iloc[-1])
        
        if preco is None:
            return None
        
        # Calcula variação percentual
        prev_close = info.get("previousClose")
        variacao_pct = None
        if prev_close and preco:
            variacao_pct = ((preco - prev_close) / prev_close) * 100
        
        return {
            "preco_atual": float(preco),
            "variacao_pct": variacao_pct,
            "moeda": info.get("currency", "USD"),
            "nome_curto": info.get("shortName", ticker),
            "setor": info.get("sector", ""),
        }
    except Exception as e:
        print(f"[ERRO] Falha ao buscar {ticker}: {e}")
        return None


@st.cache_data(ttl=CACHE_TTL_COTACOES, show_spinner=False)
def buscar_cotacoes_lote(tickers):
    """Busca cotações de múltiplos tickers em lote (mais rápido).
    
    Args:
        tickers: lista de símbolos
    
    Returns:
        dict {ticker: {preco_atual, variacao_pct, ...}}
    """
    resultado = {}
    for ticker in tickers:
        if not ticker or pd.isna(ticker):
            continue
        cotacao = buscar_cotacao(ticker)
        if cotacao:
            resultado[ticker] = cotacao
    return resultado


# ============================================================
# BUSCAR DIVIDENDOS / DIVIDEND YIELD
# ============================================================

@st.cache_data(ttl=CACHE_TTL_DIVIDENDOS, show_spinner=False)
def buscar_dividend_yield(ticker):
    """Busca o Dividend Yield atual de um ticker.
    
    Args:
        ticker: símbolo da ação
    
    Returns:
        float: DY em formato decimal (0.05 = 5%) ou None
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info
        
        # Tenta diferentes campos
        dy = (
            info.get("dividendYield")
            or info.get("trailingAnnualDividendYield")
        )
        
        if dy is None:
            return None
        
        dy = float(dy)
        
        # yfinance às vezes retorna em % (5.0) e às vezes em decimal (0.05)
        # Normaliza para decimal
        if dy > 1:
            dy = dy / 100
        
        return dy
    except Exception as e:
        print(f"[ERRO] Falha ao buscar DY de {ticker}: {e}")
        return None


@st.cache_data(ttl=CACHE_TTL_DIVIDENDOS, show_spinner=False)
def buscar_dividendos_anuais(ticker):
    """Busca o total de dividendos pagos nos últimos 12 meses.
    
    Args:
        ticker: símbolo da ação
    
    Returns:
        float: dividendos por ação nos últimos 12 meses (USD) ou None
    """
    try:
        t = yf.Ticker(ticker)
        divs = t.dividends
        
        if divs.empty:
            return None
        
        # Pega últimos 12 meses
        um_ano_atras = pd.Timestamp.now(tz=divs.index.tz) - pd.DateOffset(years=1)
        divs_recentes = divs[divs.index >= um_ano_atras]
        
        if divs_recentes.empty:
            return None
        
        return float(divs_recentes.sum())
    except Exception as e:
        print(f"[ERRO] Falha ao buscar dividendos de {ticker}: {e}")
        return None


# ============================================================
# FUNÇÃO COMPLETA: ENRIQUECER DADOS DA CARTEIRA
# ============================================================

def enriquecer_ativo(ticker):
    """Busca todos os dados de mercado de um ativo.
    
    Args:
        ticker: símbolo da ação
    
    Returns:
        dict com: preco_atual, variacao_pct, div_yield, div_anual, setor
    """
    cotacao = buscar_cotacao(ticker)
    dy = buscar_dividend_yield(ticker)
    div_anual = buscar_dividendos_anuais(ticker)
    
    if cotacao is None:
        return {
            "preco_atual": None,
            "variacao_pct": None,
            "div_yield": dy,
            "div_anual": div_anual,
            "moeda": "USD",
            "nome_curto": ticker,
            "setor": "",
        }
    
    return {
        "preco_atual": cotacao["preco_atual"],
        "variacao_pct": cotacao["variacao_pct"],
        "div_yield": dy,
        "div_anual": div_anual,
        "moeda": cotacao["moeda"],
        "nome_curto": cotacao["nome_curto"],
        "setor": cotacao["setor"],
    }


# ============================================================
# FUNÇÃO DE TESTE (rodar manualmente para verificar)
# ============================================================

def testar_conexao():
    """Testa se yfinance está funcionando.
    
    Returns:
        bool: True se OK, False se falhou
    """
    try:
        dados = buscar_cotacao("AAPL")
        if dados and dados.get("preco_atual"):
            print(f"✅ yfinance OK - AAPL: ${dados['preco_atual']:.2f}")
            return True
        return False
    except Exception as e:
        print(f"❌ yfinance falhou: {e}")
        return False