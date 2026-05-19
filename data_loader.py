# ============================================================
# data_loader.py - Carregamento via Google Sheets
# ============================================================

import streamlit as st
import pandas as pd
import requests
from io import StringIO
from config import (
    GOOGLE_SHEETS_URL,
    MAPEAMENTO_COLUNAS,
    TICKER_ERICSSON,
)
from market_data import enriquecer_ativo
from utils import safe_float, safe_div


# ============================================================
# CARREGAR PLANILHA DO GOOGLE SHEETS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def carregar_planilha(url=GOOGLE_SHEETS_URL):
    """Carrega a planilha direto do Google Sheets via URL CSV.
    
    Args:
        url: URL de exportação CSV do Google Sheets
    
    Returns:
        DataFrame normalizado ou None se falhar
    """
    try:
        # Faz download do CSV
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        # Lê CSV
        df = pd.read_csv(StringIO(response.text))
        
        # Normaliza nomes das colunas (lowercase, sem espaços extras)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Mantém apenas as colunas A-N (primeiras 14)
        if len(df.columns) > 14:
            df = df.iloc[:, :14]
        
        # Renomeia colunas para padrão do dashboard
        df = df.rename(columns=MAPEAMENTO_COLUNAS)
        
        # Valida colunas essenciais
        colunas_essenciais = ["ticker", "qtd", "pm_usd"]
        faltando = [c for c in colunas_essenciais if c not in df.columns]
        if faltando:
            st.error(
                f"❌ Colunas essenciais faltando: {faltando}\n\n"
                f"Colunas encontradas: {list(df.columns)}"
            )
            return None
        
        # Limpa e normaliza
        df = limpar_dados(df)
        
        return df
    
    except requests.exceptions.RequestException as e:
        st.error(
            f"❌ Erro ao acessar Google Sheets: {e}\n\n"
            "Verifique se a planilha está pública (Compartilhar → "
            "Qualquer pessoa com o link → Leitor)."
        )
        return None
    except Exception as e:
        st.error(f"❌ Erro ao processar planilha: {e}")
        return None


def limpar_dados(df):
    """Limpa e normaliza os dados da planilha.
    
    Args:
        df: DataFrame bruto
    
    Returns:
        DataFrame limpo
    """
    df = df.copy()
    
    # Remove linhas sem ticker
    df = df.dropna(subset=["ticker"])
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df = df[df["ticker"] != ""]
    df = df[df["ticker"] != "NAN"]
    
    # Converte colunas numéricas (limpa formatação como "$", ",", "%")
    colunas_numericas = [
        "qtd", "pm_usd", "div_anual", "yoc_planilha",
        "preco_atual_planilha", "valor_total_planilha",
        "peso_planilha", "objetivo_pct", "diferenca", "valor_acao"
    ]
    
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(limpar_numero)
    
    # Preenche colunas opcionais que podem não existir
    if "nome" not in df.columns:
        df["nome"] = df["ticker"]
    else:
        df["nome"] = df["nome"].fillna(df["ticker"]).astype(str)
    
    if "categoria" not in df.columns:
        df["categoria"] = "Outros"
    else:
        df["categoria"] = df["categoria"].fillna("Outros").astype(str)
    
    # Define o tipo (principal ou ericsson) baseado no ticker
    df["tipo"] = df["ticker"].apply(
        lambda t: "ericsson" if t == TICKER_ERICSSON else "principal"
    )
    
    # Remove ativos sem quantidade
    df = df[df["qtd"] > 0].reset_index(drop=True)
    
    return df


