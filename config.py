# ============================================================
# config.py - Configurações, constantes e tooltips
# ============================================================

# ----- Caminho da planilha -----
PLANILHA_PATH = "carteira.xlsx"

# ----- Configurações financeiras padrão -----
META_MENSAL_DEFAULT = 5000.0      # Meta de renda mensal em USD
APORTE_MENSAL_DEFAULT = 1000.0    # Aporte mensal em USD
TAXA_RETORNO_DEFAULT = 0.10       # 10% ao ano (retorno esperado)
TAXA_SAQUE_DEFAULT = 0.04         # 4% ao ano (regra dos 4%)
ANOS_PROJECAO_DEFAULT = 17        # 48 → 65 anos

# ----- Configurações do Streamlit -----
PAGE_CONFIG = {
    "page_title": "Dashboard Aposentadoria",
    "page_icon": "💰",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

# ----- Cache (em segundos) -----
CACHE_TTL_COTACOES = 300          # 5 minutos
CACHE_TTL_DIVIDENDOS = 3600       # 1 hora

# ----- Limites de rebalanceamento -----
LIMITE_ERICSSON_PCT = 0.25        # 25% da carteira principal

# ----- Tooltips (textos de ajuda) -----
TOOLTIPS = {
    "patrimonio": (
        "Soma do valor atual (preço × quantidade) de todos os ativos "
        "da carteira principal, excluindo a Ericsson."
    ),
    "renda_mensal": (
        "Estimativa de renda mensal baseada no Dividend Yield (DY) "
        "atual de cada ativo, dividido por 12 meses."
    ),
    "ericsson": (
        "Carteira paralela com ações da Ericsson adquiridas via plano "
        "de compra da empresa. Tratada separadamente."
    ),
    "meta": (
        "Meta de renda mensal passiva (em USD) que você deseja atingir "
        "para se aposentar com tranquilidade."
    ),
    "aporte": (
        "Valor que você consegue investir todo mês na carteira."
    ),
    "taxa_retorno": (
        "Retorno anual médio esperado da carteira (juros compostos), "
        "considerando dividendos reinvestidos."
    ),
    "taxa_saque": (
        "Percentual anual seguro para retirada na aposentadoria. "
        "A 'regra dos 4%' é o padrão consagrado."
    ),
    "dy": (
        "Dividend Yield: percentual que o ativo paga em dividendos "
        "ao ano, em relação ao preço atual."
    ),
    "yoc": (
        "Yield on Cost: dividendos pagos em relação ao seu preço "
        "médio de compra (não ao preço atual). Mostra a rentabilidade "
        "real do seu investimento."
    ),
}

# ----- Cores para gráficos -----
CORES = {
    "lucro": "#00C853",
    "prejuizo": "#D50000",
    "neutro": "#9E9E9E",
    "primaria": "#1f77b4",
    "ericsson": "#FF6B35",
    "meta": "#FFC107",
}

# ----- Colunas esperadas na planilha -----
COLUNAS_PLANILHA = [
    "ticker",       # Ex: AAPL, MSFT, ERIC
    "nome",         # Nome da empresa
    "tipo",         # 'principal' ou 'ericsson'
    "setor",        # Setor da empresa (Tech, Health, etc.)
    "qtd",          # Quantidade de ações
    "pm_usd",       # Preço médio em USD
]