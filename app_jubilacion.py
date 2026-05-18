# dashboard_aposentadoria.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import StringIO
import yfinance as yf
from datetime import datetime
import numpy as np
import unicodedata
import json
import io

st.set_page_config(
    page_title="Dashboard \u2014 Aposentadoria",
    page_icon="\ud83d\udcca",
    layout="wide",
    initial_sidebar_state="expanded"
)

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  CONSTANTES
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
META_MENSAL_USD_PADRAO = 2300.0
SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"

# Colunas agregadas/resumo da planilha que N\u00c3O devem aparecer como coluna por ativo
COLUNAS_AGREGADAS_IGNORAR = [
    "porcentagem", "porcentaje", "percent", "percentage", "%",
    "dy medio", "dy_medio", "yield medio",
    "total", "total con ecn", "total com ecn", "total ecn",
]

# Tickers padr\u00e3o tratados como "Ericsson" (carteira paralela)
TICKERS_ERICSSON_PADRAO = ["ERIC", "ERIC-B.ST", "ERICB.ST", "ERIC-A.ST", "ERICA.ST"]

LAYOUT_BASE = dict(
    plot_bgcolor="#f8fafc",
    paper_bgcolor="white",
    font=dict(color="#1e293b", size=13),
    margin=dict(t=60, b=60, l=60, r=60),
)


def layout_eixos(xaxis_title="", yaxis_title=""):
    return dict(
        **LAYOUT_BASE,
        xaxis=dict(
            title=dict(text=xaxis_title, font=dict(color="#1e293b", size=14)),
            tickfont=dict(color="#1e293b", size=12),
            linecolor="#94a3b8", gridcolor="#e2e8f0",
        ),
        yaxis=dict(
            title=dict(text=yaxis_title, font=dict(color="#1e293b", size=14)),
            tickfont=dict(color="#1e293b", size=12),
            linecolor="#94a3b8", gridcolor="#e2e8f0",
        ),
    )


def build_csv_url(spreadsheet_id, gid):
    return (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )


@st.cache_data(ttl=300)
def load_sheet_raw(spreadsheet_id, gid):
    url = build_csv_url(spreadsheet_id, gid)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=15, headers=headers)
        if response.status_code != 200:
            return "", f"HTTP_{response.status_code}", url
        content = response.text
        if content.strip().startswith("<!DOCTYPE") or content.strip().startswith("<html"):
            return "", "HTML_RESPONSE", url
        return content, None, url
    except Exception as e:
        return "", f"ERROR: {str(e)}", url


@st.cache_data(ttl=300)
def get_exchange_rate(from_currency, to_currency="USD"):
    if from_currency.upper() == to_currency.upper():
        return 1.0
    try:
        pair = f"{from_currency.upper()}{to_currency.upper()}=X"
        ticker = yf.Ticker(pair)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 1.0


@st.cache_data(ttl=300)
def get_all_rates():
    moedas = ["SEK", "EUR", "GBP", "BRL", "CAD", "CHF", "JPY", "NOK", "DKK"]
    rates = {"USD": 1.0}
    for moeda in moedas:
        rates[moeda] = get_exchange_rate(moeda, "USD")
    return rates


@st.cache_data(ttl=300)
def get_ticker_info(ticker, rates_tuple):
    rates = dict(rates_tuple)
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="2d")
        moeda_mercado = info.get("currency", "USD").upper()
        preco_raw = info.get("currentPrice") or info.get("regularMarketPrice", None)
        preco_usd = None
        if preco_raw:
            if moeda_mercado == "USD":
                preco_usd = float(preco_raw)
            else:
                taxa = rates.get(moeda_mercado, None)
                if taxa:
                    preco_usd = float(preco_raw) * taxa
                else:
                    preco_usd = float(preco_raw)

        variacao_pct = None
        if hist is not None and len(hist) >= 2:
            try:
                preco_ontem = float(hist["Close"].iloc[-2])
                preco_hoje = float(hist["Close"].iloc[-1])
                if preco_ontem > 0:
                    variacao_pct = ((preco_hoje - preco_ontem) / preco_ontem) * 100
            except Exception:
                pass
        elif hist is not None and len(hist) == 1:
            try:
                preco_hoje = float(hist["Close"].iloc[-1])
                preco_ontem_raw = info.get("previousClose") or info.get("regularMarketPreviousClose")
                if preco_ontem_raw:
                    preco_ontem = float(preco_ontem_raw)
                    if preco_ontem > 0:
                        variacao_pct = ((preco_hoje - preco_ontem) / preco_ontem) * 100
            except Exception:
                pass

        div_yield = info.get("dividendYield", None)
        div_anual_usd = None
        if div_yield and preco_usd:
            div_anual_usd = preco_usd * div_yield

        nome = info.get("shortName") or info.get("longName") or ticker
        return {
            "ticker": ticker,
            "nome": nome,
            "preco_usd": preco_usd,
            "moeda_mercado": moeda_mercado,
            "variacao_pct": variacao_pct,
            "div_yield": div_yield,
            "div_anual_usd": div_anual_usd,
            "info": info,
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "nome": ticker,
            "preco_usd": None,
            "moeda_mercado": "USD",
            "variacao_pct": None,
            "div_yield": None,
            "div_anual_usd": None,
            "info": {},
            "erro": str(e),
        }