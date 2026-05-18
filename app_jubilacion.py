# ============================================================
# DASHBOARD DE APOSENTADORIA - ARQUIVO ÚNICO COMPLETO
# ============================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import StringIO
import yfinance as yf
from datetime import datetime
import numpy as np
import unicodedata

st.set_page_config(page_title="Dashboard Aposentadoria", layout="wide")

SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"
TICKER_ERICSSON = "ERIC-B.ST"
COLS_IGNORAR = ["porcentagem", "porcentaje", "percent", "%", "dy medio", "total", "total con ecn", "total com ecn"]


def norm(s):
    s = str(s).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def safe_float(v):
    if v is None or pd.isna(v):
        return None
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except Exception:
        return None


def parse_num(v):
    if pd.isna(v):
        return None
    s = str(v).strip().replace("$", "").replace(" ", "").replace("US", "")
    if not s or s in ("-", "—", "nan", "None"):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def fmt_usd(v):
    v = safe_float(v)
    return "-" if v is None else f"${v:,.2f}"


def fmt_pct(v):
    v = safe_float(v)
    if v is None:
        return "-"
    return f"{'+' if v > 0 else ''}{v:.2f}%"


@st.cache_data(ttl=300)
def load_sheet(sid, gid):
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        if r.text.strip().startswith("<"):
            return None, "Planilha nao publica"
        df = pd.read_csv(StringIO(r.text))
        df.columns = [norm(c) for c in df.columns]
        df = df.dropna(how="all")
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=300)
def get_rate(moeda):
    if moeda == "USD":
        return 1.0
    try:
        h = yf.Ticker(f"{moeda}USD=X").history(period="1d")
        if not h.empty:
            return float(h["Close"].iloc[-1])
    except Exception:
        pass
    return 1.0


@st.cache_data(ttl=300)
def get_ticker(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period="5d")
        moeda = (info.get("currency") or "USD").upper()
        rate = get_rate(moeda)
        preco_raw = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        if not preco_raw and hist is not None and not hist.empty:
            preco_raw = float(hist["Close"].iloc[-1])
        preco_usd = float(preco_raw) * rate if preco_raw else None
        var_pct = None
        if hist is not None and len(hist) >= 2:
            try:
                ontem = float(hist["Close"].iloc[-2])
                hoje = float(hist["Close"].iloc[-1])
                if ontem > 0:
                    var_pct = ((hoje - ontem) / ontem) * 100
            except Exception:
                pass
        dy = info.get("dividendYield")
        if dy and dy > 1:
            dy = dy / 100
        div_rate = info.get("dividendRate")
        div_anual_usd = None
        if div_rate:
            div_anual_usd = float(div_rate) * rate
        elif dy and preco_usd:
            div_anual_usd = preco_usd * dy
        return {
            "ticker": ticker,
            "nome": info.get("shortName") or info.get("longName") or ticker,
            "preco_usd": preco_usd,
            "moeda": moeda,
            "var_pct": var_pct,
            "div_yield": dy,
            "div_anual_usd": div_anual_usd,
        }
    except Exception:
        return {"ticker": ticker, "nome": ticker, "preco_usd": None, "moeda": "USD", "var_pct": None, "div_yield": None, "div_anual_usd": None}


def encontrar_col(cols, candidatos):
    cs = set(cols)
    for c in candidatos:
        if norm(c) in cs:
            return norm(c)
    return None


