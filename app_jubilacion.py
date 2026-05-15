import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Estrategia Jubilación", layout="wide")

# --- CONEXIÓN ---
SHEET_ID = '1zgByQdqcNFUzXJmwbHu8TxxiLMzcD2CawB_ZEGOathU'
# Exportar como TSV (separado por tabulaciones) es a prueba de errores de comas
URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=tsv'

def smart_parser(x):
    """Convierte texto a número entendiendo formatos de México y Brasil simultáneamente."""
    if pd.isna(x): return 0.0
    s = str(x).strip().replace('$', '').replace('%', '').replace('R$', '').replace(' ', '')
    if not s: return 0.0
    
    # Identificar si la coma actúa como decimal (Brasil) o miles (México/USA)
    if ',' in s:
        parts = s.split(',')
        # Si después de la coma hay 1 o 2 dígitos, es un decimal
        if len(parts[-1]) <= 2 or (len(parts) == 2 and '.' in parts[0]): 
            s = s.replace('.', '').replace(',', '.')
        else:
            # Si hay 3 dígitos después de la coma, es separador de miles
            s = s.replace(',', '')
            
    try:
        return float(s)
    except:
        return 0.0

@st.cache_data(ttl=300)
def load_data():
    try:
        df = pd.read_csv(URL, sep='\t') # Leer como TSV
        df.columns = [str(c).strip() for c in df.columns]
        
        for col in ['Cantidad', 'Precio Medio', 'Objetivo %']:
            if col in df.columns:
                df[col] = df[col].apply(smart_parser)
        
        # Filtramos posiciones en cero
        if 'Cantidad' in df.columns:
            df = df[df['Cantidad'] > 0].copy()
            
        return df
    except Exception as e:
        st.error(f"Error de lectura: {e}")
        return None

st.title("Dashboard de Jubilación")

df = load_data()

if df is not None and not df.empty:
    # --- PRECIOS ---
    if st.sidebar.button('Sincronizar Mercado'):
        precios = []
        for t in df['Ticker']:
            try:
                tk = str(t).replace('.B', '-B')
                val = yf.Ticker(tk).fast_info['lastPrice']
                precios.append(val)
            except: precios.append(0.0)
        df['Precio_Actual'] = precios
    else:
        df['Precio_Actual'] = df['Precio Medio']

    # --- CÁLCULOS ESTÁNDAR Y PLAN DE EMPRESA ---
    df['Valor_Posicion'] = df['Precio_Actual'] * df['Cantidad']
    
    # Separar la posición de beneficios para que el resto sume el 100% exacto
    mask_std = df['Ticker'] != 'ERIC-B'
    total_std = df.loc[mask_std, 'Valor_Posicion'].sum()
    
    df['% Real'] = 0.0
    if total_std > 0:
        df.loc[mask_std, '% Real'] = (df.loc[mask_std, 'Valor_Posicion'] / total_std) * 100
        
    df['Dif %'] = df['% Real'] - df['Objetivo %']

    # --- MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimonio Estándar", f"${total_std:,.2f}")
    c2.metric("Beneficio Empresa (Extra)", f"${df.loc[~mask_std, 'Valor_Posicion'].sum():,.2f}")
    c3.metric("Posiciones Abiertas", len(df))

    st.markdown("---")

   # --- TABLA ---
    st.subheader("Análisis de Rebalanceo")
    
    def color_dif(val):
        # Rojo suave si falta comprar, Verde suave si estás en la meta o por encima
        return 'background-color: #f8d7da' if val < -0.1 else 'background-color: #d4edda'

    st.dataframe(
        df[['Ticker', 'Cantidad', 'Precio Medio', 'Precio_Actual', 'Objetivo %', '% Real', 'Dif %']].style.format({
            'Cantidad': '{:.4f}', 
            'Precio Medio': '${:.2f}', 
            'Precio_Actual': '${:.2f}',
            'Objetivo %': '{:.2f}%', 
            '% Real': '{:.2f}%', 
            'Dif %': '{:.2f}%'
        }).map(color_dif, subset=['Dif %']), # Nota: applymap cambió a map en versiones recientes de Pandas
        use_container_width=True
    )