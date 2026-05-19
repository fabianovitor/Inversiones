# ============================================================
# debug_manager.py - Sistema de Debug com exportação de arquivo
# ============================================================

import json
import traceback
import streamlit as st
from datetime import datetime
import pandas as pd


def _serializar(obj):
    """Converte objetos não serializáveis para JSON."""
    if isinstance(obj, pd.DataFrame):
        return {
            "tipo": "DataFrame",
            "linhas": len(obj),
            "colunas": list(obj.columns),
            "dados": obj.head(10).to_dict(orient="records"),
        }
    if isinstance(obj, pd.Series):
        return obj.tolist()
    try:
        return float(obj)
    except Exception:
        return str(obj)


class DebugManager:
    """Gerencia coleta e exportação de dados de debug."""

    def __init__(self):
        if "debug_log" not in st.session_state:
            st.session_state["debug_log"] = []
        if "debug_ativo" not in st.session_state:
            st.session_state["debug_ativo"] = False

    @property
    def ativo(self) -> bool:
        return st.session_state.get("debug_ativo", False)

    def log(self, secao: str, chave: str, valor):
        """Registra informação de debug."""
        if not self.ativo:
            return
        entry = {
            "timestamp": datetime.now().isoformat(),
            "secao": secao,
            "chave": chave,
            "valor": valor,
        }
        st.session_state["debug_log"].append(entry)

    def log_erro(self, secao: str, erro: Exception):
        """Registra erro com traceback completo."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "secao": secao,
            "chave": "ERRO",
            "valor": {
                "tipo": type(erro).__name__,
                "mensagem": str(erro),
                "traceback": traceback.format_exc(),
            },
        }
        # Sempre registra erros, mesmo sem debug ativo
        st.session_state["debug_log"].append(entry)

    def log_df(self, secao: str, nome: str, df: pd.DataFrame):
        """Registra informações de um DataFrame."""
        if not self.ativo:
            return
        if df is None or df.empty:
            self.log(secao, nome, "DataFrame VAZIO")
            return
        self.log(secao, nome, {
            "linhas": len(df),
            "colunas": list(df.columns),
            "tipos": {c: str(df[c].dtype) for c in df.columns},
            "nulos": {c: int(df[c].isna().sum()) for c in df.columns},
            "amostra_5": df.head(5).to_dict(orient="records"),
            "numericos_soma": {
                c: float(df[c].sum())
                for c in df.columns
                if pd.api.types.is_numeric_dtype(df[c])
            },
        })

    def log_resumo(self, secao: str, resumo: dict):
        """Registra dicionário de resumo."""
        if not self.ativo:
            return
        self.log(secao, "resumo_carteira", resumo)

    def gerar_json(self) -> str:
        """Gera JSON completo para exportação."""
        dados = {
            "gerado_em": datetime.now().isoformat(),
            "versao_app": "Inversiones FCV",
            "total_entradas": len(st.session_state.get("debug_log", [])),
            "log": st.session_state.get("debug_log", []),
        }
        return json.dumps(dados, ensure_ascii=False,
                          indent=2, default=_serializar)

    def limpar(self):
        """Limpa o log de debug."""
        st.session_state["debug_log"] = []


# Instância global
debug = DebugManager()


def renderizar_sidebar_debug():
    """Renderiza controles de debug na sidebar."""
    with st.sidebar:
        st.divider()
        st.markdown("### 🔧 Debug")

        ativo = st.toggle(
            "Modo Debug",
            value=st.session_state.get("debug_ativo", False),
            key="toggle_debug",
        )
        st.session_state["debug_ativo"] = ativo

        if ativo:
            st.warning("⚠️ Debug ativado")

        total = len(st.session_state.get("debug_log", []))
        erros = [
            e for e in st.session_state.get("debug_log", [])
            if e.get("chave") == "ERRO"
        ]

        if erros:
            st.error(f"🔴 {len(erros)} erro(s) detectado(s)")

        if total > 0:
            st.caption(f"📋 {total} entradas registradas")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Limpar", use_container_width=True):
                    debug.limpar()
                    st.rerun()

            with col2:
                json_str = debug.gerar_json()
                nome_arquivo = (
                    f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                st.download_button(
                    label="⬇️ Baixar",
                    data=json_str.encode("utf-8"),
                    file_name=nome_arquivo,
                    mime="application/json",
                    use_container_width=True,
                )

            if ativo:
                with st.expander("👁️ Preview últimas entradas"):
                    log = st.session_state.get("debug_log", [])
                    for entry in log[-5:]:
                        st.json(entry)
