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
    
    def get_forex_factory_events(self) -> pd.DataFrame:
        """Scrapea eventos de ForexFactory"""
        cache_key = get_cache_key("forexfactory")
        cached_events = load_from_cache(cache_key)
        
        if cached_events is not None:
            return cached_events
        
        try:
            url = "https://www.forexfactory.com/calendar"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            events = []
            for row in soup.find_all('tr', class_='calendar__row'):
                try:
                    currency = row.find('td', class_='calendar__currency')
                    if currency and currency.text in ['USD', 'EUR']:
                        event_name = row.find('td', class_='calendar__event')
                        impact = row.find('td', class_='calendar__impact')
                        time_elem = row.find('td', class_='calendar__time')
                        
                        if event_name and impact:
                            events.append({
                                'fecha': datetime.now().strftime('%Y-%m-%d'),
                                'evento': event_name.text.strip(),
                                'impacto': impact.get('title', 'Medium'),
                                'moneda': currency.text.strip(),
                                'hora': time_elem.text.strip() if time_elem else 'N/A'
                            })
                except Exception:
                    continue
            
            df = pd.DataFrame(events)
            save_to_cache(cache_key, df, expiry_hours=6)
            print(f"   ✅ Obtenidos {len(df)} eventos económicos")
            return df if not df.empty else pd.DataFrame()
            
        except Exception as e:
            print(f"Error scraping ForexFactory: {e}")
            return pd.DataFrame()