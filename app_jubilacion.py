# ============================================================
# DASHBOARD DE APOSENTADORIA - ETAPA 1 (Correções e Ajustes)
# ============================================================
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

st.set_page_config(
    page_title="Dashboard Aposentadoria",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Dashboard de Aposentadoria v2.0 - Etapa 1"
    }
)

# ============================================================
# CONSTANTES
# ============================================================
SPREADSHEET_ID = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GID_PADRAO = "79928919"
TICKER_ERICSSON = "ERIC-B.ST"

MAPEAMENTO_TICKERS = {
    "ERICB": "ERIC-B.ST",
    "ERIC-B": "ERIC-B.ST",
    "ERICSSON": "ERIC-B.ST",
    "STO:ERIC-B": "ERIC-B.ST",
}

COLS_IGNORAR = [
    "porcentagem", "porcentaje", "percent", "%",
    "dy medio", "total", "total con ecn", "total com ecn"
]

# Limites de validação
DY_MAXIMO_RAZOAVEL = 0.20  # 20% - acima disso, recalcular
DY_MINIMO_RAZOAVEL = 0.001  # 0.1% - abaixo disso, ignorar

# ============================================================
# FUNÇÕES AUXILIARES - NORMALIZAÇÃO
# ============================================================
def norm(s):
    """Normaliza string: minúsculas, sem acentos, sem espaços extras."""
    s = str(s).strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def limpar_ticker(ticker_str):
    """Remove prefixos de bolsa (NYSEARCA:, NASDAQ:, NYSE:, OTCMKTS:, STO:)."""
    t = str(ticker_str).strip().upper()
    if t in MAPEAMENTO_TICKERS:
        return MAPEAMENTO_TICKERS[t]
    prefixos = ["NYSEARCA:", "NASDAQ:", "NYSE:", "OTCMKTS:", "BATS:", "AMEX:"]
    for prefixo in prefixos:
        if t.startswith(prefixo):
            return t.replace(prefixo, "")
    if t.startswith("STO:"):
        return t.replace("STO:", "") + ".ST"
    return t


# ============================================================
# FUNÇÕES AUXILIARES - PARSE E FORMATAÇÃO
# ============================================================
def safe_float(v):
    """Converte para float de forma segura, retorna None se inválido."""
    if v is None or pd.isna(v):
        return None
    try:
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def parse_num(v):
    """Parse de números com suporte a formatos BR e US."""
    if pd.isna(v):
        return None
    s = str(v).strip().replace("$", "").replace(" ", "").replace("US", "")
    if not s or s in ("-", "—", "nan", "None", "null"):
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
    except (ValueError, TypeError):
        return None


def fmt_usd(v):
    """Formata valor em USD."""
    v = safe_float(v)
    return "-" if v is None else f"${v:,.2f}"


def fmt_pct(v, com_sinal=True):
    """Formata percentual."""
    v = safe_float(v)
    if v is None:
        return "-"
    if com_sinal:
        return f"{'+' if v > 0 else ''}{v:.2f}%"
    return f"{v:.2f}%"


def fmt_pct_dy(v):
    """Formata DY (dividend yield) - já em decimal (0.05 = 5%)."""
    v = safe_float(v)
    if v is None or v == 0:
        return "-"
    return f"{v*100:.2f}%"


def cor_lucro(v):
    """Retorna cor baseada no valor (verde positivo, vermelho negativo)."""
    v = safe_float(v)
    if v is None:
        return "gray"
    return "green" if v >= 0 else "red"


def fmt_lucro_html(v, sufixo=""):
    """Formata lucro com cor HTML."""
    v = safe_float(v)
    if v is None:
        return '<span style="color:gray">-</span>'
    cor = "green" if v >= 0 else "red"
    sinal = "+" if v >= 0 else ""
    if sufixo == "%":
        return f'<span style="color:{cor}; font-weight:bold">{sinal}{v:.2f}%</span>'
    return f'<span style="color:{cor}; font-weight:bold">{sinal}${v:,.2f}</span>'


# CONTINUA NA PARTE 2/4
# CONTINUAÇÃO DA PARTE 1

# ============================================================
# FUNÇÕES DE CARREGAMENTO DE DADOS
# ============================================================
@st.cache_data(ttl=300)
def load_sheet(sid, gid):
    """Carrega planilha do Google Sheets."""
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        if r.text.strip().startswith("<"):
            return None, "Planilha nao publica - verifique permissoes"
        df = pd.read_csv(StringIO(r.text))
        df.columns = [norm(c) for c in df.columns]
        df = df.dropna(how="all")
        return df, None
    except requests.Timeout:
        return None, "Timeout ao carregar planilha"
    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=300)
