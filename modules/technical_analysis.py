"""
Módulo de análisis técnico - COMPLETAMENTE SEPARADO del bias macro
CORREGIDO: Pivotes bien calculados
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Dict

class TechnicalAnalysis:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.levels = self._calculate_levels()
    
    def _calculate_levels(self) -> Dict:
        """Calcula soportes y resistencias basados en máximos/mínimos recientes"""
        if self.df.empty:
            return {'supports': [], 'resistances': []}
        
        prices = self.df['eurusd_close'].values
        highs = self.df['eurusd_high'].values
        lows = self.df['eurusd_low'].values
        
        # Identificar máximos y mínimos locales (30-60 días)
        lookback = min(30, len(prices) // 3)
        
        resistances = []
        supports = []
        
        for i in range(lookback, len(prices) - lookback):
            # Resistencia: precio alto que no ha sido superado
            if highs[i] == max(highs[i-lookback:i+lookback]):
                resistances.append(prices[i])
            
            # Soporte: precio bajo que no ha sido perforado
            if lows[i] == min(lows[i-lookback:i+lookback]):
                supports.append(prices[i])
        
        # Agrupar niveles cercanos
        resistances = self._cluster_levels(resistances, tolerance=0.002)
        supports = self._cluster_levels(supports, tolerance=0.002)
        
        # Ordenar y tomar los más significativos
        resistances = sorted(set(resistances), reverse=True)[:5]
        supports = sorted(set(supports))[:5]
        
        # Calcular zonas de consolidación
        consolidation_zones = self._find_consolidation_zones()
        
        return {
            'supports': supports,
            'resistances': resistances,
            'consolidation_zones': consolidation_zones,
            'current_price': prices[-1]
        }
    
    def _cluster_levels(self, levels: List[float], tolerance: float) -> List[float]:
        """Agrupa niveles cercanos"""
        if not levels:
            return []
        
        levels = sorted(levels)
        clustered = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if level - current_cluster[-1] <= tolerance * current_cluster[-1]:
                current_cluster.append(level)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [level]
        
        if current_cluster:
            clustered.append(np.mean(current_cluster))
        
        return clustered
    
    def _find_consolidation_zones(self) -> List[Dict]:
        """Identifica zonas de consolidación"""
        consolidation_zones = []
        window = 20
        
        if len(self.df) < window:
            return []
        
        for i in range(0, len(self.df) - window, 5):
            segment = self.df.iloc[i:i+window]
            price_range = (segment['eurusd_high'].max() - segment['eurusd_low'].min()) / segment['eurusd_low'].min()
            
            # Consolidación si rango pequeño (< 1.5%)
            if price_range < 0.015:
                consolidation_zones.append({
                    'level': segment['eurusd_close'].mean(),
                    'range_pct': price_range * 100,
                    'start_date': segment.index[0],
                    'end_date': segment.index[-1]
                })
        
        return consolidation_zones[:3]
    
    def generate_trading_zones(self) -> List[Dict]:
        """Genera zonas operativas basadas en niveles técnicos con explicación"""
        zones = []
        current_price = self.levels['current_price']
        
        # Calcular ATR aproximado para medir volatilidad
        try:
            if len(self.df) > 14:
                highs = self.df['eurusd_high'].iloc[-14:]
                lows = self.df['eurusd_low'].iloc[-14:]
                closes = self.df['eurusd_close'].iloc[-14:]
                true_range = []
                for i in range(1, len(closes)):
                    tr = max(
                        highs.iloc[i] - lows.iloc[i],
                        abs(highs.iloc[i] - closes.iloc[i-1]),
                        abs(lows.iloc[i] - closes.iloc[i-1])
                    )
                    true_range.append(tr)
                atr = sum(true_range) / len(true_range) if true_range else 0.002
            else:
                atr = 0.002  # Valor por defecto
        except:
            atr = 0.002
        
        # Zonas de compra (soportes cercanos)
        for support in self.levels['supports']:
            distance_pct = abs(support - current_price) / current_price * 100
            
            # Solo considerar si está dentro de 1 ATR
            if abs(support - current_price) <= atr:
                zones.append({
                    'type': 'buy_zone',
                    'level': support,
                    'description': f"Zona de compra potencial en {support:.5f}",
                    'confidence': 'Alta' if distance_pct < 0.3 else 'Media',
                    'distance_pct': distance_pct,
                    'reason': f"Soporte identificado a {distance_pct:.2f}% del precio actual"
                })
        
        # Zonas de venta (resistencias cercanas)
        for resistance in self.levels['resistances']:
            distance_pct = abs(resistance - current_price) / current_price * 100
            
            # Solo considerar si está dentro de 1 ATR
            if abs(resistance - current_price) <= atr:
                zones.append({
                    'type': 'sell_zone',
                    'level': resistance,
                    'description': f"Zona de venta potencial en {resistance:.5f}",
                    'confidence': 'Alta' if distance_pct < 0.3 else 'Media',
                    'distance_pct': distance_pct,
                    'reason': f"Resistencia identificada a {distance_pct:.2f}% del precio actual"
                })
        
        return zones
    
    def get_daily_pivot_points(self) -> Dict:
        """Calcula puntos pivote diarios - CORREGIDO"""
        if len(self.df) < 2:
            return self._get_default_pivots()
        
        last_day = self.df.iloc[-1]
        high = last_day['eurusd_high']
        low = last_day['eurusd_low']
        close = last_day['eurusd_close']
        
        # Fórmula clásica de puntos pivote
        pivot = (high + low + close) / 3
        
        r1 = 2 * pivot - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        
        s1 = 2 * pivot - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }
    
    def _get_default_pivots(self) -> Dict:
        """Valores por defecto si no hay datos suficientes"""
        current_price = self.levels['current_price'] if self.levels else 1.1700
        return {
            'pivot': current_price,
            'r1': current_price + 0.0025,
            'r2': current_price + 0.0050,
            'r3': current_price + 0.0075,
            's1': current_price - 0.0025,
            's2': current_price - 0.0050,
            's3': current_price - 0.0075
        }