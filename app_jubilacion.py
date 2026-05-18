# appjubilacion.py
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

st.set_page_config(page_title="Dashboard — Aposentadoria", page_icon="📊", layout="wide")

# CONSTANTES
META_MENSAL_USD_PADRAO = 2300.0
SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"
TICKERS_ERICSSON_PADRAO = ["ERIC", "ERIC-B.ST", "ERICB.ST"]

COLUNAS_IGNORAR = ["porcentagem", "porcentaje", "percent", "percentage", "%",
                   "dy medio", "dy_medio", "yield medio",
                   "total", "total con ecn", "total com ecn", "total ecn"]


def normalizar(s):
    s = str(s).strip().lower()
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def safe_float(v):
    if v is None:
        return None
    try:
        f = float(v)
        return None if np.isnan(f) else f
    except Exception:
        return None


def fmt_usd(v):
    v = safe_float(v)
    return "—" if v is None else f"${v:,.2f}"


def fmt_pct(v):
    v = safe_float(v)
    if v is None:
        return "—"
    return f"{'+' if v > 0 else ''}{v:.2f}%"


@st.cache_data(ttl=300)
def load_sheet(spreadsheet_id, gid):
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        if r.text.strip().startswith("<"):
            return None, "Planilha não pública"
        df = pd.read_csv(StringIO(r.text))
        df.columns = [normalizar(c) for c in df.columns]
        df = df.dropna(how="all")
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=300)
def get_rate(moeda):
    if moeda == "USD":
        return 1.0
    try:
        t = yf.Ticker(f"{moeda}USD=X")
        h = t.history(period="1d")
        if not h.empty:
            return float(h["Close"].iloc[-1])
    except Exception:
        pass
    return 1.0


