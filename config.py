# ============================================================
# config.py
# ============================================================

# URL do Google Sheets publicado como CSV
GOOGLE_SHEETS_URL = (
    "https://docs.google.com/spreadsheets/d/SEU_ID_AQUI/export?format=csv&gid=0"
)

# Ticker da Ericsson (ajuste conforme aparece na planilha)
TICKER_ERICSSON = "ERIC"  # ou "ERIC B", verifique exato

# TTL do cache em segundos (5 minutos)
CACHE_TTL_PLANILHA = 300

# Mapeamento de colunas Google Sheets -> nomes internos
# AJUSTE as chaves conforme os nomes REAIS das colunas da sua planilha
MAPEAMENTO_COLUNAS_GS = {
    # Identificação
    "ticker":           "ticker",
    "ativo":            "ticker",
    "symbol":           "ticker",
    "nome":             "nome",
    "name":             "nome",
    "setor":            "setor",
    "sector":           "setor",
    "categoria":        "categoria",
    "category":         "categoria",

    # Quantidades e preços
    "qtd":              "qtd",
    "quantidade":       "qtd",
    "quantity":         "qtd",
    "shares":           "qtd",
    "pm":               "pm_usd",
    "pm (usd)":         "pm_usd",
    "preco medio":      "pm_usd",
    "preco_medio":      "pm_usd",
    "avg price":        "pm_usd",
    "avg_price":        "pm_usd",

    # Dividendos
    "div anual":        "div_anual",
    "div_anual":        "div_anual",
    "dividendo anual":  "div_anual",
    "annual div":       "div_anual",
    "annual_div":       "div_anual",
    "dps":              "div_anual",

    # YoC
    "yoc":              "yoc_planilha",
    "yield on cost":    "yoc_planilha",

    # Preço atual
    "preco atual":      "preco_atual_planilha",
    "preco_atual":      "preco_atual_planilha",
    "current price":    "preco_atual_planilha",
    "cotacao":          "preco_atual_planilha",

    # Valor total
    "valor total":      "valor_total_planilha",
    "valor_total":      "valor_total_planilha",
    "total value":      "valor_total_planilha",
    "market value":     "valor_total_planilha",

    # Peso
    "peso":             "peso_planilha",
    "weight":           "peso_planilha",
    "% carteira":       "peso_planilha",

    # Objetivo
    "objetivo":         "objetivo_pct",
    "target":           "objetivo_pct",
    "target %":         "objetivo_pct",
}
