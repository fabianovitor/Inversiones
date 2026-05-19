# ============================================================
# data_sources/__init__.py
# Pacote de fontes de dados plug-and-play
# ============================================================

from config import DATA_SOURCE

def get_data_source():
    """Retorna a instância da fonte de dados configurada.
    
    Troque DATA_SOURCE no config.py para mudar a fonte.
    
    Returns:
        Instância da fonte de dados ativa
    """
    if DATA_SOURCE == "google_sheets":
        from data_sources.google_sheets import GoogleSheetsSource
        return GoogleSheetsSource()
    
    elif DATA_SOURCE == "ibkr_flex":
        # FUTURO v2.0
        try:
            from data_sources.ibkr_flex import IBKRFlexSource
            return IBKRFlexSource()
        except ImportError:
            import streamlit as st
            st.error("❌ Módulo IBKR Flex não implementado ainda.")
            st.stop()
    
    elif DATA_SOURCE == "ibkr_api":
        # FUTURO v3.0
        try:
            from data_sources.ibkr_api import IBKRApiSource
            return IBKRApiSource()
        except ImportError:
            import streamlit as st
            st.error("❌ Módulo IBKR API não implementado ainda.")
            st.stop()
    
    elif DATA_SOURCE == "excel_local":
        # BACKUP
        try:
            from data_sources.excel_local import ExcelLocalSource
            return ExcelLocalSource()
        except ImportError:
            import streamlit as st
            st.error("❌ Módulo Excel Local não implementado ainda.")
            st.stop()
    
    else:
        raise ValueError(f"DATA_SOURCE inválido: '{DATA_SOURCE}'")


__all__ = ["get_data_source"]
