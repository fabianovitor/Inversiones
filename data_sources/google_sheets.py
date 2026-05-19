# ============================================================
# data_sources/google_sheets.py
# Fonte de dados: Google Sheets (implementação atual)
# ============================================================

import streamlit as st
import pandas as pd
import requests
from io import StringIO

from data_sources.base import DataSourceBase
from config import (
    GOOGLE_SHEETS_URL,
    MAPEAMENTO_COLUNAS_GS,
    TICKER_ERICSSON,
    CACHE_TTL_PLANILHA,
)


class GoogleSheetsSource(DataSourceBase):
    """Carrega carteira direto do Google Sheets via URL CSV.
    
    Requisito: planilha deve estar pública (Compartilhar →
    Qualquer pessoa com o link → Leitor).
    """

    def nome_fonte(self) -> str:
        return "Google Sheets"

    def suporta_tempo_real(self) -> bool:
        return False  # Dados manuais, atualizados pelo usuário

    def suporta_historico(self) -> bool:
        return False  # Sem histórico de operações (por ora)

    def esta_disponivel(self) -> bool:
        """Verifica se a URL do Google Sheets responde."""
        try:
            r = requests.head(GOOGLE_SHEETS_URL, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # --------------------------------------------------------
    # MÉTODO PRINCIPAL
    # --------------------------------------------------------

    @st.cache_data(ttl=CACHE_TTL_PLANILHA, show_spinner=False)
    def carregar(_self) -> pd.DataFrame:
        """Carrega e normaliza a planilha do Google Sheets.
        
        Returns:
            DataFrame normalizado com colunas padrão do dashboard
        """
        try:
            # 1. Download do CSV
            df_bruto = _self._baixar_csv()
            if df_bruto is None:
                return pd.DataFrame()

            # 2. Normaliza colunas
            df = _self._normalizar_colunas(df_bruto)

            # 3. Limpa dados
            df = _self._limpar(df)

            # 4. Preenche colunas opcionais faltantes
            df = _self.preencher_opcionais(df)

            # 5. Define tipo da carteira (principal / ericsson)
            df["tipo"] = df["ticker"].apply(
                lambda t: "ericsson" if t == TICKER_ERICSSON else "principal"
            )

            # 6. Valida resultado
            if not _self.validar(df):
                return pd.DataFrame()

            return df

        except Exception as e:
            st.error(f"❌ [Google Sheets] Erro inesperado: {e}")
            return pd.DataFrame()

    # --------------------------------------------------------
    # MÉTODOS INTERNOS
    # --------------------------------------------------------

    def _baixar_csv(self) -> pd.DataFrame | None:
        """Faz o download do CSV do Google Sheets."""
        try:
            response = requests.get(GOOGLE_SHEETS_URL, timeout=15)
            response.raise_for_status()
            df = pd.read_csv(StringIO(response.text))
            return df

        except requests.exceptions.ConnectionError:
            st.error(
                "❌ Sem conexão com a internet ou Google Sheets inacessível."
            )
            return None

        except requests.exceptions.Timeout:
            st.error(
                "❌ Timeout ao acessar Google Sheets. Tente novamente."
            )
            return None

        except requests.exceptions.HTTPError as e:
            if "403" in str(e):
                st.error(
                    "❌ Acesso negado ao Google Sheets (403).\n\n"
                    "**Solução:** Abra a planilha → Compartilhar → "
                    "Qualquer pessoa com o link → Leitor → Concluído."
                )
            else:
                st.error(f"❌ Erro HTTP ao acessar planilha: {e}")
            return None

        except Exception as e:
            st.error(f"❌ Erro ao baixar planilha: {e}")
            return None

    def _normalizar_colunas(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nomes das colunas e aplica mapeamento."""
        # Mantém apenas colunas A-N (primeiras 14)
        if len(df.columns) > 14:
            df = df.iloc[:, :14]

        # Lowercase + strip
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Aplica mapeamento espanhol → padrão dashboard
        df = df.rename(columns=MAPEAMENTO_COLUNAS_GS)

        return df

    def _limpar(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpa e normaliza os dados."""
        df = df.copy()

        # --- Ticker ---
        df = df.dropna(subset=["ticker"])
        df["ticker"] = (
            df["ticker"].astype(str).str.upper().str.strip()
        )
        df = df[df["ticker"] != ""]
        df = df[df["ticker"] != "NAN"]
        df = df[~df["ticker"].str.startswith("TICKER")]  # remove header duplicado

        # --- Colunas de texto ---
        if "nome" not in df.columns:
            df["nome"] = df["ticker"]
        else:
            df["nome"] = (
                df["nome"].fillna(df["ticker"]).astype(str).str.strip()
            )

        if "categoria" not in df.columns:
            df["categoria"] = "Outros"
        else:
            df["categoria"] = (
                df["categoria"].fillna("Outros").astype(str).str.strip()
            )

        # --- Colunas numéricas ---
        colunas_num = [
            "qtd",
            "pm_usd",
            "div_anual",
            "yoc_planilha",
            "preco_atual_planilha",
            "valor_total_planilha",
            "peso_planilha",
            "objetivo_pct",
            "diferenca",
            "valor_acao",
        ]

        for col in colunas_num:
            if col in df.columns:
                df[col] = df[col].apply(self._limpar_numero)
            else:
                df[col] = 0.0

        # --- Remove ativos sem quantidade ---
        df = df[df["qtd"] > 0].reset_index(drop=True)

        return df

    @staticmethod
    def _limpar_numero(valor) -> float:
        """Converte valor formatado ($, %, vírgula) para float.
        
        Exemplos:
            "$1,234.50" → 1234.50
            "5.25%"     → 5.25
            "1.234,50"  → 1234.50
            "-"         → 0.0
        """
        if pd.isna(valor) or valor is None:
            return 0.0

        if isinstance(valor, (int, float)):
            return float(valor)

        try:
            s = str(valor).strip()
            # Remove símbolos
            for simbolo in ["$", "€", "R$", "%", " "]:
                s = s.replace(simbolo, "")

            # Detecta formato numérico
            if "," in s and "." in s:
                # Formato US: 1,234.50 → remove vírgula
                s = s.replace(",", "")
            elif "," in s:
                # Formato BR/ES: 1234,50 → troca vírgula por ponto
                s = s.replace(",", ".")

            # Valores vazios ou traço
            if s in ("", "-") or s.lower() == "nan":
                return 0.0

            return float(s)

        except (ValueError, TypeError):
            return 0.0
