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
    debug = st.checkbox("🐛 Modo Debug", False, help="Mostra informações técnicas de carregamento.")

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

if debug:
    st.error("🐛 MODO DEBUG ATIVO")
    st.subheader("DEBUG - Informações detectadas")
    st.write(f"**Ticker:** `{col_ticker}` | **Qtd:** `{col_qtd}` | **PM:** `{col_pm}`")
    st.write("**Colunas:**", list(df.columns))
    st.dataframe(df.head(20))
    csv_planilha = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 CSV planilha (debug)", csv_planilha, "planilha_debug.csv", "text/csv")

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

if debug:
    st.warning("🐛 Dados completos buscados:")
    st.dataframe(dfa)
    csv_debug = dfa.to_csv(index=False).encode("utf-8")
    st.download_button("📥 CSV dados (debug)", csv_debug, "dados_debug.csv", "text/csv")

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

# Avisos sobre DY corrigidos
dy_corrigidos = df_principal[df_principal["dy_corrigido"] == True]
if not dy_corrigidos.empty:
    with st.expander(f"⚠️ {len(dy_corrigidos)} ativo(s) tiveram DY corrigido (DY anômalo do Yahoo)"):
        for _, r in dy_corrigidos.iterrows():
            dy_show = f"{r['div_yield']*100:.2f}%" if r['div_yield'] else "N/D"
            st.write(f"• **{r['ticker']}** ({r['nome']}): DY recalculado = {dy_show}")

# ============================================================
# MÉTRICAS PRINCIPAIS COM TOOLTIPS E CORES
# ============================================================
st.subheader("📊 Visão Geral")

c1, c2, c3, c4 = st.columns(4)

with c1:
    delta_pct = f"{lucro_pct_tot:+.2f}%" if custo_tot else None
    st.metric(
        label="💼 Patrimônio Principal",
        value=fmt_usd(patrimonio),
        delta=delta_pct,
        help=TOOLTIPS["patrimonio"]
    )

with c2:
    pct_meta = (renda_tot / meta_mensal * 100) if meta_mensal else 0
    st.metric(
        label="💵 Renda Mensal Estimada",
        value=fmt_usd(renda_tot),
        delta=f"{pct_meta:.1f}% da meta",
        help=TOOLTIPS["renda_mensal"]
    )

with c3:
    delta_eric = f"+{fmt_usd(renda_eric)}/mês" if renda_eric else None
    st.metric(
        label="🛰️ Ericsson (Paralela)",
        value=fmt_usd(patr_eric),
        delta=delta_eric,
        help=TOOLTIPS["ericsson"]
    )

with c4:
    if meta_mensal > renda_tot:
        delta_meta = f"Faltam {fmt_usd(meta_mensal - renda_tot)}"
        st.metric(
            label="🎯 Meta Mensal",
            value=fmt_usd(meta_mensal),
            delta=delta_meta,
            delta_color="inverse",
            help=TOOLTIPS["meta"]
        )
    else:
        st.metric(
            label="🎯 Meta Mensal",
            value=fmt_usd(meta_mensal),
            delta="✅ Atingida!",
            help=TOOLTIPS["meta"]
        )

# Barra de progresso visual da meta
st.markdown("##### 📈 Progresso até a Meta de Renda Mensal")
progresso = min(renda_tot / meta_mensal, 1.0) if meta_mensal else 0
st.progress(progresso, text=f"{renda_tot/meta_mensal*100:.1f}% — {fmt_usd(renda_tot)} de {fmt_usd(meta_mensal)}")

st.markdown("---")

# CONTINUA NA PARTE 4/4
# CONTINUAÇÃO DA PARTE 3

# ============================================================
# CARTEIRA PRINCIPAL - TABELA COM CORES
# ============================================================
st.subheader("💼 Carteira Principal")

