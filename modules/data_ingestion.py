"""
Módulo 1: Ingesta de datos
Maneja la obtención de datos de mercado, bonos, noticias y eventos
PRIORIDAD: Yahoo Finance (tiempo real) -> Frankfurter (EOD, fallback)
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
import warnings
import time
import yfinance as yf

warnings.filterwarnings('ignore')

from .utils import save_to_cache, load_from_cache, get_cache_key

class DataIngestion:
    def __init__(self, fred_api_key: Optional[str] = None, news_api_key: Optional[str] = None):
        self.fred_api_key = fred_api_key
        self.news_api_key = news_api_key
        self.using_fallback = False
        self.fallback_warning = None
    
    def get_current_price_realtime(self) -> Optional[float]:
        """
        Obtiene el precio ACTUAL de EUR/USD en tiempo real desde Yahoo Finance
        Esta es la fuente principal y más actualizada
        """
        try:
            # Método 1: Usar yfinance con ticker correcto
            ticker = yf.Ticker("EURUSD=X")
            data = ticker.history(period="1d", interval="1m")
            
            if not data.empty:
                current_price = data['Close'].iloc[-1]
                print(f"✅ Precio REAL desde Yahoo Finance: {current_price:.5f}")
                return current_price
            
            # Método 2: Fallback a download
            data = yf.download("EURUSD=X", period="1d", interval="5m", progress=False)
            if not data.empty:
                current_price = data['Close'].iloc[-1]
                print(f"✅ Precio REAL desde Yahoo Finance (download): {current_price:.5f}")
                return current_price
                
        except Exception as e:
            print(f"⚠️ Error obteniendo precio de Yahoo: {e}")
        
        return None
    
    def get_market_data(self, days: int = 90, force_refresh: bool = False) -> pd.DataFrame:
        """
        Obtiene datos de mercado PRIORIZANDO Yahoo Finance (tiempo real)
        Si Yahoo falla, usa Frankfurter con advertencia de retraso
        """
        cache_key = get_cache_key("market", days)
        
        # Resetear estado de fallback
        self.using_fallback = False
        self.fallback_warning = None
        
        # Si no es force refresh, intentar cache
        if not force_refresh:
            cached_data = load_from_cache(cache_key)
            if cached_data is not None and not cached_data.empty:
                # Intentar actualizar el último precio con Yahoo en tiempo real
                real_price = self.get_current_price_realtime()
                if real_price:
                    cached_data.iloc[-1, cached_data.columns.get_loc('eurusd_close')] = real_price
                    cached_data.iloc[-1, cached_data.columns.get_loc('eurusd_high')] = real_price + 0.0005
                    cached_data.iloc[-1, cached_data.columns.get_loc('eurusd_low')] = real_price - 0.0005
                    print(f"✅ Cache actualizado con precio real: {real_price:.5f}")
                    return cached_data
                else:
                    # Cache existe pero no se pudo actualizar
                    print("⚠️ Usando cache - no se pudo obtener precio real")
                    return cached_data
        
        print("📡 Obteniendo datos fresh...")
        
        # ESTRATEGIA 1: Yahoo Finance (tiempo real)
        df = self._get_data_from_yahoo(days)
        
        # ESTRATEGIA 2: Frankfurter (EOD, fallback) si Yahoo falla
        if df is None or df.empty:
            print("⚠️ Yahoo Finance falló, usando Frankfurter API (datos EOD)")
            self.using_fallback = True
            self.fallback_warning = "⚠️ **Advertencia:** Datos con retraso de 1 día (Frankfurter API). Yahoo Finance no está disponible temporalmente."
            df = self._get_data_from_frankfurter(days)
        
        if df is None or df.empty:
            raise ValueError(
                "❌ No se pudieron obtener datos de mercado.\n\n"
                "Todas las fuentes están fallando. Verifica tu conexión a Internet."
            )
        
        # Si estamos en fallback, mostrar advertencia en los datos
        if self.using_fallback:
            df.attrs['warning'] = self.fallback_warning
        
        save_to_cache(cache_key, df, expiry_hours=1)
        return df
    
    def _get_data_from_yahoo(self, days: int) -> Optional[pd.DataFrame]:
        """
        Obtiene datos históricos DE VERDAD de Yahoo Finance
        Esto da velas reales, OHLC completos, no solo closes
        """
        try:
            print("   🔄 Conectando con Yahoo Finance (tiempo real)...")
            
            # Descargar datos históricos con OHLC completo
            ticker = yf.Ticker("EURUSD=X")
            
            # Calcular fecha de inicio
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 5)  # Margen extra
            
            # Descargar datos diarios completos
            data = ticker.history(start=start_date, end=end_date, interval="1d")
            
            if data.empty:
                # Intentar método alternativo
                data = yf.download("EURUSD=X", period=f"{days}d", interval="1d", progress=False)
            
            if data.empty:
                print("   ❌ Yahoo Finance no devolvió datos")
                return None
            
            # Verificar que tenemos las columnas necesarias
            if 'Close' not in data.columns:
                print("   ❌ Datos de Yahoo incompletos")
                return None
            
            # Asegurar que tenemos High y Low (pueden llamarse diferente)
            high_col = 'High' if 'High' in data.columns else 'high'
            low_col = 'Low' if 'Low' in data.columns else 'low'
            
            # Crear DataFrame con OHLC reales
            df = pd.DataFrame({
                'eurusd_close': data['Close'],
                'eurusd_high': data[high_col] if high_col in data else data['Close'],
                'eurusd_low': data[low_col] if low_col in data else data['Close'],
                'spy_close': 4500  # Placeholder, no afecta el bias
            }, index=data.index)
            
            df.dropna(inplace=True)
            
            # Limitar a los días solicitados
            df = df.tail(days)
            
            print(f"   ✅ Yahoo Finance: {len(df)} días de datos REALES")
            print(f"   📊 Último precio REAL: {df['eurusd_close'].iloc[-1]:.5f}")
            print(f"   🕐 Última fecha: {df.index[-1].strftime('%Y-%m-%d %H:%M')}")
            
            return df
            
        except Exception as e:
            print(f"   ❌ Error en Yahoo Finance: {str(e)}")
            return None
    
    def _get_data_from_frankfurter(self, days: int) -> Optional[pd.DataFrame]:
        """
        FALLBACK: Frankfurter API (datos EOD con 1 día de retraso)
        """
        try:
            end_date = datetime.now() - timedelta(days=1)  # Frankfurter tiene 1 día de retraso
            start_date = end_date - timedelta(days=days)
            
            url = f"https://api.frankfurter.app/{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
            params = {
                'from': 'USD',
                'to': 'EUR'
            }
            
            print(f"   Consultando Frankfurter API (datos EOD)...")
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                print(f"   Error HTTP {response.status_code}")
                return None
            
            data = response.json()
            
            if 'rates' not in data or not data['rates']:
                print("   No hay datos de rates")
                return None
            
            rates = data['rates']
            dates = []
            prices = []
            
            for date_str in sorted(rates.keys()):
                rate = rates[date_str]
                if 'EUR' in rate:
                    dates.append(pd.to_datetime(date_str))
                    eur_usd = 1 / rate['EUR']
                    prices.append(eur_usd)
            
            if not prices:
                return None
            
            df = pd.DataFrame({
                'eurusd_close': prices,
                'eurusd_high': prices,
                'eurusd_low': prices,
                'spy_close': 4500
            }, index=dates)
            
            print(f"   ✅ Frankfurter: {len(df)} días (DATOS CON RETRASO - EOD)")
            print(f"   📊 Último precio (con retraso): {prices[-1]:.5f}")
            
            return df if len(df) > 10 else None
            
        except Exception as e:
            print(f"   ❌ Error en Frankfurter: {str(e)}")
            return None
    
    def get_bond_yields(self) -> Tuple[Optional[float], Optional[float]]:
        """Obtiene yields US 2Y y Germany 2Y"""
        if not self.fred_api_key:
            print("⚠️ Sin API key de FRED. No se pueden obtener yields reales.")
            return None, None
        
        try:
            from fredapi import Fred
            fred = Fred(api_key=self.fred_api_key)
            
            us2y_series = fred.get_series('DGS2')
            us2y_current = us2y_series.iloc[-1] if len(us2y_series) > 0 else None
            
            try:
                de2y_series = fred.get_series('IRLTLT01DEM156N')
                de2y_current = de2y_series.iloc[-1] if len(de2y_series) > 0 else None
            except:
                print("⚠️ No se pudo obtener yield de Alemania")
                de2y_current = None
            
            if us2y_current and de2y_current:
                print(f"   ✅ Yields: US 2Y={us2y_current:.2f}%, Germany 2Y={de2y_current:.2f}%")
            
            return us2y_current, de2y_current
            
        except Exception as e:
            print(f"Error obteniendo yields de FRED: {e}")
            return None, None
    
    def get_news(self, query: str, days_back: int = 3) -> List[Dict]:
        """Obtiene noticias de NewsAPI"""
        if not self.news_api_key:
            return []
        
        cache_key = get_cache_key("news", query, days_back)
        cached_news = load_from_cache(cache_key)
        
        if cached_news is not None:
            return cached_news
        
        try:
            from newsapi import NewsApiClient
            newsapi = NewsApiClient(api_key=self.news_api_key)
            
            from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            response = newsapi.get_everything(
                q=query,
                from_param=from_date,
                language='en',
                sort_by='relevancy',
                page_size=20
            )
            
            articles = []
            for article in response.get('articles', []):
                articles.append({
                    'title': article['title'],
                    'description': article['description'] or '',
                    'published_at': article['publishedAt'],
                    'source': article['source']['name']
                })
            
            print(f"   ✅ Obtenidas {len(articles)} noticias")
            save_to_cache(cache_key, articles, expiry_hours=1)
            return articles
            
        except Exception as e:
            print(f"Error obteniendo noticias: {e}")
            return []
    
    """
