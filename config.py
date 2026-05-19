# ============================================================
# config.py - Configurações centrais do dashboard
# ============================================================

# ============================================================
# FONTE DE DADOS (troque aqui no futuro)
# ============================================================
# Opções disponíveis:
#   "google_sheets"  -> Planilha Google Sheets (ATUAL)
#   "ibkr_flex"      -> IBKR Flex Query (FUTURO v2.0)
#   "ibkr_api"       -> IBKR TWS API (FUTURO v3.0)
#   "excel_local"    -> Arquivo Excel local (BACKUP)

DATA_SOURCE = "google_sheets"
# ============================================================
# VARIÁVEIS ADICIONAIS
# ============================================================
BRL_USD = 5.0           # Taxa de câmbio USD → BRL
MOSTRAR_ERICSSON = True  # Habilitar aba Ericsson
# ============================================================
# CONFIGURAÇÕES: GOOGLE SHEETS
# ============================================================
GOOGLE_SHEETS_ID  = "1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU"
GOOGLE_SHEETS_GID = "79928919"
GOOGLE_SHEETS_URL = (
    f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}"
    f"/export?format=csv&gid={GOOGLE_SHEETS_GID}"
)

# ============================================================
# CONFIGURAÇÕES: IBKR FLEX QUERY (FUTURO - deixe vazio por ora)
# ============================================================
IBKR_FLEX_TOKEN   = ""   # Seu token Flex Query
IBKR_FLEX_QUERY_ID = ""  # ID da query configurada no IBKR

# ============================================================
# CONFIGURAÇÕES: IBKR TWS API (FUTURO - deixe vazio por ora)
# ============================================================
IBKR_TWS_HOST = "127.0.0.1"
IBKR_TWS_PORT = 7497
IBKR_TWS_CLIENT_ID = 1

# ============================================================
# MAPEAMENTO DE COLUNAS: Google Sheets -> padrão dashboard
# ============================================================
MAPEAMENTO_COLUNAS_GS = {
    "ticker"        : "ticker",
    "empresa"       : "nome",
    "categoría"     : "categoria",
    "categoria"     : "categoria",
    "objetivo %"    : "objetivo_pct",
    "cantidad"      : "qtd",
    "precio medio"  : "pm_usd",
    "dividendos ttm": "div_anual",
    "yield on cost" : "yoc_planilha",
    "precio actual" : "preco_atual_planilha",
    "valor total"   : "valor_total_planilha",
    "% actual"      : "peso_planilha",
    "diferencia"    : "diferenca",
    "accion"        : "acao",
    "valor"         : "valor_acao",
}

# ============================================================
# IDENTIFICAÇÃO DE CARTEIRAS
# ============================================================
TICKER_ERICSSON = "ERIC"   # Ticker que identifica carteira Ericsson

# ============================================================
# CONFIGURAÇÕES DE CACHE
# ============================================================
CACHE_TTL_PLANILHA  = 300   # 5 minutos (Google Sheets)
CACHE_TTL_MERCADO   = 180   # 3 minutos (Yahoo Finance)

# ============================================================
# MOEDA E FORMATAÇÃO
# ============================================================
MOEDA_SIMBOLO = "USD"
MOEDA_LOCALE  = "en_US"

# ============================================================
# CORES DO DASHBOARD
# ============================================================
CORES = {
    "positivo"  : "#00C853",
    "negativo"  : "#FF1744",
    "neutro"    : "#9E9E9E",
    "primario"  : "#1565C0",
    "secundario": "#FFA000",
    "fundo"     : "#0E1117",
}

# ============================================================
# TOOLTIPS
# ============================================================
TOOLTIPS = {
    "patrimonio"   : "Valor total da carteira a preço atual de mercado.",
    "renda_mensal" : "Estimativa de dividendos mensais (Dividendos TTM ÷ 12).",
    "dy"           : "Dividend Yield: dividendos anuais ÷ preço atual.",
    "yoc"          : "Yield on Cost: dividendos anuais ÷ preço médio de compra.",
    "lucro"        : "Diferença entre valor atual e custo total investido.",
}