def limpar_numero(valor):
    """Converte valores com formatação ($, ,, %) para float.
    
    Exemplos:
        "$1,234.50" -> 1234.50
        "5.25%"     -> 5.25
        "1.234,50"  -> 1234.50 (formato BR)
        "-"         -> 0.0
    """
    if pd.isna(valor) or valor is None:
        return 0.0
    
    if isinstance(valor, (int, float)):
        return float(valor)
    
    try:
        # Remove caracteres não numéricos comuns
        s = str(valor).strip()
        s = s.replace("$", "").replace("€", "").replace("R$", "")
        s = s.replace("%", "").replace(" ", "")
        
        # Detecta formato BR vs US
        # Se tem vírgula E ponto, ponto é separador de milhar (formato US: 1,234.50)
        # Se tem só vírgula, vírgula é decimal (formato BR: 1234,50)
        if "," in s and "." in s:
            # Formato US: 1,234.50
            s = s.replace(",", "")
        elif "," in s:
            # Formato BR: 1234,50
            s = s.replace(",", ".")
        
        if s == "" or s == "-" or s.lower() == "nan":
            return 0.0
        
        return float(s)
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# ENRIQUECER COM DADOS DE MERCADO (yfinance)
# ============================================================

def enriquecer_carteira(df, usar_planilha=True):
    """Adiciona dados de mercado e calcula métricas.
    
    Args:
        df: DataFrame da planilha
        usar_planilha: Se True, usa preços/dividendos da planilha;
                      Se False, busca tudo via yfinance
    
    Returns:
        DataFrame enriquecido
    """
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # Inicializa colunas
    df["preco_atual"] = 0.0
    df["variacao_pct"] = 0.0
    df["div_yield"] = 0.0
    df["setor"] = ""
    
    # Decide a estratégia
    if usar_planilha:
        # Usa preço da planilha como base, busca só variação/setor via yfinance
        st.info("📊 Usando preços da planilha + buscando variação do dia...")
    else:
        st.info("🌐 Buscando todos os dados via Yahoo Finance...")
    
    # Busca dados de cada ticker
    progress_bar = st.progress(0, text="Buscando cotações...")
    total = len(df)
    
    for i, row in df.iterrows():
        ticker = row["ticker"]
        progress_bar.progress((i + 1) / total, text=f"Processando {ticker}...")
        
        dados = enriquecer_ativo(ticker)
        
        if usar_planilha and row.get("preco_atual_planilha", 0) > 0:
            # Usa preço da planilha
            df.at[i, "preco_atual"] = safe_float(row["preco_atual_planilha"])
        else:
            # Usa preço do yfinance
            df.at[i, "preco_atual"] = safe_float(dados.get("preco_atual"))
        
        df.at[i, "variacao_pct"] = safe_float(dados.get("variacao_pct"))
        df.at[i, "setor"] = dados.get("setor") or row.get("categoria", "Outros")
        
        # DY: usa da planilha se tiver, senão do yfinance
        if usar_planilha and row.get("yoc_planilha", 0) > 0:
            df.at[i, "div_yield"] = safe_float(row["yoc_planilha"]) / 100
        else:
            df.at[i, "div_yield"] = safe_float(dados.get("div_yield"))
        
        # Dividendos anuais por ação (usa da planilha)
        if "div_anual" not in df.columns or pd.isna(row.get("div_anual")):
            df.at[i, "div_anual"] = safe_float(dados.get("div_anual"))
    
    progress_bar.empty()
    
    # ----- CÁLCULOS DERIVADOS -----
    
    # Custo total = qtd × pm_usd
    df["custo_total"] = df["qtd"] * df["pm_usd"]
    
    # Valor atual = qtd × preco_atual
    df["valor_atual"] = df["qtd"] * df["preco_atual"]
    
    # Lucro/Prejuízo
    df["lucro_usd"] = df["valor_atual"] - df["custo_total"]
    df["lucro_pct"] = df.apply(
        lambda r: safe_div(r["lucro_usd"], r["custo_total"]) * 100,
        axis=1
    )
    
    # Renda de dividendos
    # div_anual já é o valor por ação (Dividendos TTM da planilha)
    df["div_recebido_anual"] = df["qtd"] * df["div_anual"].fillna(0)
    df["renda_mensal"] = df["div_recebido_anual"] / 12
    
    # Yield on Cost
    df["yoc"] = df.apply(
        lambda r: safe_div(r["div_recebido_