Módulo 1: Ingesta de datos
Maneja la obtención de datos de mercado, bonos, noticias y eventos
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
import warnings
import time
import yfinance as yf

warnings.filterwarnings('ignore')

from .utils import save_to_cache, load_from_cache, get_cache_key

class DataIngestion:
    def __init__(self, fred_api_key: Optional[str] = None, news_api_key: Optional[str] = None):
        self.fred_api_key = fred_api_key
        self.news_api_key = news_api_key
        self.using_fallback = False
        self.fallback_warning = None
    
    # ============================================================
    # SECCIÓN 1: DATOS DE MERCADO (Yahoo Finance)
    # ============================================================
    
    def get_current_price_realtime(self) -> Optional[float]:
        """Obtiene el precio ACTUAL de EUR/USD en tiempo real desde Yahoo Finance"""
        try:
            ticker = yf.Ticker("EURUSD=X")
            data = ticker.history(period="1d", interval="1m")
            
            if not data.empty:
                current_price = data['Close'].iloc[-1]
                print(f"✅ Precio REAL desde Yahoo Finance: {current_price:.5f}")
                return current_price
            
            data = yf.download("EURUSD=X", period="1d", interval="5m", progress=False)
            if not data.empty:
                current_price = data['Close'].iloc[-1]
                print(f"✅ Precio REAL desde Yahoo Finance (download): {current_price:.5f}")
                return current_price
                
        except Exception as e:
            print(f"⚠️ Error obteniendo precio de Yahoo: {e}")
        
        return None
    
    def get_market_data(self, days: int = 90, force_refresh: bool = False) -> pd.DataFrame:
        """Obtiene datos de mercado priorizando Yahoo Finance"""
        cache_key = get_cache_key("market", days)
        
        self.using_fallback = False
        self.fallback_warning = None
        
        if not force_refresh:
            cached_data = load_from_cache(cache_key)
            if cached_data is not None and not cached_data.empty:
                real_price = self.get_current_price_realtime()
                if real_price:
                    cached_data.iloc[-1, cached_data.columns.get_loc('eurusd_close')] = real_price
                    cached_data.iloc[-1, cached_data.columns.get_loc('eurusd_high')] = real_price + 0.0005
                    cached_data.iloc[-1, cached_data.columns.get_loc('eurusd_low')] = real_price - 0.0005
                    print(f"✅ Cache actualizado con precio real: {real_price:.5f}")
                    return cached_data
                else:
                    print("⚠️ Usando cache - no se pudo obtener precio real")
                    return cached_data
        
        print("📡 Obteniendo datos fresh...")
        
        df = self._get_data_from_yahoo(days)
        
        if df is None or df.empty:
            print("⚠️ Yahoo Finance falló, usando Frankfurter API (datos EOD)")
            self.using_fallback = True
            self.fallback_warning = "⚠️ **Advertencia:** Datos con retraso de 1 día (Frankfurter API). Yahoo Finance no está disponible temporalmente."
            df = self._get_data_from_frankfurter(days)
        
        if df is None or df.empty:
            raise ValueError("❌ No se pudieron obtener datos de mercado.")
        
        if self.using_fallback:
            df.attrs['warning'] = self.fallback_warning
        
        save_to_cache(cache_key, df, expiry_hours=1)
        return df
    
    def _get_data_from_yahoo(self, days: int) -> Optional[pd.DataFrame]:
        """Obtiene datos históricos de Yahoo Finance"""
        try:
            print("   🔄 Conectando con Yahoo Finance...")
            
            ticker = yf.Ticker("EURUSD=X")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 5)
            
            data = ticker.history(start=start_date, end=end_date, interval="1d")
            
            if data.empty:
                data = yf.download("EURUSD=X", period=f"{days}d", interval="1d", progress=False)
            
            if data.empty:
                print("   ❌ Yahoo Finance no devolvió datos")
                return None
            
            df = pd.DataFrame({
                'eurusd_close': data['Close'],
                'eurusd_high': data['High'] if 'High' in data else data['Close'],
                'eurusd_low': data['Low'] if 'Low' in data else data['Close'],
                'spy_close': 4500
            }, index=data.index)
            
            df.dropna(inplace=True)
            df = df.tail(days)
            
            print(f"   ✅ Yahoo Finance: {len(df)} días de datos")
            print(f"   📊 Último precio: {df['eurusd_close'].iloc[-1]:.5f}")
            
            return df
            
        except Exception as e:
            print(f"   ❌ Error en Yahoo Finance: {str(e)}")
            return None
    
    def _get_data_from_frankfurter(self, days: int) -> Optional[pd.DataFrame]:
        """FALLBACK: Frankfurter API (datos EOD)"""
        try:
            end_date = datetime.now() - timedelta(days=1)
            start_date = end_date - timedelta(days=days)
            
            url = f"https://api.frankfurter.app/{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
            params = {'from': 'USD', 'to': 'EUR'}
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if 'rates' not in data or not data['rates']:
                return None
            
            rates = data['rates']
            dates = []
            prices = []
            
            for date_str in sorted(rates.keys()):
                rate = rates[date_str]
                if 'EUR' in rate:
                    dates.append(pd.to_datetime(date_str))
                    prices.append(1 / rate['EUR'])
            
            if not prices:
                return None
            
            df = pd.DataFrame({
                'eurusd_close': prices,
                'eurusd_high': prices,
                'eurusd_low': prices,
                'spy_close': 4500
            }, index=dates)
            
            print(f"   ✅ Frankfurter: {len(df)} días (datos EOD)")
            
            return df if len(df) > 10 else None
            
        except Exception as e:
            print(f"   ❌ Error en Frankfurter: {str(e)}")
            return None
    
    # ============================================================
    # SECCIÓN 2: BONOS (FRED API)
    # ============================================================
    
    def get_bond_yields(self) -> Tuple[Optional[float], Optional[float]]:
        """Obtiene yields US 2Y y Germany 2Y"""
        if not self.fred_api_key:
            print("⚠️ Sin API key de FRED.")
            return None, None
        
        try:
            from fredapi import Fred
            fred = Fred(api_key=self.fred_api_key)
            
            us2y_series = fred.get_series('DGS2')
            us2y_current = us2y_series.iloc[-1] if len(us2y_series) > 0 else None
            
            try:
                de2y_series = fred.get_series('IRLTLT01DEM156N')
                de2y_current = de2y_series.iloc[-1] if len(de2y_series) > 0 else None
            except:
                de2y_current = None
            
            if us2y_current and de2y_current:
                print(f"   ✅ Yields: US 2Y={us2y_current:.2f}%, Germany 2Y={de2y_current:.2f}%")
            
            return us2y_current, de2y_current
            
        except Exception as e:
            print(f"Error obteniendo yields: {e}")
            return None, None
    
    # ============================================================
    # SECCIÓN 3: NOTICIAS (NewsAPI)
    # ============================================================
    
    def get_news(self, query: str, days_back: int = 3) -> List[Dict]:
        """Obtiene noticias de NewsAPI"""
        if not self.news_api_key:
            return []
        
        cache_key = get_cache_key("news", query, days_back)
        cached_news = load_from_cache(cache_key)
        
        if cached_news is not None:
            return cached_news
        
        try:
            from newsapi import NewsApiClient
            newsapi = NewsApiClient(api_key=self.news_api_key)
            
            from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            
            response = newsapi.get_everything(
                q=query,
                from_param=from_date,
                language='en',
                sort_by='relevancy',
                page_size=20
            )
            
            articles = []
            for article in response.get('articles', []):
                articles.append({
                    'title': article['title'],
                    'description': article['description'] or '',
                    'published_at': article['publishedAt'],
                    'source': article['source']['name']
                })
            
            print(f"   ✅ Obtenidas {len(articles)} noticias")
            save_to_cache(cache_key, articles, expiry_hours=1)
            return articles
            
        except Exception as e:
            print(f"Error obteniendo noticias: {e}")
            return []
    
    # ============================================================
    # SECCIÓN 4: CALENDARIO DE EVENTOS (NUEVO - CON FILTROS)
    # ============================================================
    
    def get_calendar_events(self) -> pd.DataFrame:
        """
        Obtiene eventos de la SEMANA ACTUAL (lunes a domingo)
        - Filtra eventos de BAJO impacto (no se muestran)
        - Eventos pasados en gris
        - Solo eventos que afectan USD/EUR
        """
        cache_key = get_cache_key("calendar_week")
        cached_events = load_from_cache(cache_key)
        
        if cached_events is not None:
            return cached_events
        
        print("📅 Obteniendo calendario de eventos...")
        
        # Obtener eventos de múltiples fuentes
        events = self._fetch_events_from_forexfactory()
        
        if not events:
            events = self._fetch_events_from_investing()
        
        if not events:
            events = self._get_default_weekly_events()
        
        if not events:
            return pd.DataFrame()
        
        # Convertir a DataFrame
        df = pd.DataFrame(events)
        
        # Filtrar por semana actual (lunes a domingo)
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        
        df = df[(df['fecha'] >= monday) & (df['fecha'] <= sunday)]
        
        # Filtrar eventos de BAJO impacto (excluir Low)
        df = df[df['impacto'] != 'Low']
        
        # Ordenar por fecha y hora
        df = df.sort_values(['fecha', 'hora'])
        
        # Calcular estado (pasado/futuro)
        now = datetime.now()
        df['estado'] = df.apply(
            lambda row: 'pasado' if (row['fecha'] < now.date()) or 
                        (row['fecha'] == now.date() and self._is_time_passed(row['hora'])) 
                        else 'futuro',
            axis=1
        )
        
        # Solo eventos pasados tienen detalles (actual/forecast/previous)
        for idx in df.index:
            if df.loc[idx, 'estado'] == 'futuro':
                df.loc[idx, 'actual'] = '-'
                df.loc[idx, 'forecast'] = '-'
                df.loc[idx, 'previous'] = '-'
        
        # Renombrar columnas para la UI
        df = df.rename(columns={
            'fecha': 'Fecha',
            'hora': 'Hora',
            'evento': 'Evento',
            'moneda': 'Moneda',
            'impacto': 'Impacto',
            'impacto_icon': 'Icono',
            'actual': 'Actual',
            'forecast': 'Pronóstico',
            'previous': 'Anterior',
            'estado': 'Estado'
        })
        
        save_to_cache(cache_key, df, expiry_hours=6)
        
        print(f"   ✅ {len(df)} eventos para esta semana (lunes a domingo)")
        
        return df
    
    def _is_time_passed(self, time_str: str) -> bool:
        """Verifica si una hora ya pasó hoy"""
        if not time_str or time_str == 'TBD' or ':' not in time_str:
            return False
        
        try:
            # Extraer hora (formato "14:30" o "2:30pm")
            if 'pm' in time_str.lower() or 'am' in time_str.lower():
                from dateutil import parser
                time_obj = parser.parse(time_str).time()
            else:
                hour, minute = map(int, time_str.split(':')[:2])
                time_obj = datetime.now().replace(hour=hour, minute=minute, second=0).time()
            
            now = datetime.now().time()
            return time_obj < now
        except:
            return False
    
    def _fetch_events_from_forexfactory(self) -> List[Dict]:
        """Scrapea eventos de ForexFactory filtrando por impacto"""
        try:
            url = "https://www.forexfactory.com/calendar"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            events = []
            today = datetime.now().date()
            
            for row in soup.find_all('tr', class_='calendar__row'):
                try:
                    # Verificar moneda (solo USD/EUR)
                    currency_elem = row.find('td', class_='calendar__currency')
                    if not currency_elem or currency_elem.text not in ['USD', 'EUR']:
                        continue
                    
                    # Verificar impacto (excluir Low)
                    impact_elem = row.find('td', class_='calendar__impact')
                    impact_icon = impact_elem.find('span', class_='calendar__impact-icon') if impact_elem else None
                    
                    if impact_icon:
                        impact_title = impact_icon.get('title', '')
                        if 'Low' in impact_title:
                            continue  # Saltar eventos de bajo impacto
                        
                        if 'High' in impact_title:
                            impacto = 'High'
                            icono = '🔴'
                        else:
                            impacto = 'Medium'
                            icono = '🟡'
                    else:
                        impacto = 'Medium'
                        icono = '🟡'
                    
                    # Fecha
                    date_elem = row.find('td', class_='calendar__date')
                    if date_elem:
                        date_text = date_elem.get('data-date', '')
                        if date_text:
                            event_date = datetime.strptime(date_text, '%Y-%m-%d').date()
                        else:
                            continue
                    else:
                        continue
                    
                    # Hora
                    time_elem = row.find('td', class_='calendar__time')
                    event_time = time_elem.text.strip() if time_elem else 'TBD'
                    
                    # Evento
                    event_elem = row.find('td', class_='calendar__event')
                    event_name = event_elem.text.strip() if event_elem else 'Unknown'
                    
                    # Actual, Forecast, Previous (solo si el evento ya pasó)
                    actual_elem = row.find('td', class_='calendar__actual')
                    forecast_elem = row.find('td', class_='calendar__forecast')
                    previous_elem = row.find('td', class_='calendar__previous')
                    
                    actual = actual_elem.text.strip() if actual_elem else '-'
                    forecast = forecast_elem.text.strip() if forecast_elem else '-'
                    previous = previous_elem.text.strip() if previous_elem else '-'
                    
                    events.append({
                        'fecha': event_date,
                        'hora': event_time,
                        'evento': event_name,
                        'moneda': currency_elem.text,
                        'impacto': impacto,
                        'impacto_icon': icono,
                        'actual': actual if actual else '-',
                        'forecast': forecast if forecast else '-',
                        'previous': previous if previous else '-'
                    })
                    
                except Exception as e:
                    continue
            
            return events
            
        except Exception as e:
            print(f"Error en ForexFactory: {e}")
            return []
    
    def _fetch_events_from_investing(self) -> List[Dict]:
        """Obtiene eventos de Investing.com"""
        try:
            url = "https://m.investing.com/economic-calendar/"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            events = []
            today = datetime.now().date()
            
            for row in soup.find_all('tr', class_='js-event-row')[:60]:
                try:
                    # Moneda
                    flag_elem = row.find('td', class_='flag')
                    if 'us' in str(flag_elem).lower():
                        currency = 'USD'
                    elif 'fr' in str(flag_elem).lower() or 'de' in str(flag_elem).lower():
                        currency = 'EUR'
                    else:
                        continue
                    
                    # Impacto
                    impact_elem = row.find('td', class_='impact')
                    if impact_elem:
                        impact_text = impact_elem.get('class', [])
                        if 'high' in str(impact_text).lower():
                            impacto = 'High'
                            icono = '🔴'
                        elif 'medium' in str(impact_text).lower():
                            impacto = 'Medium'
                            icono = '🟡'
                        else:
                            continue  # Saltar bajo impacto
                    else:
                        continue
                    
                    # Fecha
                    date_elem = row.find('td', class_='date')
                    if date_elem:
                        date_text = date_elem.text.strip()
                        if 'Today' in date_text:
                            event_date = today
                        elif 'Tomorrow' in date_text:
                            event_date = today + timedelta(days=1)
                        else:
                            try:
                                event_date = datetime.strptime(date_text, '%b %d, %Y').date()
                            except:
                                continue
                    else:
                        continue
                    
                    # Hora
                    time_elem = row.find('td', class_='time')
                    event_time = time_elem.text.strip() if time_elem else 'TBD'
                    
                    # Evento
                    event_elem = row.find('td', class_='event')
                    event_name = event_elem.text.strip() if event_elem else 'Unknown'
                    
                    # Datos
                    actual_elem = row.find('td', class_='actual')
                    forecast_elem = row.find('td', class_='forecast')
                    previous_elem = row.find('td', class_='previous')
                    
                    events.append({
                        'fecha': event_date,
                        'hora': event_time,
                        'evento': event_name,
                        'moneda': currency,
                        'impacto': impacto,
                        'impacto_icon': icono,
                        'actual': actual_elem.text.strip() if actual_elem else '-',
                        'forecast': forecast_elem.text.strip() if forecast_elem else '-',
                        'previous': previous_elem.text.strip() if previous_elem else '-'
                    })
                    
                except Exception:
                    continue
            
            return events
            
        except Exception as e:
            print(f"Error en Investing.com: {e}")
            return []
    
    def _get_default_weekly_events(self) -> List[Dict]:
        """Eventos por defecto para la semana actual (fallback)"""
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        
        events = []
        
        # Eventos estándar de la semana (lunes a viernes)
        default_events = {
            0: [  # Lunes
                ('USD', 'ISM Manufacturing PMI', 'Medium', '🟡', '15:00'),
                ('EUR', 'German CPI (YoY)', 'Medium', '🟡', '14:00'),
            ],
            1: [  # Martes
                ('USD', 'JOLTS Job Openings', 'Medium', '🟡', '15:00'),
                ('EUR', 'Eurozone CPI (YoY)', 'High', '🔴', '11:00'),
            ],
            2: [  # Miércoles
                ('USD', 'ADP Non-Farm Employment Change', 'Medium', '🟡', '13:15'),
                ('USD', 'ISM Services PMI', 'Medium', '🟡', '15:00'),
            ],
            3: [  # Jueves
                ('USD', 'Unemployment Claims', 'Medium', '🟡', '13:30'),
                ('EUR', 'ECB President Lagarde Speaks', 'Medium', '🟡', '14:00'),
            ],
            4: [  # Viernes
                ('USD', 'Non-Farm Employment Change', 'High', '🔴', '13:30'),
                ('USD', 'Unemployment Rate', 'High', '🔴', '13:30'),
                ('EUR', 'German GDP (YoY)', 'Medium', '🟡', '07:00'),
            ],
        }
        
        for weekday, day_events in default_events.items():
            event_date = monday + timedelta(days=weekday)
            if event_date >= today - timedelta(days=1):  # Incluir desde ayer
                for currency, name, impact, icon, hour in day_events:
                    events.append({
                        'fecha': event_date,
                        'hora': hour,
                        'evento': name,
                        'moneda': currency,
                        'impacto': impact,
                        'impacto_icon': icon,
                        'actual': '-',
                        'forecast': '-',
                        'previous': '-'
                    })
        
        return events