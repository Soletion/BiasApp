"""
Main Streamlit App - Análisis Macroeconómico EUR/USD
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Importar módulos
from modules.data_ingestion import DataIngestion
from modules.news_analyzer import FinBERTAnalyzer
from modules.data_processing import MacroBiasCalculator
from modules.technical_analysis import TechnicalAnalysis
from modules.utils import clear_cache

# Configuración de página
st.set_page_config(
    page_title="Macro Analysis EUR/USD",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .bias-box {
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        margin: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .alert-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .critical-error {
        background-color: #dc3545;
        color: white;
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        margin: 2rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar session state
if 'data_ingestion' not in st.session_state:
    st.session_state.data_ingestion = DataIngestion(
        fred_api_key=os.getenv('FRED_API_KEY'),
        news_api_key=os.getenv('NEWSAPI_KEY')
    )
if 'news_analyzer' not in st.session_state:
    st.session_state.news_analyzer = FinBERTAnalyzer()
if 'bias_calculator' not in st.session_state:
    st.session_state.bias_calculator = MacroBiasCalculator()
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'market_data' not in st.session_state:
    st.session_state.market_data = None
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None
if 'data_error' not in st.session_state:
    st.session_state.data_error = None
if 'data_status' not in st.session_state:
    st.session_state.data_status = None

def refresh_data():
    """Actualiza todos los datos - PRIORIDAD Yahoo Finance"""
    with st.spinner("🔄 Conectando con fuentes de datos..."):
        try:
            # Limpiar errores previos
            st.session_state.data_error = None
            st.session_state.data_status = None
            
            # Obtener datos con prioridad Yahoo Finance
            st.session_state.market_data = st.session_state.data_ingestion.get_market_data(days=90, force_refresh=True)
            
            # VERIFICACIÓN ESTRICTA: No permitir datos vacíos
            if st.session_state.market_data is None or st.session_state.market_data.empty:
                error_msg = """
                ❌ **ERROR CRÍTICO: No se pudieron obtener datos de mercado reales**
                
                **Posibles causas:**
                - Sin conexión a Internet
                - Yahoo Finance no está accesible
                - Firewall o proxy bloqueando la conexión
                
                **Soluciones:**
                1. Verifica tu conexión a Internet
                2. Espera unos minutos y vuelve a intentar
                3. Desactiva temporalmente VPN o firewall
                """
                st.session_state.data_error = error_msg
                st.session_state.data_status = 'error'
                st.session_state.market_data = None
                st.session_state.analysis_result = None
                return
            
            # Verificar que los datos tengan la estructura esperada
            required_columns = ['eurusd_close', 'eurusd_high', 'eurusd_low', 'spy_close']
            missing_columns = [col for col in required_columns if col not in st.session_state.market_data.columns]
            
            if missing_columns:
                error_msg = f"""
                ❌ **ERROR: Datos de mercado incompletos**
                
                Columnas faltantes: {', '.join(missing_columns)}
                
                Por favor, intenta nuevamente más tarde.
                """
                st.session_state.data_error = error_msg
                st.session_state.data_status = 'error'
                st.session_state.market_data = None
                st.session_state.analysis_result = None
                return
            
            # Verificar cantidad mínima de datos
            if len(st.session_state.market_data) < 30:
                error_msg = f"""
                ❌ **ERROR: Datos insuficientes para análisis**
                
                Se obtuvieron solo {len(st.session_state.market_data)} días de datos.
                Se necesitan al menos 30 días para un análisis significativo.
                """
                st.session_state.data_error = error_msg
                st.session_state.data_status = 'error'
                st.session_state.market_data = None
                st.session_state.analysis_result = None
                return
            
            # Obtener yields
            us2y, de2y = st.session_state.data_ingestion.get_bond_yields()
            
            if us2y is None or de2y is None:
                st.warning("⚠️ No se pudieron obtener datos de bonos. El análisis continuará sin componente de yield spread.")
            
            # Obtener noticias
            fed_news = st.session_state.data_ingestion.get_news("Federal Reserve OR FOMC OR Powell interest rates")
            ecb_news = st.session_state.data_ingestion.get_news("ECB OR Lagarde interest rates")
            all_news = fed_news + ecb_news
            
            if not all_news:
                st.warning("⚠️ No se obtuvieron noticias. El análisis continuará sin componente de sentimiento.")
            
            # Clasificar noticias con FinBERT
            fed_tone, ecb_tone = st.session_state.news_analyzer.classify_news(all_news)
            
            # Calcular cambio S&P 500
            if len(st.session_state.market_data) > 1:
                spy_change = (st.session_state.market_data['spy_close'].iloc[-1] / 
                             st.session_state.market_data['spy_close'].iloc[-2] - 1) * 100
            else:
                spy_change = 0
            
            # Datos macro
            macro_data = {
                'us': {'gdp_surprise': 0, 'inflation': 0},
                'eu': {'gdp_surprise': 0, 'inflation': 0}
            }
            
            # Calcular bias macro
            st.session_state.analysis_result = st.session_state.bias_calculator.calculate_bias_score(
                fed_tone=fed_tone,
                ecb_tone=ecb_tone,
                us2y=us2y,
                de2y=de2y,
                macro_data=macro_data,
                spy_change=spy_change
            )
            
            st.session_state.last_update = datetime.now()
            st.session_state.data_status = 'success'
            
            current_price = st.session_state.market_data['eurusd_close'].iloc[-1]
            st.success(f"✅ Datos reales cargados correctamente - EUR/USD: {current_price:.5f}")
            
        except Exception as e:
            error_msg = f"""
            ❌ **ERROR CRÍTICO en la obtención de datos**
            
            **Detalle técnico:** {str(e)}
            """
            st.session_state.data_error = error_msg
            st.session_state.data_status = 'error'
            st.session_state.market_data = None
            st.session_state.analysis_result = None
            st.exception(e)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/economic-growth.png", width=80)
    st.title("📊 Macro Analysis")
    st.markdown("---")
    
    # Indicador de estado
    if st.session_state.data_status == 'success':
        st.success("🟢 Datos REALES cargados")
    elif st.session_state.data_status == 'error':
        st.error("🔴 Error - Sin datos reales")
    else:
        st.info("⏳ Sin conexión")
    
    st.markdown("---")
    
    if st.button("🔄 Actualizar ahora", use_container_width=True):
        refresh_data()
        st.rerun()
    
    st.markdown("---")
    
    # Mostrar estado de APIs
    st.subheader("🔌 Estado APIs")
    if os.getenv('FRED_API_KEY'):
        st.success("✅ FRED API: Configurada")
    else:
        st.warning("⚠️ FRED API: No configurada (componente bonos limitado)")
    
    if os.getenv('NEWSAPI_KEY'):
        st.success("✅ NewsAPI: Configurada")
    else:
        st.warning("⚠️ NewsAPI: No configurada (sin noticias en tiempo real)")
    
    if st.session_state.news_analyzer.available:
        st.success("✅ FinBERT: Cargado")
    else:
        st.warning("⚠️ FinBERT: No disponible (análisis básico)")
    
    st.markdown("---")
    
    if st.session_state.last_update:
        st.caption(f"Última actualización: {st.session_state.last_update.strftime('%H:%M:%S')}")
    
    st.caption("🔒 **Política de datos:** Prioridad Yahoo Finance (tiempo real) -> Fallback EOD")
    
    if st.button("🗑️ Limpiar cache", use_container_width=True):
        clear_cache()
        st.success("Cache limpiado")
        st.rerun()

# Main content
st.markdown('<div class="main-header">📈 Análisis Macroeconómico EUR/USD</div>', unsafe_allow_html=True)

# Mostrar error crítico si existe
if st.session_state.data_error:
    st.markdown(f'<div class="critical-error">{st.session_state.data_error}</div>', unsafe_allow_html=True)
    
    with st.expander("🔧 Guía de solución de problemas"):
        st.markdown("""
        ### Pasos para resolver el problema:
        
        1. **Verificar conexión a Internet**
        2. **Espera 2-3 minutos y reintenta**
        3. **Reinicia la aplicación**
        """)
    
    st.stop()

# Si no hay datos, no continuar
if st.session_state.analysis_result is None or st.session_state.market_data is None:
    st.info("📡 Esperando conexión con fuentes de datos reales...")
    st.info("Haz clic en 'Actualizar ahora' para intentar conectar.")
    st.stop()

# TABS
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboard", "📰 Noticias", "📅 Calendario", 
    "📐 Zonas Técnicas", "🔄 Evolución", "📚 Glosario"
])

# TAB 1: DASHBOARD
with tab1:
    # Mostrar advertencia si estamos en fallback
    if hasattr(st.session_state.data_ingestion, 'using_fallback') and st.session_state.data_ingestion.using_fallback:
        st.warning(st.session_state.data_ingestion.fallback_warning)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        bias = st.session_state.analysis_result['bias']
        confidence = st.session_state.analysis_result['confidence']
        
        color_map = {
            '🟢 BULLISH': '#28a745',
            '🔴 BEARISH': '#dc3545',
            '⚪ NEUTRAL': '#6c757d'
        }
        bg_color = color_map.get(bias, '#6c757d')
        
        st.markdown(f"""
        <div class="bias-box" style="background-color: {bg_color}20; border: 2px solid {bg_color}">
            <h2 style="margin:0; color: {bg_color}">{bias}</h2>
            <p style="font-size: 1.2rem; margin:0.5rem 0">Confianza: {confidence:.0f}%</p>
            <p style="margin:0.5rem 0 0 0">{st.session_state.analysis_result['explanation']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📝 Interpretación")
        explanation_text = st.session_state.bias_calculator.generate_natural_language_explanation(
            st.session_state.analysis_result
        )
        st.info(explanation_text)
        
        if st.session_state.analysis_result.get('alerts'):
            st.markdown("### 🚨 Alertas")
            for alert in st.session_state.analysis_result['alerts']:
                st.markdown(f'<div class="alert-box">{alert["message"]}</div>', 
                           unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 🧠 Drivers")
        components = st.session_state.analysis_result['components']
        
        fed_delta = components.get('fed_delta', 0)
        fed_delta_icon = "🔼" if fed_delta > 0 else "🔽" if fed_delta < 0 else "➡️"
        st.metric("Fed Tone", f"{components.get('fed_tone', 0):.2f}", 
                 delta=f"{fed_delta_icon} {fed_delta:+.2f}")
        
        ecb_delta = components.get('ecb_delta', 0)
        ecb_delta_icon = "🔼" if ecb_delta > 0 else "🔽" if ecb_delta < 0 else "➡️"
        st.metric("ECB Tone", f"{components.get('ecb_tone', 0):.2f}", 
                 delta=f"{ecb_delta_icon} {ecb_delta:+.2f}")
        
        if components.get('yield_spread'):
            st.metric("Yield Spread", f"{components['yield_spread']:.2f}%")
        
        st.metric("US Macro", f"{components.get('us_macro', 0):.2f}")
        st.metric("EU Macro", f"{components.get('eu_macro', 0):.2f}")
    
    with col3:
        st.markdown("### 📊 Score Breakdown")
        score = st.session_state.analysis_result['score']
        st.progress(min(abs(score) / 10, 1.0))
        st.metric("Score Total", f"{score:.2f}")
        
        contributions = st.session_state.analysis_result.get('contributions', {})
        
        if contributions:
            fed_contrib = contributions.get('fed', 0)
            fed_color = "🟢" if fed_contrib > 0 else "🔴" if fed_contrib < 0 else "⚪"
            st.metric(f"{fed_color} Fed", f"{fed_contrib:+.2f}")
            
            ecb_contrib = contributions.get('ecb', 0)
            ecb_color = "🟢" if ecb_contrib > 0 else "🔴" if ecb_contrib < 0 else "⚪"
            st.metric(f"{ecb_color} BCE", f"{ecb_contrib:+.2f}")
            
            spread_contrib = contributions.get('spread', 0)
            spread_color = "🟢" if spread_contrib > 0 else "🔴" if spread_contrib < 0 else "⚪"
            st.metric(f"{spread_color} Yield Spread", f"{spread_contrib:+.2f}")
        
        current_price = st.session_state.market_data['eurusd_close'].iloc[-1]
        prev_price = st.session_state.market_data['eurusd_close'].iloc[-2] if len(st.session_state.market_data) > 1 else current_price
        change = (current_price - prev_price) / prev_price * 100
        st.metric("EUR/USD", f"{current_price:.5f}", f"{change:+.2f}%")
        st.caption(f"🕐 Actualizado: {st.session_state.last_update.strftime('%H:%M:%S')}")
    
    # GRÁFICOS
    st.markdown("---")
    st.markdown("### 📈 Evolución del Mercado")
    
    fig = make_subplots(rows=2, cols=1, 
                       shared_xaxes=True,
                       vertical_spacing=0.1,
                       subplot_titles=("EUR/USD (Datos REALES)", "Yield Spread"))
    
    fig.add_trace(
        go.Scatter(x=st.session_state.market_data.index, 
                  y=st.session_state.market_data['eurusd_close'],
                  mode='lines',
                  name='EUR/USD',
                  line=dict(color='#1f77b4', width=2)),
        row=1, col=1
    )
    
    components = st.session_state.analysis_result['components']
    spread_value = components.get('yield_spread')
    if spread_value:
        spread_data = [spread_value] * len(st.session_state.market_data)
        fig.add_trace(
            go.Scatter(x=st.session_state.market_data.index,
                      y=spread_data,
                      mode='lines',
                      name='Yield Spread',
                      line=dict(color='#ff7f0e', width=2, dash='dash')),
            row=2, col=1
        )
    else:
        fig.add_annotation(
            text="Datos de bonos no disponibles",
            xref="x2", yref="y2",
            x=0.5, y=0.5,
            showarrow=False,
            row=2, col=1
        )
    
    fig.update_layout(height=600, showlegend=True, title_text="")
    fig.update_xaxes(title_text="Fecha", row=2, col=1)
    fig.update_yaxes(title_text="Precio", row=1, col=1)
    fig.update_yaxes(title_text="Spread (%)", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)

# TAB 2: NOTICIAS
with tab2:
    st.markdown("### 📰 Análisis de Sentimiento de Noticias")
    
    fed_news = st.session_state.data_ingestion.get_news("Federal Reserve OR FOMC OR Powell", days_back=3)
    ecb_news = st.session_state.data_ingestion.get_news("ECB OR Lagarde", days_back=3)
    
    if fed_news or ecb_news:
        all_news = fed_news + ecb_news
        
        news_analysis = []
        for news in all_news[:20]:
            text = f"{news['title']} {news.get('description', '')}"
            score = 0
            impact = ""
            
            text_lower = text.lower()
            if any(word in text_lower for word in ['hawkish', 'tightening', 'hike', 'raise rates']):
                score = 1
                impact = "🔴 USD fuerte"
            elif any(word in text_lower for word in ['dovish', 'cut', 'lower rates', 'pause']):
                score = -1
                impact = "🟢 EUR fuerte"
            else:
                impact = "⚪ Neutral"
            
            news_analysis.append({
                'Fecha': news.get('published_at', '')[:10],
                'Fuente': news.get('source', 'Unknown'),
                'Titular': news.get('title', '')[:100],
                'Impacto': impact,
                'Score': score
            })
        
        df_news = pd.DataFrame(news_analysis)
        if not df_news.empty:
            st.dataframe(df_news, use_container_width=True, hide_index=True)
            
            avg_score = df_news['Score'].mean()
            if avg_score > 0.2:
                st.info("📊 **Interpretación:** Sentimiento general HAWKISH - Fortalece al USD")
            elif avg_score < -0.2:
                st.info("📊 **Interpretación:** Sentimiento general DOVISH - Debilita al USD")
            else:
                st.info("📊 **Interpretación:** Sentimiento NEUTRAL - Sin impacto claro")
        else:
            st.info("No hay noticias para mostrar")
    else:
        st.warning("""
        ⚠️ **No hay noticias disponibles**
        
        Para ver noticias reales, configura tu API key de NewsAPI en el archivo `.env`
        """)

# TAB 3: CALENDARIO
with tab3:
    st.markdown("### 📅 Eventos Económicos Próximos")
    
    events_df = st.session_state.data_ingestion.get_forex_factory_events()
    
    if not events_df.empty:
        display_df = events_df[['fecha', 'evento', 'impacto', 'moneda']].head(10)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.info("💡 **Impacto:** Eventos de alto impacto pueden generar volatilidad significativa en EUR/USD")
    else:
        st.info("No hay eventos programados en los próximos días")

# TAB 4: ZONAS TÉCNICAS
with tab4:
    st.markdown("### 📐 Análisis Técnico (Independiente del Bias Macro)")
    st.caption("Este análisis NO afecta al bias principal - Solo niveles operativos")
    
    # EXPLICACIÓN DE TEMPORALIDADES
    with st.expander("⏰ Temporalidades de esta App", expanded=False):
        st.markdown("""
        | Análisis | Temporalidad | ¿Qué mide? |
        |----------|--------------|------------|
        | **Bias Macro** | Días / Semanas | Tendencias basadas en política monetaria, bonos, noticias |
        | **Zonas Técnicas** | Intradía / 1-5 días | Soportes, resistencias y puntos pivote |
        | **Gráfico de Velas** | 90 días (diario) | Evolución histórica del precio |
        
        ⚠️ **Importante:** No operes un bias macro en temporalidades de minutos.
        """)
    
    # GRÁFICO DE VELAS
    st.markdown("### 📊 Gráfico de Velas - 90 Días")
    
    try:
        df_candles = st.session_state.market_data.copy()
        df_candles = df_candles.tail(90)
        
        fig_candles = go.Figure(data=[
            go.Candlestick(
                x=df_candles.index,
                open=df_candles['eurusd_close'].shift(1).fillna(df_candles['eurusd_close']),
                high=df_candles['eurusd_high'],
                low=df_candles['eurusd_low'],
                close=df_candles['eurusd_close'],
                name='EUR/USD'
            )
        ])
        
        tech_analysis = TechnicalAnalysis(st.session_state.market_data)
        
        for support in tech_analysis.levels.get('supports', []):
            fig_candles.add_hline(y=support, line_dash="dash", line_color="green", 
                                  annotation_text=f"Soporte: {support:.4f}")
        
        for resistance in tech_analysis.levels.get('resistances', []):
            fig_candles.add_hline(y=resistance, line_dash="dash", line_color="red", 
                                  annotation_text=f"Resistencia: {resistance:.4f}")
        
        current_price = st.session_state.market_data['eurusd_close'].iloc[-1]
        fig_candles.add_hline(y=current_price, line_color="blue", line_width=2,
                              annotation_text=f"Actual: {current_price:.5f}")
        
        fig_candles.update_layout(
            title="EUR/USD - Velas Diarias con Soportes/Resistencias",
            yaxis_title="Precio",
            xaxis_title="Fecha",
            height=500,
            template="plotly_dark"
        )
        
        st.plotly_chart(fig_candles, use_container_width=True)
        
    except Exception as e:
        st.warning(f"No se pudo generar el gráfico de velas: {str(e)[:100]}")
    
    # RELACIÓN ENTRE BIAS MACRO Y ANÁLISIS TÉCNICO
    st.markdown("### 🔗 Relación entre Bias Macro y Zonas Técnicas")
    
    bias_type = st.session_state.analysis_result['bias']
    
    if "BULLISH" in bias_type:
        st.info("""
        💡 **Cómo usar esta información:**
        
        - El **bias macro es ALCISTA** (se espera que el EUR suba)
        - Las **zonas técnicas** te muestran DÓNDE podría haber oportunidades de COMPRA
        
        ✅ **Si ambos indican la misma dirección:** Mayor probabilidad de éxito
        """)
    elif "BEARISH" in bias_type:
        st.info("""
        💡 **Cómo usar esta información:**
        
        - El **bias macro es BAJISTA** (se espera que el USD suba / EUR baje)
        - Las **zonas técnicas** te muestran DÓNDE podría haber oportunidades de VENTA
        
        ✅ **Si ambos indican la misma dirección:** Mayor probabilidad de éxito
        """)
    else:
        st.info("""
        💡 **Cómo usar esta información:**
        
        - El **bias macro es NEUTRAL** (sin dirección clara)
        - Las **zonas técnicas** son más relevantes en este contexto
        """)
    
    # CONVERGENCIA DE SEÑALES
    st.markdown("### 🎯 Convergencia de Señales")
    
    buy_zones = [z for z in tech_analysis.generate_trading_zones() if z.get('type') == 'buy_zone']
    sell_zones = [z for z in tech_analysis.generate_trading_zones() if z.get('type') == 'sell_zone']
    
    bias_direction = "bullish" if "BULLISH" in bias_type else "bearish" if "BEARISH" in bias_type else "neutral"
    
    if bias_direction == "bullish" and buy_zones:
        st.success("""
        ✅ **CONVERGENCIA ALCISTA**
        
        - Bias macro: BULLISH (EUR fuerte)
        - Zonas técnicas: COMPRA disponible
        
        **Esto aumenta la probabilidad de éxito** de operaciones largas (comprar EUR/USD)
        """)
    elif bias_direction == "bearish" and sell_zones:
        st.success("""
        ✅ **CONVERGENCIA BAJISTA**
        
        - Bias macro: BEARISH (USD fuerte)
        - Zonas técnicas: VENTA disponible
        
        **Esto aumenta la probabilidad de éxito** de operaciones cortas (vender EUR/USD)
        """)
    else:
        st.info("📊 Señales mixtas o neutrales - Consolidación esperada")
    
    # ZONAS TÉCNICAS MEJORADAS
    st.markdown("---")
    st.markdown("### 📍 Niveles Operativos")
    
    # Obtener análisis técnico actualizado
    tech_analysis = TechnicalAnalysis(st.session_state.market_data)
    current_price = st.session_state.market_data['eurusd_close'].iloc[-1]
    
    # Calcular distancias a niveles clave
    supports = tech_analysis.levels.get('supports', [])
    resistances = tech_analysis.levels.get('resistances', [])
    buy_zones = [z for z in tech_analysis.generate_trading_zones() if z.get('type') == 'buy_zone']
    sell_zones = [z for z in tech_analysis.generate_trading_zones() if z.get('type') == 'sell_zone']
    
    # Determinar situación actual del precio
    nearest_support = supports[0] if supports else None
    nearest_resistance = resistances[0] if resistances else None
    
    # Verificar si hay niveles válidos antes de mostrar
    has_supports = supports and len(supports) > 0
    has_resistances = resistances and len(resistances) > 0
    
    # Determinar situación actual del precio con manejo de None
    if has_supports and has_resistances:
        dist_to_support = abs(current_price - nearest_support) / current_price * 100
        dist_to_resistance = abs(current_price - nearest_resistance) / current_price * 100
        
        if dist_to_support < 0.3:
            price_location = "cerca de SOPORTE"
            location_desc = f"El precio está a solo {dist_to_support:.2f}% del soporte en {nearest_support:.5f}"
            bias_towards = "compra"
        elif dist_to_resistance < 0.3:
            price_location = "cerca de RESISTENCIA"
            location_desc = f"El precio está a solo {dist_to_resistance:.2f}% de la resistencia en {nearest_resistance:.5f}"
            bias_towards = "venta"
        else:
            price_location = "zona NEUTRAL"
            location_desc = f"El precio está entre soporte ({nearest_support:.5f}) y resistencia ({nearest_resistance:.5f})"
            bias_towards = "neutral"
    elif has_supports and not has_resistances:
        price_location = "cerca de SOPORTE"
        dist_to_support = abs(current_price - nearest_support) / current_price * 100
        location_desc = f"El precio está a {dist_to_support:.2f}% del soporte en {nearest_support:.5f}. No hay resistencias claras."
        bias_towards = "compra"
    elif not has_supports and has_resistances:
        price_location = "cerca de RESISTENCIA"
        dist_to_resistance = abs(current_price - nearest_resistance) / current_price * 100
        location_desc = f"El precio está a {dist_to_resistance:.2f}% de la resistencia en {nearest_resistance:.5f}. No hay soportes claros."
        bias_towards = "venta"
    else:
        price_location = "indefinida"
        location_desc = "No hay niveles claros de soporte o resistencia en el rango reciente"
        bias_towards = "neutral"
    
    # Explicación de la situación actual
    st.markdown("#### 📊 Situación Actual del Precio")
    
    if bias_towards == "compra":
        st.info(f"""
        **📍 Precio actual:** {current_price:.5f}
        
        **🔍 Análisis:** {location_desc}
        
        **✅ Conclusión:** El análisis técnico sugiere una **zona de COMPRA** en este nivel.
        """)
        if has_resistances:
            st.info(f"- Próxima resistencia: {nearest_resistance:.5f}")
        if has_supports:
            st.info(f"- Stop loss sugerido: debajo de {nearest_support:.5f}")
            
    elif bias_towards == "venta":
        st.info(f"""
        **📍 Precio actual:** {current_price:.5f}
        
        **🔍 Análisis:** {location_desc}
        
        **✅ Conclusión:** El análisis técnico sugiere una **zona de VENTA** en este nivel.
        """)
        if has_supports:
            st.info(f"- Próximo soporte: {nearest_support:.5f}")
        if has_resistances:
            st.info(f"- Stop loss sugerido: arriba de {nearest_resistance:.5f}")
            
    else:
        st.info(f"""
        **📍 Precio actual:** {current_price:.5f}
        
        **🔍 Análisis:** {location_desc}
        
        **⚪ Conclusión:** El análisis técnico NO muestra una zona clara de compra o venta en el precio actual.
        
        **📋 Recomendación:** Esperar a que el precio llegue a un nivel de soporte o resistencia antes de tomar una decisión.
        """)
        if has_supports:
            st.info(f"- Zona de compra potencial: cerca de {nearest_support:.5f}")
        if has_resistances:
            st.info(f"- Zona de venta potencial: cerca de {nearest_resistance:.5f}")
        if not has_supports and not has_resistances:
            st.info("- No hay niveles técnicos definidos. Considera usar puntos pivote como referencia.")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🛡️ Niveles de Soporte")
        if supports:
            for i, support in enumerate(supports[:5]):
                distance = abs(current_price - support) / current_price * 100
                if distance < 0.3:
                    st.success(f"✅ **Soporte activo:** {support:.5f} (a {distance:.2f}%)")
                else:
                    st.metric(f"Soporte {i+1}", f"{support:.5f}")
        else:
            st.caption("📌 No se detectaron niveles de soporte significativos")
            st.caption("💡 Esto puede deberse a que el precio está en rango o en tendencia fuerte sin retrocesos claros")
        
        st.markdown("#### 🟢 Zona de Compra Potencial")
        if buy_zones:
            for zone in buy_zones:
                st.success(f"""
                **{zone['description']}**
                - Confianza: {zone['confidence']}
                - Distancia: {zone['distance_pct']:.2f}%
                """)
        else:
            st.caption("📌 No hay zona de compra en el precio actual")
            if supports:
                st.caption(f"💡 La zona de compra estaría cerca del soporte en {supports[0]:.5f}")
            else:
                st.caption("💡 No hay soportes cercanos - esperar a que el precio defina un nivel")
    
    with col2:
        st.markdown("#### 🚫 Niveles de Resistencia")
        if resistances:
            for i, resistance in enumerate(resistances[:5]):
                distance = abs(current_price - resistance) / current_price * 100
                if distance < 0.3:
                    st.error(f"⚠️ **Resistencia activa:** {resistance:.5f} (a {distance:.2f}%)")
                else:
                    st.metric(f"Resistencia {i+1}", f"{resistance:.5f}")
        else:
            st.caption("📌 No se detectaron niveles de resistencia significativos")
            st.caption("💡 Esto puede indicar que el precio está en zona de descubrimiento o tendencia alcista fuerte")
        
        st.markdown("#### 🔴 Zona de Venta Potencial")
        if sell_zones:
            for zone in sell_zones:
                st.error(f"""
                **{zone['description']}**
                - Confianza: {zone['confidence']}
                - Distancia: {zone['distance_pct']:.2f}%
                """)
        else:
            st.caption("📌 No hay zona de venta en el precio actual")
            if resistances:
                st.caption(f"💡 La zona de venta estaría cerca de la resistencia en {resistances[0]:.5f}")
            else:
                st.caption("💡 No hay resistencias cercanas - esperar a que el precio defina un nivel")
    
    # Puntos pivote
    st.markdown("---")
    st.markdown("#### 📍 Puntos Pivote Diarios (Clásicos)")
    
    pivots = tech_analysis.get_daily_pivot_points()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("R3", f"{pivots.get('r3', 0):.5f}")
        st.metric("R2", f"{pivots.get('r2', 0):.5f}")
    with col2:
        st.metric("R1", f"{pivots.get('r1', 0):.5f}")
    with col3:
        st.metric("Pivot", f"{pivots.get('pivot', 0):.5f}", delta="Punto central")
    with col4:
        st.metric("S1", f"{pivots.get('s1', 0):.5f}")
    with col5:
        st.metric("S2", f"{pivots.get('s2', 0):.5f}")
        st.metric("S3", f"{pivots.get('s3', 0):.5f}")
    
    # Explicación adicional si no hay zonas claras
    if not buy_zones and not sell_zones:
        st.markdown("---")
        st.markdown("#### 🤔 ¿Por qué no hay zonas claras de compra o venta?")
        
        st.markdown("""
        **Posibles razones:**
        
        1. **El precio está en zona neutral** - No está cerca de ningún soporte o resistencia significativo
        2. **Falta de consolidación previa** - No hay niveles donde el precio haya rebotado múltiples veces
        3. **Rango de precios estrecho** - La volatilidad reciente no ha definido niveles claros
        
        **¿Qué hacer en esta situación?**
        
        - **Si el bias macro es claro** (BULLISH/BEARISH fuerte), espera a que el precio llegue a un nivel técnico
        - **Si el bias macro es neutral**, es mejor no operar hasta que se definan niveles
        - **Usa puntos pivote** como referencia de entrada/salida (ver más arriba)
        """)

# TAB 5: EVOLUCIÓN
with tab5:
    st.markdown("### 🔄 Evolución del Bias (Últimos 7 días)")
    
    bias_history = st.session_state.bias_calculator.get_bias_evolution()
    
    if not bias_history.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=bias_history['timestamp'],
            y=bias_history['score'],
            mode='lines+markers',
            name='Score',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=8)
        ))
        
        fig.add_hline(y=2.5, line_dash="dash", line_color="green", 
                     annotation_text="Bullish threshold")
        fig.add_hline(y=-2.5, line_dash="dash", line_color="red",
                     annotation_text="Bearish threshold")
        fig.add_hline(y=0, line_dash="dot", line_color="gray")
        
        fig.update_layout(
            title="Evolución del Score de Bias",
            xaxis_title="Fecha",
            yaxis_title="Score",
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        bias_history['bias_simplificado'] = bias_history['bias'].apply(lambda x: x.split()[1] if isinstance(x, str) else 'NEUTRAL')
        display_history = bias_history[['timestamp', 'score', 'bias_simplificado']].copy()
        display_history.columns = ['Fecha', 'Score', 'Bias']
        display_history['Fecha'] = display_history['Fecha'].dt.strftime('%d/%m %H:%M')
        
        st.dataframe(display_history, use_container_width=True, hide_index=True)
    else:
        st.info("No hay suficiente historial para mostrar la evolución")

# TAB 6: GLOSARIO
with tab6:
    st.markdown("### 📊 Explicación Rápida: ¿Para qué sirve esta App?")
    
    st.markdown("#### 🎯 Objetivo Principal")
    st.markdown("""
    La app **analiza si el EUR/USD va a subir o bajar** basándose en factores macroeconómicos reales  
    *(no en gráficos ni velas japonesas)*.
    """)
    
    st.markdown("---")
    
    st.markdown("### 🔍 ¿Qué hace exactamente?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 1️⃣ Genera un BIAS (tendencia esperada)")
        st.markdown("""
        Te dice si debes esperar que el Euro se fortalezca o se debilite frente al Dólar:
        
        - 🟢 **BULLISH** → Se espera que el EUR suba frente al USD
        - 🔴 **BEARISH** → Se espera que el EUR baje frente al USD
        - ⚪ **NEUTRAL** → Sin dirección clara
        """)
        
        st.markdown("#### 2️⃣ Te explica POR QUÉ")
        st.markdown("""
        No solo te da una dirección, sino que te dice **qué factores están influyendo**:
        
        - ¿La Fed (banco central USA) está siendo agresiva (hawkish) o cautelosa (dovish)?
        - ¿El BCE (banco central europeo) está subiendo o bajando tipos?
        - ¿Cómo está la diferencia de rendimientos entre bonos USA y Alemania?
        - ¿El mercado está en modo "riesgo" o "aversión al riesgo"?
        """)
    
    with col2:
        st.markdown("#### 3️⃣ Te da zonas para operar (aparte)")
        st.markdown("""
        - **Zonas de compra** (soportes donde el precio podría rebotar)
        - **Zonas de venta** (resistencias donde el precio podría rechazar)
        
        *Esto es **independiente** del análisis macro*
        """)
        
        st.markdown("#### 4️⃣ Te alerta de cambios importantes")
        st.markdown("""
        - Si la Fed cambia su discurso (de agresivo a cauteloso)
        - Si hay eventos económicos de alto impacto próximos
        """)
    
    st.markdown("---")
    
    st.markdown("### 💡 Ejemplo práctico de uso")
    
    st.info("""
    **Situación:**  
    La Fed dice que va a subir tipos agresivamente (hawkish), el BCE se mantiene cauteloso (dovish),  
    y los bonos USA pagan más que los alemanes.
    
    **Qué diría la app:**  
    🔴 **BEARISH** (Confianza: 85%)  
    *"Se espera que el EUR se debilite frente al USD porque la Fed es más agresiva que el BCE"*
    
    **Qué harías tú:**  
    Buscarías oportunidades para vender EUR/USD, apoyándote en las zonas técnicas de resistencia.
    """)
    
    st.markdown("---")
    st.markdown("### 📚 Glosario de Términos")
    
    glosario = {
        "EUR/USD": "El par de divisas que cotiza el Euro frente al Dólar Americano. Es el par más líquido del mundo.",
        "Bias (Sesgo)": "La dirección esperada del mercado basada en análisis macro.",
        "Hawkish": "Tono agresivo del banco central. Indica que podrían subir tipos → Fortalece la moneda.",
        "Dovish": "Tono cauteloso del banco central. Indica que podrían bajar tipos o pausar subidas → Debilita la moneda.",
        "Yield Spread": "Diferencia entre bonos USA y Alemania. Spread positivo → USD más atractivo.",
        "FinBERT": "Modelo de IA que lee noticias financieras.",
        "Risk On / Risk Off": "Cuando el mercado sube (risk-on) el USD tiende a debilitarse.",
        "Resistencia/Soporte": "Niveles donde el precio ha rebotado múltiples veces."
    }
    
    for term, definition in glosario.items():
        with st.expander(f"**{term}**"):
            st.write(definition)
    
    st.markdown("---")
    st.markdown("### 🧠 Fórmula del Score")
    
    st.code("""
score = (
    -(fed_tone_score * 2.5) +    # Fed hawkish → USD fuerte → RESTA
    (ecb_tone_score * 2.0) +     # ECB hawkish → EUR fuerte → SUMA
    -(delta_fed_tone * 2.0) +    # Delta Fed hawkish → RESTA
    (delta_ecb_tone * 1.5) +     # Delta ECB hawkish → SUMA
    -(yield_spread * 2.0) +      # Spread alto → USD fuerte → RESTA
    -(delta_spread * 2.5) +      # Spread aumenta → RESTA
    -(us_macro_score * 0.5) +    # Macro USA fuerte → RESTA
    (eu_macro_score * 0.5) +     # Macro EU fuerte → SUMA
    (risk_score * 0.5)           # Risk-on → SUMA
)
    """, language="python")
    
    st.markdown("""
    **Interpretación del Score:**
    - **> 2.5** → 🟢 BULLISH (EUR fuerte)
    - **< -2.5** → 🔴 BEARISH (USD fuerte)
    - **Entre -2.5 y 2.5** → ⚪ NEUTRAL
    """)

# Footer
st.markdown("---")
st.caption("📊 Análisis Macro para EUR/USD | Fuentes: Yahoo Finance (tiempo real) → Frankfurter API (fallback EOD)")
st.caption("⚠️ **Política de datos:** Prioridad datos en tiempo real de Yahoo Finance. Fallback a datos EOD de Frankfurter con advertencia.")