def get_rate(moeda):
    """Obtém taxa de câmbio para USD."""
    if moeda == "USD":
        return 1.0
    try:
        h = yf.Ticker(f"{moeda}USD=X").history(period="1d")
        if not h.empty:
            return float(h["Close"].iloc[-1])
    except Exception:
        pass
    return 1.0


def validar_dy(dy_raw, div_rate, preco_usd, rate):
    """
    Valida e corrige Dividend Yield anômalo.
    Se DY > 20%, recalcula via dividendRate / preço.
    Retorna DY em formato decimal (0.05 = 5%).
    """
    dy = safe_float(dy_raw)

    # Yahoo às vezes retorna em % (ex: 5.0 ao invés de 0.05)
    if dy and dy > 1:
        dy = dy / 100

    # Validação: se DY muito alto (>20%), tentar recalcular
    if dy and dy > DY_MAXIMO_RAZOAVEL:
        if div_rate and preco_usd and preco_usd > 0:
            dy_recalculado = (float(div_rate) * rate) / preco_usd
            if dy_recalculado <= DY_MAXIMO_RAZOAVEL:
                return dy_recalculado, True  # True = foi corrigido
        # Se não conseguir recalcular, marcar como suspeito
        return dy, True

    # DY muito baixo - provavelmente erro
    if dy and dy < DY_MINIMO_RAZOAVEL:
        return None, False

    return dy, False


