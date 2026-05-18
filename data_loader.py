# ============================================================
# data_loader.py - Carregamento e processamento da planilha
# ============================================================

import streamlit as st
import pandas as pd
import os
from config import PLANILHA_PATH, COLUNAS_PLANILHA
from market_data import enriquecer_ativo
from utils import safe_float, safe_div


# ============================================================
# CARREGAR PLANILHA
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def carregar_planilha(caminho=PLANILHA_PATH):
    """Carrega a planilha Excel da carteira.
    
    Args:
        caminho: caminho do arquivo .xlsx
    
    Returns:
        DataFrame com a carteira ou None se falhar
    """
    if not os.path.exists(caminho):
        st.error(f"❌ Planilha não encontrada: {caminho}")
        st.info(
            "Crie um arquivo `carteira.xlsx` na raiz do projeto com as colunas: "
            f"{', '.join(COLUNAS_PLANILHA)}"
        )
        return None
    
    try:
        df = pd.read_excel(caminho)
        
        # Normaliza nomes das colunas (lowercase, sem espaços)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Valida colunas obrigatórias
        colunas_faltando = [c for c in COLUNAS_PLANILHA if c not in df.columns]
        if colunas_faltando:
            st.error(
                f"❌ Colunas faltando na planilha: {colunas_faltando}\n\n"
                f"Colunas esperadas: {COLUNAS_PLANILHA}\n"
                f"Colunas encontradas: {list(df.columns)}"
            )
            return None
        
        # Remove linhas vazias
        df = df.dropna(subset=["ticker"])
        
        # Normaliza tipos
        df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
        df["tipo"] = df["tipo"].astype(str).str.lower().str.strip()
        df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
        df["pm_usd"] = pd.to_numeric(df["pm_usd"], errors="coerce").fillna(0)
        
        # Remove ativos sem quantidade
        df = df[df["qtd"] > 0].reset_index(drop=True)
        
        return df
    
    except Exception as e:
        st.error(f"❌ Erro ao ler planilha: {e}")
        return None


# ============================================================
# ENRIQUECER CARTEIRA COM DADOS DE MERCADO
# ============================================================

def enriquecer_carteira(df):
    """Adiciona dados de mercado (preço, DY, etc.) à carteira.
    
    Args:
        df: DataFrame da planilha
    
    Returns:
        DataFrame enriquecido com colunas calculadas
    """
    if df is None or df.empty:
        return df
    
    # Cria cópia para não alterar original
    df = df.copy()
    
    # Inicializa colunas de mercado
    df["preco_atual"] = 0.0
    df["variacao_pct"] = 0.0
    df["div_yield"] = 0.0
    df["div_anual"] = 0.0
    
    # Busca dados de cada ticker
    progress_bar = st.progress(0, text="Buscando cotações...")
    total = len(df)
    
    for i, row in df.iterrows():
        ticker = row["ticker"]
        progress_bar.progress((i + 1) / total, text=f"Buscando {ticker}...")
        
        dados = enriquecer_ativo(ticker)
        
        df.at[i, "preco_atual"] = safe_float(dados.get("preco_atual"))
        df.at[i, "variacao_pct"] = safe_float(dados.get("variacao_pct"))
        df.at[i, "div_yield"] = safe_float(dados.get("div_yield"))
        df.at[i, "div_anual"] = safe_float(dados.get("div_anual"))
        
        # Atualiza setor se vazio na planilha
        if pd.isna(row.get("setor")) or not str(row.get("setor", "")).strip():
            df.at[i, "setor"] = dados.get("setor", "Outros")
    
    progress_bar.empty()
    
    # ----- CÁLCULOS DERIVADOS -----
    
    # Valor investido (custo)
    df["custo_total"] = df["qtd"] * df["pm_usd"]
    
    # Valor atual de mercado
    df["valor_atual"] = df["qtd"] * df["preco_atual"]
    
    # Lucro/Prejuízo em USD
    df["lucro_usd"] = df["valor_atual"] - df["custo_total"]
    
    # Lucro/Prejuízo em %
    df["lucro_pct"] = df.apply(
        lambda r: safe_div(r["lucro_usd"], r["custo_total"]) * 100,
        axis=1
    )
    
    # Dividendos anuais estimados (USD)
    # Usa div_anual se disponível, senão calcula via DY
    df["div_recebido_anual"] = df.apply(
        lambda r: r["qtd"] * r["div_anual"] if r["div_anual"] > 0
        else r["valor_atual"] * r["div_yield"],
        axis=1
    )
    
    # Renda mensal estimada
    df["renda_mensal"] = df["div_recebido_anual"] / 12
    
    # Yield on Cost (YoC) - rentabilidade sobre o preço de compra
    df["yoc"] = df.apply(
        lambda r: safe_div(r["div_recebido_anual"], r["custo_total"]) * 100,
        axis=1
    )
    
    # Peso na carteira (calculado depois pela função separar_carteiras)
    df["peso_pct"] = 0.0
    
    return df