if not df_principal.empty:
    # Preparar dataframe para exibição
    df_show = df_principal[[
        "ticker", "nome", "qtd", "pm_usd", "preco_usd", "var_pct",
        "valor_atual", "custo_total", "lucro", "lucro_pct",
        "div_yield", "yoc", "renda_mensal"
    ]].copy()

    # Renomear colunas
    df_show.columns = [
        "Ticker", "Nome", "Qtd", "PM (USD)", "Preço (USD)", "Var %",
        "Valor Atual", "Custo Total", "Lucro/Prej.", "Lucro %",
        "DY", "YOC", "Renda/Mês"
    ]

    # Função de estilização (cores verde/vermelho)
    def colorir_lucro(val):
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

    # Aplicar formatação
    styled = df_show.style.format({
        "Qtd": lambda x: f"{x:.4f}".rstrip("0").rstrip(".") if pd.notna(x) else "-",
        "PM (USD)": lambda x: fmt_usd(x),
        "Preço (USD)": lambda x: fmt_usd(x),
        "Var %": lambda x: fmt_pct(x) if pd.notna(x) else "-",
        "Valor Atual": lambda x: fmt_usd(x),
        "Custo Total": lambda x: fmt_usd(x),
        "Lucro/Prej.": lambda x: fmt_usd(x),
        "Lucro %": lambda x: fmt_pct(x) if pd.notna(x) else "-",
        "DY": lambda x: fmt_pct_dy(x),
        "YOC": lambda x: fmt_pct_dy(x),
        "Renda/Mês": lambda x: fmt_usd(x),
    }).applymap(colorir_lucro, subset=["Var %", "Lucro/Prej.", "Lucro %"])

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Gráfico de pizza - distribuição do patrimônio
    df_pizza = df_principal[df_principal["valor_atual"].notna() & (df_principal["valor_atual"] > 0)].copy()
    if not df_pizza.empty:
        fig = px.pie(
            df_pizza,
            values="valor_atual",
            names="ticker",
            title="🥧 Distribuição do Patrimônio",
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nenhum ativo na carteira principal.")

st.markdown("---")

# ============================================================
# ERICSSON PARALELA
# ============================================================
if not df_eric.empty:
    st.subheader("🛰️ Ericsson (Carteira Paralela)")

    df_eric_show = df_eric[[
        "ticker", "nome", "qtd", "pm_usd", "preco_usd",
        "valor_atual", "lucro", "lucro_pct", "div_yield", "renda_mensal"
    ]].copy()

    df_eric_show.columns = [
        "Ticker", "Nome", "Qtd", "PM (USD)", "Preço (USD)",
        "Valor Atual", "Lucro/Prej.", "Lucro %", "DY", "Renda/Mês"
    ]

    styled_eric = df_eric_show.style.format({
        "Qtd": lambda x: f"{x:.4f}".rstrip("0").rstrip(".") if pd.notna(x) else "-",
        "PM (USD)": lambda x: fmt_usd(x),
        "Preço (USD)": lambda x: fmt_usd(x),
        "Valor Atual": lambda x: fmt_usd(x),
        "Lucro/Prej.": lambda x: fmt_usd(x),
        "Lucro %": lambda x: fmt_pct(x) if pd.notna(x) else "-",
        "DY": lambda x: fmt_pct_dy(x),
        "Renda/Mês": lambda x: fmt_usd(x),
    }).applymap(colorir_lucro, subset=["Lucro/Prej.", "Lucro %"])

    st.dataframe(styled_eric, use_container_width=True, hide_index=True)

    st.markdown("---")

# ============================================================
# PROJEÇÃO PATRIMONIAL
# ============================================================
st.subheader("📈 Projeção Patrimonial")

col_proj1, col_proj2 = st.columns([1, 3])
with col_proj1:
    anos_proj = st.slider(
        "Anos de projeção",
        5, 40, 20, 1,
        help="Quantos anos projetar à frente."
    )

taxa_mensal = (1 + taxa_retorno) ** (1/12) - 1
saldo = float(patrimonio)
proj = []
for m in range(1, anos_proj * 12 + 1):
    saldo = saldo * (1 + taxa_mensal) + aporte_mensal
    if m % 12 == 0:
        proj.append({
            "Ano": datetime.now().year + m // 12,
            "Patrimonio (USD)": saldo,
            "Renda Mensal Est. (USD)": saldo * 0.004,
        })
df_proj = pd.DataFrame(proj)

if not df_proj.empty:
    # Identificar quando atinge a meta
    df_proj["Atinge Meta"] = df_proj["Renda Mensal Est. (USD)"] >= meta_mensal
    ano_meta = df_proj[df_proj["Atinge Meta"]]["Ano"].min() if df_proj["Atinge Meta"].any() else None

    if ano_meta:
        anos_faltam = ano_meta - datetime.now().year
        st.success(f"🎯 **Você atinge a meta de {fmt_usd(meta_mensal)}/mês em {int(ano_meta)}** (em {int(anos_faltam)} anos)")
    else:
        st.warning(f"⚠️ Com aporte de {fmt_usd(aporte_mensal)}/mês e retorno de {taxa_retorno*100:.1f}%, você não atinge a meta em {anos_proj} anos.")

    # Gráfico de projeção
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df_proj["Ano"],
        y=df_proj["Patrimonio (USD)"],
        mode="lines+markers",
        name="Patrimônio",
        line=dict(color="#1f77b4", width=3),
        fill="tozeroy",
        fillcolor="rgba(31, 119, 180, 0.1)",
    ))

    # Linha da meta (patrimônio necessário pela regra dos 4%)
    patrimonio_meta = meta_mensal * 12 / 0.04
    fig2.add_hline(
        y=patrimonio_meta,
        line_dash="dash",
        line_color="green",
        annotation_text=f"Meta FIRE: {fmt_usd(patrimonio_meta)}",
        annotation_position="top right"
    )

    fig2.update_layout(
        title=f"Projeção (retorno {taxa_retorno*100:.1f}% a.a., aporte {fmt_usd(aporte_mensal)}/mês)",
        xaxis_title="Ano",
        yaxis_title="Patrimônio (USD)",
        height=450,
        hovermode="x unified",
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Tabela de projeção
    df_proj_show = df_proj[["Ano", "Patrimonio (USD)", "Renda Mensal Est. (USD)"]].copy()
    df_proj_show["Patrimonio (USD)"] = df_proj_show["Patrimonio (USD)"].apply(fmt_usd)
    df_proj_show["Renda Mensal Est. (USD)"] = df_proj_show["Renda Mensal Est. (USD)"].apply(fmt_usd)
    st.dataframe(df_proj_show, use_container_width=True, hide_index=True)

# ============================================================
# RODAPÉ
# ============================================================
st.markdown("---")
col_rod1, col_rod2, col_rod3 = st.columns(3)
with col_rod1:
    st.caption("📊 **Dashboard de Aposentadoria v2.0**")
with col_rod2:
    st.caption("🔗 Dados: Yahoo Finance + Google Sheets")
with col_rod3:
    st.caption(f"⏱️ Cache: 5 min | Etapa 1 ✅")