@st.cache_data(ttl=300)
def get_ticker(ticker):
    """
    Busca informações do ticker no Yahoo Finance.
    Inclui validação automática de DY anômalo.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period="5d")
        moeda = (info.get("currency") or "USD").upper()
        rate = get_rate(moeda)

        # Preço atual
        preco_raw = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        if not preco_raw and hist is not None and not hist.empty:
            preco_raw = float(hist["Close"].iloc[-1])
        preco_usd = float(preco_raw) * rate if preco_raw else None

        # Variação diária
        var_pct = None
        if hist is not None and len(hist) >= 2:
            try:
                ontem = float(hist["Close"].iloc[-2])
                hoje = float(hist["Close"].iloc[-1])
                if ontem > 0:
                    var_pct = ((hoje - ontem) / ontem) * 100
            except Exception:
                pass

        # Dividend Yield com validação
        dy_raw = info.get("dividendYield")
        div_rate = info.get("dividendRate")
        dy, dy_corrigido = validar_dy(dy_raw, div_rate, preco_usd, rate)

        # Dividendo anual em USD
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
            "dy_corrigido": dy_corrigido,
            "setor": info.get("sector", "N/A"),
            "industria": info.get("industry", "N/A"),
        }
    except Exception as e:
        return {
            "ticker": ticker,
            "nome": ticker,
            "preco_usd": None,
            "moeda": "USD",
            "var_pct": None,
            "div_yield": None,
            "div_anual_usd": None,
            "dy_corrigido": False,
            "setor": "N/A",
            "industria": "N/A",
        }


def encontrar_col(cols, candidatos):
    """Encontra coluna por lista de candidatos (normalizado)."""
    cs = set(cols)
    for c in candidatos:
        if norm(c) in cs:
            return norm(c)
    return None


# ============================================================
# TOOLTIPS E EXPLICAÇÕES
# ============================================================
TOOLTIPS = {
    "patrimonio": "Soma do valor atual de todos os ativos da carteira principal (excluindo Ericsson).",
    "renda_mensal": "Estimativa de renda mensal baseada nos dividendos anuais dos ativos / 12.",
    "ericsson": "Patrimônio em ações da Ericsson (carteira separada/paralela).",
    "meta": "Sua meta de renda mensal passiva para se aposentar.",
    "dy": "Dividend Yield: rendimento anual em dividendos como % do preço atual.",
    "yoc": "Yield on Cost: rendimento anual sobre o preço de compra (não o atual).",
    "fire": "Financial Independence Retire Early: patrimônio necessário para viver de renda (regra dos 4%).",
    "var_pct": "Variação percentual do preço comparado ao último dia útil.",
    "lucro": "Diferença entre valor atual da posição e custo total investido.",
}


# CONTINUA NA PARTE 3/4
# CONTINUAÇÃO DA PARTE 2

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("⚙️ Painel de Controle")

    st.markdown("### 🎯 Metas")
    meta_mensal = st.number_input(
        "Meta renda mensal (USD)",
        100.0, 50000.0, 2300.0, 100.0,
        help=TOOLTIPS["meta"]
    )
    aporte_mensal = st.number_input(
        "Aporte mensal (USD)",
        0.0, 20000.0, 1500.0, 100.0,
        help="Quanto você consegue aportar todo mês."
    )
    taxa_retorno = st.slider(
        "Retorno anual esperado (%)",
        3.0, 15.0, 7.0, 0.5,
        help="Taxa anual média esperada (mercado histórico: 7-10%)."
    ) / 100

    st.markdown("---")
    st.markdown("### 📊 Fonte de Dados")
    st.caption(f"Ericsson ({TICKER_ERICSSON}) é tratada como carteira paralela.")
    sid = st.text_input("ID da planilha", SPREADSHEET_ID)
    gid = st.text_input("GID", GID_PADRAO)

    if st.button("🔄 Atualizar Dados", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 🐛 Debug")
    debug = st.checkbox("Modo Debug", False, help="Mostra informações técnicas de carregamento.")

    # Placeholder para botões de download de debug (preenchido após carregamento)
    debug_download_placeholder = st.empty()

# ============================================================
# CABEÇALHO PRINCIPAL
# ============================================================
st.title("💰 Dashboard de Aposentadoria")
st.caption(f"📅 Atualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.markdown("---")

# ============================================================
# CARREGAMENTO DA PLANILHA
# ============================================================
df, erro = load_sheet(sid, gid)
if erro or df is None or df.empty:
    st.error(f"❌ Erro ao carregar planilha: {erro}")
    st.stop()

col_ticker = encontrar_col(df.columns, ["ticker", "tickers", "ticket", "simbolo", "ativo"])
col_qtd = encontrar_col(df.columns, ["quantidade", "qtd", "qty", "shares", "acoes", "cantidad", "cant", "cant."])
col_pm = encontrar_col(df.columns, [
    "preco medio", "precio medio", "avg price", "custo medio",
    "preco medio usd", "precio medio usd", "pm", "pm usd",
    "pcio compra", "pcio. compra", "precio compra"
])

if not col_ticker:
    st.error("❌ Coluna de ticker não encontrada. Ative o Debug para investigar.")
    st.stop()

# ============================================================
# FILTRAGEM E PROCESSAMENTO
# ============================================================
df_ok = df[df[col_ticker].notna()].copy()
df_ok = df_ok[~df_ok[col_ticker].astype(str).str.lower().str.strip().isin(COLS_IGNORAR)]
df_ok[col_ticker] = df_ok[col_ticker].astype(str).str.strip()
df_ok = df_ok[df_ok[col_ticker] != ""]

if df_ok.empty:
    st.warning("⚠️ Nenhum ativo encontrado.")
    st.stop()

# Busca cotações
ativos = []
with st.spinner("🔍 Buscando cotações no Yahoo Finance..."):
    for _, row in df_ok.iterrows():
        ticker_original = str(row[col_ticker]).strip().upper()
        ticker = limpar_ticker(ticker_original)
        info = get_ticker(ticker)
        qtd = parse_num(row[col_qtd]) if col_qtd else None
        pm = parse_num(row[col_pm]) if col_pm else None
        valor = (qtd * info["preco_usd"]) if (qtd and info["preco_usd"]) else None
        custo = (qtd * pm) if (qtd and pm) else None
        lucro = (valor - custo) if (valor is not None and custo is not None) else None
        lucro_pct = ((lucro / custo) * 100) if (lucro is not None and custo) else None
        renda = (qtd * info["div_anual_usd"] / 12) if (qtd and info["div_anual_usd"]) else None
        # Yield on Cost (YOC)
        yoc = None
        if pm and info["div_anual_usd"] and pm > 0:
            yoc = info["div_anual_usd"] / pm

        ativos.append({
            "ticker": ticker,
            "nome": info["nome"],
            "moeda": info["moeda"],
            "qtd": qtd,
            "pm_usd": pm,
            "preco_usd": info["preco_usd"],
            "var_pct": info["var_pct"],
            "valor_atual": valor,
            "custo_total": custo,
            "lucro": lucro,
            "lucro_pct": lucro_pct,
            "div_yield": info["div_yield"],
            "yoc": yoc,
            "renda_mensal": renda,
            "dy_corrigido": info["dy_corrigido"],
            "setor": info["setor"],
            "ericsson": ticker.upper() == TICKER_ERICSSON.upper() or "ERIC" in ticker_original,
        })

dfa = pd.DataFrame(ativos)

# Separar carteira principal e Ericsson
df_principal = dfa[~dfa["ericsson"]].copy()
df_eric = dfa[dfa["ericsson"]].copy()

# Cálculos agregados
patrimonio = df_principal["valor_atual"].sum(skipna=True) or 0
custo_tot = df_principal["custo_total"].sum(skipna=True) or 0
lucro_tot = patrimonio - custo_tot if (patrimonio and custo_tot) else 0
lucro_pct_tot = (lucro_tot / custo_tot * 100) if custo_tot else 0
renda_tot = df_principal["renda_mensal"].sum(skipna=True) or 0
patr_eric = df_eric["valor_atual"].sum(skipna=True) or 0
renda_eric = df_eric["renda_mensal"].sum(skipna=True) or 0

# ============================================================
# DEBUG NA SIDEBAR (após carregamento dos dados)
# ============================================================
if debug:
    with debug_download_placeholder.container():
        st.markdown("**📥 Downloads Debug:**")
        csv_planilha = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 CSV Planilha",
            csv_planilha,
            "planilha_debug.csv",
            "text/csv",
            use_container_width=True,
            key="dl_planilha"
        )
        csv_dados = dfa.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 CSV Dados",
            csv_dados,
            "dados_debug.csv",
            "text/csv",
            use_container_width=True,
            key="dl_dados"
        )
        st.caption(f"**Ticker:** `{col_ticker}`")
        st.caption(f"**Qtd:** `{col_qtd}`")
        st.caption(f"**PM:** `{col_pm}`")

# CONTINUA NA PARTE 4/4
# CONTINUA\u00c7\u00c3O DA PARTE 3

# ============================================================
# FUN\u00c7\u00d5ES DE ESTILIZA\u00c7\u00c3O
# ============================================================
def colorir_lucro(val):
    """Aplica cor verde/vermelho baseado no valor."""
    if pd.isna(val):
        return "color: gray"
    try:
        v = float(val)
        if v > 0:
            return "color: #00C853; font-weight: bold"
        elif v < 0:
            return "color: #D50000; font-weight: bold"
        return "color: gray"
    except:
        return ""


def aplicar_estilo_df(styled_df, colunas_cor):
    """Aplica estilo de cor compat\u00edvel com pandas novo (map) e antigo (applymap)."""
    try:
        return styled_df.map(colorir_lucro, subset=colunas_cor)
    except AttributeError:
        return styled_df.applymap(colorir_lucro, subset=colunas_cor)


# ============================================================
# M\u00c9TRICAS PRINCIPAIS (sempre vis\u00edveis no topo)
# ============================================================
st.subheader("\ud83d\udcca Vis\u00e3o Geral")

c1, c2, c3, c4 = st.columns(4)

with c1:
    delta_pct = f"{lucro_pct_tot:+.2f}%" if custo_tot else None
    st.metric(
        label="\ud83d\udcbc Patrim\u00f4nio Principal",
        value=fmt_usd(patrimonio),
        delta=delta_pct,
        help=TOOLTIPS["patrimonio"]
    )

with c2:
    pct_meta = (renda_tot / meta_mensal * 100) if meta_mensal else 0
    st.metric(
        label="\ud83d\udcb5 Renda Mensal Estimada",
        value=fmt_usd(renda_tot),
        delta=f"{pct_meta:.1f}% da meta",
        help=TOOLTIPS["renda_mensal"]
    )

with c3:
    delta_eric = f"+{fmt_usd(renda_eric)}/m\u00eas" if renda_eric else None
    st.metric(
        label="\ud83d\udef0\ufe0f Ericsson (Paralela)",
        value=fmt_usd(patr_eric),
        delta=delta_eric,
        help=TOOLTIPS["ericsson"]
    )

with c4:
    if meta_mensal > renda_tot:
        delta_meta = f"Faltam {fmt_usd(meta_mensal - renda_tot)}"
        st.metric(
            label="\ud83c\udfaf Meta Mensal",
            value=fmt_usd(meta_mensal),
            delta=delta_meta,
            delta_color="inverse",
            help=TOOLTIPS["meta"]
        )
    else:
        st.metric(
            label="\ud83c\udfaf Meta Mensal",
            value=fmt_usd(meta_mensal),
            delta="\u2705 Atingida!",
            help=TOOLTIPS["meta"]
        )

# Barra de progresso visual da meta
st.markdown("##### \ud83d\udcc8 Progresso at\u00e9 a Meta de Renda Mensal")
progresso = min(renda_tot / meta_mensal, 1.0) if meta_mensal else 0
st.progress(progresso, text=f"{renda_tot/meta_mensal*100:.1f}% \u2014 {fmt_usd(renda_tot)} de {fmt_usd(meta_mensal)}")

st.markdown("---")

# ============================================================
# LAYOUT EM ABAS
# ============================================================
tab_carteira, tab_ericsson, tab_projecao, tab_analises = st.tabs([
    "\ud83d\udcbc Carteira Principal",
    "\ud83d\udef0\ufe0f Ericsson",
    "\ud83d\udcc8 Proje\u00e7\u00e3o",
    "\ud83d\udd0d An\u00e1lises"
])

# ============================================================
# ABA 1: CARTEIRA PRINCIPAL
# ============================================================
with tab_carteira:
    st.subheader("\ud83d\udcbc Carteira Principal")

    if not df_principal.empty:
        # Resumo r\u00e1pido
        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
        with col_r1:
            st.metric("Total de Ativos", len(df_principal))
        with col_r2:
            st.metric("Investido", fmt_usd(custo_tot))
        with col_r3:
            st.metric("Lucro/Preju\u00edzo", fmt_usd(lucro_tot), delta=f"{lucro_pct_tot:+.2f}%")
        with col_r4:
            dy_medio = (df_principal["div_yield"] * df_principal["valor_atual"]).sum() / patrimonio if patrimonio else 0
            st.metric("DY M\u00e9dio (ponderado)", f"{dy_medio*100:.2f}%")

        st.markdown("---")

        # Preparar dataframe
        df_show = df_principal[[
            "ticker", "nome", "qtd", "pm_usd", "preco_usd", "var_pct",
            "valor_atual", "custo_total", "lucro", "lucro_pct",
            "div_yield", "yoc", "renda_mensal"
        ]].copy()

        df_show.columns = [
            "Ticker", "Nome", "Qtd", "PM (USD)", "Pre\u00e7o (USD)", "Var %",
            "Valor Atual", "Custo Total", "Lucro/Prej.", "Lucro %",
            "DY", "YOC", "Renda/M\u00eas"
        ]

        styled = df_show.style.format({
            "Qtd": lambda x: f"{x:.4f}".rstrip("0").rstrip(".") if pd.notna(x) else "-",
            "PM (USD)": lambda x: fmt_usd(x),
            "Pre\u00e7o (USD)": lambda x: fmt_usd(x),
            "Var %": lambda x: fmt_pct(x) if pd.notna(x) else "-",
            "Valor Atual": lambda x: fmt_usd(x),
            "Custo Total": lambda x: fmt_usd(x),
            "Lucro/Prej.": lambda x: fmt_usd(x),
            "Lucro %": lambda x: fmt_pct(x) if pd.notna(x) else "-",
            "DY": lambda x: fmt_pct_dy(x),
            "YOC": lambda x: fmt_pct_dy(x),
            "Renda/M\u00eas": lambda x: fmt_usd(x),
        })

        styled = aplicar_estilo_df(styled, ["Var %", "Lucro/Prej.", "Lucro %"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Gr\u00e1ficos
        df_pizza = df_principal[df_principal["valor_atual"].notna() & (df_principal["valor_atual"] > 0)].copy()
        if not df_pizza.empty:
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                fig_pizza = px.pie(
                    df_pizza,
                    values="valor_atual",
                    names="ticker",
                    title="\ud83e\udd67 Distribui\u00e7\u00e3o do Patrim\u00f4nio",
                    hole=0.4,
                )
                fig_pizza.update_traces(textposition="inside", textinfo="percent+label")
                fig_pizza.update_layout(height=400)
                st.plotly_chart(fig_pizza, use_container_width=True)

            with col_g2:
                df_renda = df_principal[df_principal["renda_mensal"].notna() & (df_principal["renda_mensal"] > 0)].copy()
                df_renda = df_renda.sort_values("renda_mensal", ascending=True)
                if not df_renda.empty:
                    fig_renda = px.bar(
                        df_renda,
                        x="renda_mensal",
                        y="ticker",
                        orientation="h",
                        title="\ud83d\udcb5 Renda Mensal por Ativo",
                        labels={"renda_mensal": "Renda (USD)", "ticker": "Ativo"},
                        color="renda_mensal",
                        color_continuous_scale="Viridis",
                    )
                    fig_renda.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig_renda, use_container_width=True)
    else:
        st.info("Nenhum ativo na carteira principal.")

# ============================================================
# ABA 2: ERICSSON
# ============================================================
with tab_ericsson:
    st.subheader("\ud83d\udef0\ufe0f Ericsson (Carteira Paralela)")

    if not df_eric.empty:
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            st.metric("Patrim\u00f4nio", fmt_usd(patr_eric))
        with col_e2:
            lucro_eric = df_eric["lucro"].sum(skipna=True) or 0
            st.metric("Lucro/Preju\u00edzo", fmt_usd(lucro_eric))
        with col_e3:
            st.metric("Renda Mensal", fmt_usd(renda_eric))

        st.markdown("---")

        df_eric_show = df_eric[[
            "ticker", "nome", "qtd", "pm_usd", "preco_usd",
            "valor_atual", "lucro", "lucro_pct", "div_yield", "renda_mensal"
        ]].copy()

        df_eric_show.columns = [
            "Ticker", "Nome", "Qtd", "PM (USD)", "Pre\u00e7o (USD)",
            "Valor Atual", "Lucro/Prej.", "Lucro %", "DY", "Renda/M\u00eas"
        ]

        styled_eric = df_eric_show.style.format({
            "Qtd": lambda x: f"{x:.4f}".rstrip("0").rstrip(".") if pd.notna(x) else "-",
            "PM (USD)": lambda x: fmt_usd(x),
            "Pre\u00e7o (USD)": lambda x: fmt_usd(x),
            "Valor Atual": lambda x: fmt_usd(x),
            "Lucro/Prej.": lambda x: fmt_usd(x),
            "Lucro %": lambda x: fmt_pct(x) if pd.notna(x) else "-",
            "DY": lambda x: fmt_pct_dy(x),
            "Renda/M\u00eas": lambda x: fmt_usd(x),
        })

        styled_eric = aplicar_estilo_df(styled_eric, ["Lucro/Prej.", "Lucro %"])
        st.dataframe(styled_eric, use_container_width=True, hide_index=True)

        st.info("\ud83d\udca1 A carteira Ericsson \u00e9 tratada de forma separada da carteira principal por ser uma posi\u00e7\u00e3o estrat\u00e9gica/paralela.")
    else:
        st.
#PARTE 4B

        st.info("Nenhum ativo Ericsson encontrado na planilha.")

# ============================================================
# ABA 3: PROJEÇÃO
# ============================================================
with tab_projecao:
    st.subheader("📈 Projeção Patrimonial")

    col_proj1, col_proj2 = st.columns([1, 3])
    with col_proj1:
        anos_proj = st.slider(
            "Anos de projeção",
            5, 40, 20, 1,
            help="Quantos anos projetar à frente.",
            key="slider_proj"
        )

    # Cálculo da projeção (juros compostos com aporte mensal)
    taxa_mensal = (1 + taxa_retorno) ** (1/12) - 1
    saldo = float(patrimonio)
    proj = []
    for m in range(1, anos_proj * 12 + 1):
        saldo = saldo * (1 + taxa_mensal) + aporte_mensal
        if m % 12 == 0:
            proj.append({
                "Ano": datetime.now().year + m // 12,
                "Patrimonio (USD)": saldo,
                "Renda Mensal Estimada (USD)": saldo * taxa_retorno / 12,
                "Aportado Acumulado (USD)": aporte_mensal * m,
            })

    df_proj = pd.DataFrame(proj)

    if not df_proj.empty:
        # Métricas finais da projeção
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            st.metric(
                f"Patrimônio em {anos_proj} anos",
                fmt_usd(df_proj["Patrimonio (USD)"].iloc[-1])
            )
        with col_p2:
            renda_final = df_proj["Renda Mensal Estimada (USD)"].iloc[-1]
            st.metric(
                "Renda Mensal Estimada",
                fmt_usd(renda_final),
                delta=f"{renda_final/meta_mensal*100:.0f}% da meta" if meta_mensal else None
            )
        with col_p3:
            total_aportado = df_proj["Aportado Acumulado (USD)"].iloc[-1]
            st.metric(
                "Total Aportado",
                fmt_usd(total_aportado)
            )

        st.markdown("---")

        # Gráfico de evolução
        fig_proj = px.line(
            df_proj,
            x="Ano",
            y=["Patrimonio (USD)", "Aportado Acumulado (USD)"],
            title="📈 Evolução Patrimonial Projetada",
            labels={"value": "USD", "variable": "Tipo"},
            markers=True,
        )
        fig_proj.update_layout(height=450, hovermode="x unified")
        st.plotly_chart(fig_proj, use_container_width=True)

        # Quando atingirá a meta?
        df_proj_meta = df_proj[df_proj["Renda Mensal Estimada (USD)"] >= meta_mensal]
        if not df_proj_meta.empty:
            ano_meta = df_proj_meta["Ano"].iloc[0]
            anos_faltam = ano_meta - datetime.now().year
            st.success(
                f"🎯 **Meta atingida em {ano_meta}** (em {anos_faltam} anos)! "
                f"Renda mensal projetada: {fmt_usd(df_proj_meta['Renda Mensal Estimada (USD)'].iloc[0])}"
            )
        else:
            renda_final = df_proj["Renda Mensal Estimada (USD)"].iloc[-1]
            faltam = meta_mensal - renda_final
            st.warning(
                f"⚠️ Meta não atingida em {anos_proj} anos. "
                f"Faltam {fmt_usd(faltam)}/mês. Considere aumentar o aporte ou estender o prazo."
            )

        # Tabela de projeção
        with st.expander("📋 Ver tabela completa da projeção"):
            df_proj_show = df_proj.copy()
            df_proj_show["Patrimonio (USD)"] = df_proj_show["Patrimonio (USD)"].apply(fmt_usd)
            df_proj_show["Renda Mensal Estimada (USD)"] = df_proj_show["Renda Mensal Estimada (USD)"].apply(fmt_usd)
            df_proj_show["Aportado Acumulado (USD)"] = df_proj_show["Aportado Acumulado (USD)"].apply(fmt_usd)
            st.dataframe(df_proj_show, use_container_width=True, hide_index=True)
    else:
        st.info("Não foi possível gerar projeção.")

# CONTINUA NA PARTE 5/5
# ============================================================
# ABA 4: ANÁLISES
# ============================================================
with tab_analises:
    st.subheader("🔍 Análises Detalhadas")

    if not df_principal.empty:
        # ===== Análise por Setor =====
        st.markdown("### 🏭 Alocação por Setor")
        df_setor = df_principal[df_principal["valor_atual"].notna() & (df_principal["valor_atual"] > 0)].copy()
        df_setor["setor"] = df_setor["setor"].fillna("Outros").replace("", "Outros")

        if not df_setor.empty:
            setor_agg = df_setor.groupby("setor").agg(
                valor_total=("valor_atual", "sum"),
                renda_total=("renda_mensal", "sum"),
                qtd_ativos=("ticker", "count")
            ).reset_index().sort_values("valor_total", ascending=False)

            setor_agg["pct"] = setor_agg["valor_total"] / setor_agg["valor_total"].sum() * 100

            col_s1, col_s2 = st.columns([1, 1])

            with col_s1:
                fig_setor = px.pie(
                    setor_agg,
                    values="valor_total",
                    names="setor",
                    title="Distribuição por Setor",
                    hole=0.4,
                )
                fig_setor.update_traces(textposition="inside", textinfo="percent+label")
                fig_setor.update_layout(height=400)
                st.plotly_chart(fig_setor, use_container_width=True)

            with col_s2:
                setor_show = setor_agg.copy()
                setor_show.columns = ["Setor", "Valor (USD)", "Renda/Mês", "Nº Ativos", "%"]
                setor_show["Valor (USD)"] = setor_show["Valor (USD)"].apply(fmt_usd)
                setor_show["Renda/Mês"] = setor_show["Renda/Mês"].apply(fmt_usd)
                setor_show["%"] = setor_show["%"].apply(lambda x: f"{x:.1f}%")
                st.dataframe(setor_show, use_container_width=True, hide_index=True)

        st.markdown("---")

        # ===== Top Performers =====
        st.markdown("### 🏆 Top Performers")

        col_t1, col_t2 = st.columns(2)

        with col_t1:
            st.markdown("**📈 Maiores Lucros (%)**")
            top_lucro = df_principal[df_principal["lucro_pct"].notna()].nlargest(5, "lucro_pct")[
                ["ticker", "lucro_pct", "lucro"]
            ].copy()
            if not top_lucro.empty:
                top_lucro.columns = ["Ticker", "Lucro %", "Lucro USD"]
                top_lucro["Lucro %"] = top_lucro["Lucro %"].apply(lambda x: f"+{x:.2f}%")
                top_lucro["Lucro USD"] = top_lucro["Lucro USD"].apply(fmt_usd)
                st.dataframe(top_lucro, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados suficientes.")

        with col_t2:
            st.markdown("**📉 Maiores Prejuízos (%)**")
            top_prej = df_principal[df_principal["lucro_pct"].notna()].nsmallest(5, "lucro_pct")[
                ["ticker", "lucro_pct", "lucro"]
            ].copy()
            if not top_prej.empty:
                top_prej.columns = ["Ticker", "Lucro %", "Lucro USD"]
                top_prej["Lucro %"] = top_prej["Lucro %"].apply(lambda x: f"{x:.2f}%")
                top_prej["Lucro USD"] = top_prej["Lucro USD"].apply(fmt_usd)
                st.dataframe(top_prej, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados suficientes.")

        st.markdown("---")

        # ===== Maiores Pagadores de Dividendos =====
        st.markdown("### 💰 Maiores Pagadores de Dividendos")

        col_d1, col_d2 = st.columns(2)

        with col_d1:
            st.markdown("**💵 Maior Renda Mensal (USD)**")
            top_renda = df_principal[df_principal["renda_mensal"].notna() & (df_principal["renda_mensal"] > 0)].nlargest(5, "renda_mensal")[
                ["ticker", "renda_mensal", "div_yield"]
            ].copy()
            if not top_renda.empty:
                top_renda.columns = ["Ticker", "Renda/Mês", "DY"]
                top_renda["Renda/Mês"] = top_renda["Renda/Mês"].apply(fmt_usd)
                top_renda["DY"] = top_renda["DY"].apply(fmt_pct_dy)
                st.dataframe(top_renda, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados suficientes.")

        with col_d2:
            st.markdown("**📊 Maior DY (%)**")
            top_dy = df_principal[df_principal["div_yield"].notna() & (df_principal["div_yield"] > 0)].nlargest(5, "div_yield")[
                ["ticker", "div_yield", "yoc"]
            ].copy()
            if not top_dy.empty:
                top_dy.columns = ["Ticker", "DY Atual", "YOC"]
                top_dy["DY Atual"] = top_dy["DY Atual"].apply(fmt_pct_dy)
                top_dy["YOC"] = top_dy["YOC"].apply(fmt_pct_dy)
                st.dataframe(top_dy, use_container_width=True, hide_index=True)
            else:
                st.info("Sem dados suficientes.")

        st.markdown("---")

        # ===== Concentração da Carteira =====
        st.markdown("### ⚖️ Concentração da Carteira")
        df_conc = df_principal[df_principal["valor_atual"].notna() & (df_principal["valor_atual"] > 0)].copy()
        if not df_conc.empty and patrimonio:
            df_conc["pct"] = df_conc["valor_atual"] / patrimonio * 100
            df_conc = df_conc.sort_values("pct", ascending=False)

            top5_pct = df_conc.head(5)["pct"].sum()
            top10_pct = df_conc.head(10)["pct"].sum()

            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                st.metric("Top 5 Ativos", f"{top5_pct:.1f}% do patrimônio")
            with col_c2:
                st.metric("Top 10 Ativos", f"{top10_pct:.1f}% do patrimônio")
            with col_c3:
                maior = df_conc.iloc[0]
                st.metric(f"Maior posição: {maior['ticker']}", f"{maior['pct']:.1f}%")

            if top5_pct > 50:
                st.warning("⚠️ **Alta concentração:** Top 5 ativos representam mais de 50% da carteira. Considere diversificar.")
            elif top5_pct < 30:
                st.success("✅ **Boa diversificação:** Carteira bem distribuída entre os ativos.")
    else:
        st.info("Carregue dados para ver as análises.")

# ============================================================
# RODAPÉ
# ============================================================
st.markdown("---")
st.caption(
    "💡 **Dashboard de Aposentadoria** | "
    f"Dados via Yahoo Finance (cache: {CACHE_TTL//60} min) | "
    "Valores em USD"
)
st.caption(
    "⚠️ *Este dashboard é uma ferramenta de acompanhamento. Não constitui recomendação de investimento.*"
)

