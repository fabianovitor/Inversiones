# ============================================================
# data_sources/base.py
# Interface abstrata - todas as fontes devem seguir este contrato
# ============================================================

from abc import ABC, abstractmethod
import pandas as pd


class DataSourceBase(ABC):
    """Interface base para todas as fontes de dados.
    
    Qualquer nova fonte (IBKR, Excel, etc.) deve:
    1. Herdar desta classe
    2. Implementar os métodos abstratos
    3. Registrar no data_sources/__init__.py
    
    Isso garante que o dashboard funcione igual,
    independente de onde vêm os dados.
    """

    # --------------------------------------------------------
    # MÉTODO PRINCIPAL (obrigatório implementar)
    # --------------------------------------------------------

    @abstractmethod
    def carregar(self) -> pd.DataFrame:
        """Carrega os dados brutos da fonte e retorna DataFrame normalizado.
        
        O DataFrame retornado DEVE conter as colunas padrão:
        
        Obrigatórias:
            ticker          (str)   - Símbolo do ativo (ex: "AAPL")
            nome            (str)   - Nome da empresa
            categoria       (str)   - Categoria/setor (ex: "ETF", "Stock")
            qtd             (float) - Quantidade de ações
            pm_usd          (float) - Preço médio de compra em USD
            div_anual       (float) - Dividendos anuais por ação (TTM)
        
        Opcionais (podem ser 0 se não disponíveis):
            objetivo_pct         (float) - % objetivo na carteira
            yoc_planilha         (float) - Yield on cost da planilha
            preco_atual_planilha (float) - Preço atual da planilha
            valor_total_planilha (float) - Valor total da planilha
            peso_planilha        (float) - Peso % da planilha
            diferenca            (float) - Diferença da planilha
        
        Returns:
            pd.DataFrame normalizado ou DataFrame vazio se falhar
        """
        pass

    # --------------------------------------------------------
    # MÉTODOS OPCIONAIS (podem sobrescrever)
    # --------------------------------------------------------

    def nome_fonte(self) -> str:
        """Nome legível da fonte de dados."""
        return self.__class__.__name__

    def esta_disponivel(self) -> bool:
        """Verifica se a fonte está acessível antes de carregar.
        
        Útil para checar conexão, autenticação, etc.
        Retorna True por padrão (fonte sempre disponível).
        """
        return True

    def suporta_tempo_real(self) -> bool:
        """Indica se a fonte fornece dados em tempo real."""
        return False

    def suporta_historico(self) -> bool:
        """Indica se a fonte fornece histórico de operações."""
        return False

    def info(self) -> dict:
        """Retorna informações sobre a fonte."""
        return {
            "nome": self.nome_fonte(),
            "tempo_real": self.suporta_tempo_real(),
            "historico": self.suporta_historico(),
            "disponivel": self.esta_disponivel(),
        }

    # --------------------------------------------------------
    # COLUNAS PADRÃO (contrato do dashboard)
    # --------------------------------------------------------

    COLUNAS_OBRIGATORIAS = [
        "ticker",
        "nome",
        "categoria",
        "qtd",
        "pm_usd",
        "div_anual",
    ]

    COLUNAS_OPCIONAIS = {
        "objetivo_pct"          : 0.0,
        "yoc_planilha"          : 0.0,
        "preco_atual_planilha"  : 0.0,
        "valor_total_planilha"  : 0.0,
        "peso_planilha"         : 0.0,
        "diferenca"             : 0.0,
    }

    def validar(self, df: pd.DataFrame) -> bool:
        """Valida se o DataFrame tem as colunas obrigatórias.
        
        Args:
            df: DataFrame a validar
            
        Returns:
            True se válido, False se inválido
        """
        import streamlit as st

        if df is None or df.empty:
            st.error(f"❌ [{self.nome_fonte()}] DataFrame vazio.")
            return False

        faltando = [
            c for c in self.COLUNAS_OBRIGATORIAS
            if c not in df.columns
        ]

        if faltando:
            st.error(
                f"❌ [{self.nome_fonte()}] Colunas obrigatórias faltando: "
                f"{faltando}\n\n"
                f"Colunas encontradas: {list(df.columns)}"
            )
            return False

        return True

    def preencher_opcionais(self, df: pd.DataFrame) -> pd.DataFrame:
        """Garante que colunas opcionais existam com valor padrão.
        
        Args:
            df: DataFrame a completar
            
        Returns:
            DataFrame com todas as colunas opcionais preenchidas
        """
        for col, valor_padrao in self.COLUNAS_OPCIONAIS.items():
            if col not in df.columns:
                df[col] = valor_padrao
        return df