# ============================================================
# SEPARAR CARTEIRA PRINCIPAL E ERICSSON
# ============================================================

def separar_carteiras(df):
    """Separa a carteira em principal e Ericsson.
    
    Args:
        df: DataFrame enriquecido
    
    Returns:
        tuple: (df_principal, df_ericsson)
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    df_principal = df[df["tipo"] == "principal"].copy().reset_index(drop=True)
    df_ericsson = df[df["tipo"] == "ericsson"].copy().reset_index(drop=True)
    
    # Calcula peso percentual em cada carteira
    if not df_principal.empty:
        total_principal = df_principal["valor_atual"].sum()
        if total_principal > 0:
            df_principal["peso_pct"] = (df_principal["valor_atual"] / total_principal) * 100
    
    if not df_ericsson.empty:
        total_ericsson = df_ericsson["valor_atual"].sum()
        if total_ericsson > 0:
            df_ericsson["peso_pct"] = (df_ericsson["valor_atual"] / total_ericsson) * 100
    
    return df_principal, df_ericsson


# ============================================================
# CALCULAR MÉTRICAS RESUMO
# ============================================================

def calcular_metricas(df):
    """Calcula métricas resumo de uma carteira.
    
    Args:
        df: DataFrame de uma carteira (principal ou ericsson)
    
    Returns:
        dict com: patrimonio, custo_total, lucro_usd, lucro_pct,
                  renda_mensal, renda_anual, dy_medio, yoc_medio
    """
    if df is None or df.empty:
        return {
            "patrimonio": 0.0,
            "custo_total": 0.0,
            "lucro_usd": 0.0,
            "lucro_pct": 0.0,
            "renda_mensal": 0.0,
            "renda_anual": 0.0,
            "dy_medio": 0.0,
            "yoc_medio": 0.0,
            "num_ativos": 0,
        }
    
    patrimonio = df["valor_atual"].sum()
    custo_total = df["custo_total"].sum()
    lucro_usd = df["lucro_usd"].sum()
    lucro_pct = safe_div(lucro_usd, custo_total) * 100
    renda_anual = df["div_recebido_anual"].sum()
    renda_mensal = renda_anual / 12
    
    # DY médio ponderado pelo valor atual
    dy_medio = safe_div(renda_anual, patrimonio) * 100
    
    # YoC médio ponderado pelo custo
    yoc_medio = safe_div(renda_anual, custo_total) * 100
    
    return {
        "patrimonio": patrimonio,
        "custo_total": custo_total,
        "lucro_usd": lucro_usd,
        "lucro_pct": lucro_pct,
        "renda_mensal": renda_mensal,
        "renda_anual": renda_anual,
        "dy_medio": dy_medio,
        "yoc_medio": yoc_medio,
        "num_ativos": len(df),
    }


# ============================================================
# CRIAR PLANILHA EXEMPLO (caso o usuário não tenha)
# ============================================================

def criar_planilha_exemplo(caminho=PLANILHA_PATH):
    """Cria uma planilha exemplo se não existir.
    
    Útil para o primeiro uso do dashboard.
    """
    if os.path.exists(caminho):
        return False
    
    exemplo = pd.DataFrame([
        {"ticker": "AAPL", "nome": "Apple Inc.", "tipo": "principal",
         "setor": "Technology", "qtd": 10, "pm_usd": 150.00},
        {"ticker": "MSFT", "nome": "Microsoft Corp.", "tipo": "principal",
         "setor": "Technology", "qtd": 5, "pm_usd": 300.00},
        {"ticker": "JNJ", "nome": "Johnson & Johnson", "tipo": "principal",
         "setor": "Healthcare", "qtd": 8, "pm_usd": 160.00},
        {"ticker": "KO", "nome": "Coca-Cola", "tipo": "principal",
         "setor": "Consumer", "qtd": 20, "pm_usd": 55.00},
        {"ticker": "ERIC", "nome": "Ericsson", "tipo": "ericsson",
         "setor": "Technology", "qtd": 100, "pm_usd": 6.50},
    ])
    
    exemplo.to_excel(caminho, index=False)
    return True