@st.cache_data(ttl=300)
def get_ticker_info(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        hist = t.history(period="2d")
        moeda = info.get("currency", "USD").upper()
        preco_raw = info.get("currentPrice") or info.get("regularMarketPrice")
        preco_usd = None
        if preco_raw:
            taxa = get_rate(moeda)
            preco_usd = float(preco_raw) * taxa

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
        div_anual = preco_usd * dy if (dy and preco_usd) else None

        return {
            "ticker": ticker,
            "nome": info.get("shortName") or info.get("longName") or ticker,
            "preco_usd": preco_usd,
            "moeda_mercado": moeda,
            "variacao_pct": var_pct,
            "div_yield": dy,
            "div_anual_usd": div_anual,
        }
    except Exception as e:
        return {"ticker": ticker, "nome": ticker, "preco_usd": None,
                "moeda_mercado": "USD", "variacao_pct": None,
                "div_yield": None, "div_anual_usd": None, "erro": str(e)}


def is_ericsson(ticker, lista_eric):
    if not ticker:
        return False
    return str(ticker).strip().upper() in [t.strip().upper() for t in lista_eric]


def encontrar_col(df_cols, candidatos):
    cols = set(df_cols)
    for c in candidatos:
        if normalizar(c) in cols:
            return normalizar(c)
    return None


def parse_num(valor):
    """Converte valores BR/US para float."""
    if pd.isna(valor):
        return None
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if not s:
        return None
    # Tenta formato BR (1.234,56) e US (1,234.56)
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


# SIDEBAR
with st.sidebar:
    st.title("⚙️ Painel")
    st.markdown("### 🎯 Objetivos")
    meta_mensal = st.number_input("Meta renda mensal (USD)", 100.0, 50000.0, META_MENSAL_USD_PADRAO, 100.0)
    aporte_mensal = st.number_input("Aporte mensal (USD)", 0.0, 20000.0, 1500.0, 100.0)
    taxa_retorno = st.slider("Retorno anual (%)", 3.0, 15.0, 7.0, 0.5) / 100

    st.markdown("---")
    st.markdown("### 🏢 Ericsson (Paralela)")
    st.caption("Ações via plano da empresa, fora dos 100% da carteira principal.")
    tickers_eric_str = st.text_area("Tickers Ericsson", "\n".join(TICKERS_ERICSSON_PADRAO), height=80)
    tickers_eric = [t.strip() for t in tickers_eric_str.split("\n") if t.strip()]
    limite_rebal = st.slider("Alerta rebalanceamento (%)", 5.0, 50.0, 25.0, 1.0)

    st.markdown("---")
    st.markdown("### 📋 Planilha")
    sid = st.text_input("ID planilha", SPREADSHEET_ID)
    gid = st.text_input("GID aba", GID_PADRAO)

    if st.button("🔄 Atualizar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    debug = st.checkbox("🔧 Debug", False)


# HEADER
st.title("📊 Dashboard de Aposentadoria")
st.caption(f"Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")


# CARREGAR DADOS
df, erro = load_sheet(sid, gid)
if erro or df is None or df.empty:
    st.error(f"❌ Erro ao carregar planilha: {erro}")
    st.stop()

if debug:
    st.subheader("🔧 Debug")
    st.write("Colunas:", list(df.columns))
    st.dataframe(df.head(20))


# IDENTIFICAR COLUNAS
col_ticker = encontrar_col(df.columns, ["ticker", "tickers", "simbolo", "ativo"])
col_qtd = encontrar_col(df.columns, ["quantidade", "qtd", "qty", "shares", "acoes"])
col_pm = encontrar_col(df.columns, ["preco medio", "precio medio", "avg price", "custo medio"])

if not col_ticker:
    st.error("❌ Coluna de ticker não encontrada.")
    st.stop()


# FILTRAR ATIVOS
df_ok = df[df[col_ticker].notna()].copy()
df_ok = df_ok[~df_ok[col_ticker].astype(str).str.lower().str.strip().isin(COLUNAS_IGNORAR)]
df_ok[col_ticker] = df_ok[col_ticker].astype(str).str.strip()
df_ok = df_ok[df_ok[col_ticker] != ""]

if df_ok.empty:
    st.warning("⚠️ Nenhum ativo encontrado.")
    st.stop()


# BUSCAR DADOS DE MERCADO
ativos = []
with st.spinner("Buscando cotações..."):
    for _, row in df_ok.iterrows():
        ticker = str(row[col_ticker]).strip()
        info = get_ticker_info(ticker)

        qtd = parse_num(row[col_qtd]) if col_qtd else None
        pm = parse_num(row[col_pm]) if col_pm else None

        valor_atual = (qtd * info["preco_usd"]) if (qtd and info["preco_usd"]) else None
        custo = (qtd * pm) if (qtd and pm) else None
        lucro = (valor_atual - custo) if (valor_atual and custo) else None
        lucro_pct = ((lucro / custo) * 100) if (lucro is not None and custo) else None
        renda_mensal = (qtd * info["div_anual_usd"] / 12) if (qtd and info["div_anual_usd"]) else None

        ativos.append({
            "ticker": ticker,
            "nome": info["nome"],
            "moeda": info["moeda_mercado"],
            "qtd": qtd,
            "pm_usd": pm,
            "preco_usd": info["preco_usd"],
            "var_pct": info["variacao_pct"],
            "valor_atual": valor_atual,
            "custo_total": custo,
            "lucro": lucro,
            "lucro_pct": lucro_pct,
            "div_yield": info["div_yield"],
            "div_anual": info["div_anual_usd"],
            "renda_mensal": renda_mensal,
            "ericsson": is_ericsson(ticker, tickers_eric),
        })

df_ativos = pd.DataFrame(ativos)

if df_ativos.empty:
    st.warning("⚠️ Sem dados de ativos.")
    st.stop()


# SEPARAR PRINCIPAL VS ERICSSON
df_principal = df_ativos[~df_ativos["ericsson"]].copy()
df_eric = df_ativos[df_ativos["ericsson"]].copy()


# MÉTRICAS PRINCIPAIS
patrimonio = df_principal["valor_atual"].sum(skipna=True) or 0
custo_tot = df_principal["custo_total"].sum(skipna=True) or 0
lucro_tot = patrimonio - custo_tot if (patrimonio and custo_tot) else 0
renda_tot = df_principal["renda_mensal"].sum(skipna=True) or 0
patr_eric = df_eric["valor_atual"].sum(skipna=True) or 0
renda_eric = df_eric["renda_mensal"].sum(skipna=True) or