# SIDEBAR
with st.sidebar:
    st.title("Painel")
    meta_mensal = st.number_input("Meta renda mensal (USD)", 100.0, 50000.0, 2300.0, 100.0)
    aporte_mensal = st.number_input("Aporte mensal (USD)", 0.0, 20000.0, 1500.0, 100.0)
    taxa_retorno = st.slider("Retorno anual (%)", 3.0, 15.0, 7.0, 0.5) / 100
    st.markdown("---")
    st.caption(f"Ericsson ({TICKER_ERICSSON}) tratada como carteira paralela.")
    st.markdown("---")
    sid = st.text_input("ID planilha", SPREADSHEET_ID)
    gid = st.text_input("GID", GID_PADRAO)
    if st.button("Atualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    debug = st.checkbox("Debug", False)

st.title("Dashboard de Aposentadoria")
st.caption(f"Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

df, erro = load_sheet(sid, gid)
if erro or df is None or df.empty:
    st.error(f"Erro ao carregar planilha: {erro}")
    st.stop()

col_ticker = encontrar_col(df.columns, ["ticker", "tickers", "simbolo", "ativo"])
col_qtd = encontrar_col(df.columns, ["quantidade", "qtd", "qty", "shares", "acoes", "cantidad"])
col_pm = encontrar_col(df.columns, ["preco medio", "precio medio", "avg price", "custo medio", "preco medio usd", "precio medio usd", "pm", "pm usd"])

if debug:
    st.subheader("DEBUG - Informacoes detectadas")
    st.write(f"**Coluna ticker:** `{col_ticker}` | **Quantidade:** `{col_qtd}` | **PM:** `{col_pm}`")
    st.write("**Todas as colunas:**", list(df.columns))
    st.dataframe(df.head(20))
    csv_planilha = df.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV da planilha (debug)", csv_planilha, "planilha_debug.csv", "text/csv")

if not col_ticker:
    st.error("Coluna de ticker nao encontrada. Ative o Debug.")
    st.stop()

df_ok = df[df[col_ticker].notna()].copy()
df_ok = df_ok[~df_ok[col_ticker].astype(str).str.lower().str.strip().isin(COLS_IGNORAR)]
df_ok[col_ticker] = df_ok[col_ticker].astype(str).str.strip()
df_ok = df_ok[df_ok[col_ticker] != ""]

if df_ok.empty:
    st.warning("Nenhum ativo encontrado.")
    st.stop()

ativos = []
with st.spinner("Buscando cotacoes no Yahoo Finance..."):
    for _, row in df_ok.iterrows():
        ticker = str(row[col_ticker]).strip()
        info = get_ticker(ticker)
        qtd = parse_num(row[col_qtd]) if col_qtd else None
        pm = parse_num(row[col_pm]) if col_pm else None
        valor = (qtd * info["preco_usd"]) if (qtd and info["preco_usd"]) else None
        custo = (qtd * pm) if (qtd and pm) else None
        lucro = (valor - custo) if (valor is not None and custo is not None) else None
        lucro_pct = ((lucro / custo) * 100) if (lucro is not None and custo) else None
        renda = (qtd * info["div_anual_usd"] / 12) if (qtd and info["div_anual_usd"]) else None
        ativos.append({
            "ticker": ticker, "nome": info["nome"], "moeda": info["moeda"],
            "qtd": qtd, "pm_usd": pm, "preco_usd": info["preco_usd"],
            "var_pct": info["var_pct"], "valor_atual": valor,
            "custo_total": custo, "lucro": lucro, "lucro_pct": lucro_pct,
            "div_yield": info["div_yield"], "renda_mensal": renda,
            "ericsson": str(ticker).strip().upper() == TICKER_ERICSSON.upper(),
        })

dfa = pd.DataFrame(ativos)

if debug:
    st.subheader("DEBUG - Dados completos buscados")
    st.dataframe(dfa)
    csv_debug = dfa.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV dos dados (debug)", csv_debug, "dados_debug.csv", "text/csv")

df_principal = dfa[~dfa["ericsson"]].copy()
df_eric = dfa[dfa["ericsson"]].copy()

patrimonio = df_principal["valor_atual"].sum(skipna=True) or 0
custo_tot = df_principal["custo_total"].sum(skipna=True) or 0
lucro_tot = patrimonio - custo_tot if (patrimonio and custo_tot) else 0
renda_tot = df_principal["renda_mensal"].sum(skipna=True) or 0
patr_eric = df_eric["valor_atual"].sum(skipna=True) or