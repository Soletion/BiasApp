"""
Módulo 2: Procesamiento y cálculo del bias macro
REFACTORIZADO - SIGNO CORREGIDO: Lo que fortalece USD resta al EUR/USD
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional, List
from datetime import datetime, timedelta
from collections import deque

class MacroBiasCalculator:
    def __init__(self, history_days: int = 7):
        self.bias_history = []
        self.fed_history = deque(maxlen=history_days)
        self.ecb_history = deque(maxlen=history_days)
        self.spread_history = deque(maxlen=history_days)
        
    def calculate_bias_score(self, 
                            fed_tone: float,
                            ecb_tone: float,
                            us2y: Optional[float],
                            de2y: Optional[float],
                            macro_data: Dict,
                            spy_change: float) -> Dict:
        """
        Calcula el score final con LÓGICA CORREGIDA:
        - Positivo = EUR fuerte
        - Negativo = USD fuerte
        """
        
        # 1. MEJORAR ECB TONE - Nunca debe ser 0
        ecb_tone = self._improve_ecb_tone(ecb_tone)
        
        # 2. Tone scores con signo CORREGIDO
        # FED hawkish → USD fuerte → RESTA (-)
        fed_score = -(fed_tone * 2.5)
        
        # ECB hawkish → EUR fuerte → SUMA (+)
        ecb_score = ecb_tone * 2.0
        
        # 3. Cambio de narrativa (deltas)
        delta_fed = self._calculate_delta(fed_tone, 'fed')
        delta_ecb = self._calculate_delta(ecb_tone, 'ecb')
        
        # Delta Fed hawkish (positivo) → USD más fuerte → RESTA (-)
        delta_fed_score = -(delta_fed * 2.0)
        
        # Delta ECB hawkish (positivo) → EUR más fuerte → SUMA (+)
        delta_ecb_score = delta_ecb * 1.5
        
        # 4. Bonos
        if us2y and de2y:
            yield_spread = us2y - de2y
            # Spread positivo → USD más atractivo → RESTA (-)
            spread_normalized = max(min(yield_spread / 3, 1), -1)
            spread_score = -(spread_normalized * 2.0)
            
            delta_spread = self._calculate_spread_delta(yield_spread)
            # Delta spread positivo (spread aumentando) → USD más fuerte → RESTA (-)
            delta_spread_score = -(delta_spread * 2.5)
        else:
            spread_score = 0
            delta_spread_score = 0
            yield_spread = None
        
        # 5. Macro (peso reducido)
        us_macro_score = self._calculate_macro_score(macro_data.get('us', {})) * 0.5
        eu_macro_score = self._calculate_macro_score(macro_data.get('eu', {})) * 0.5
        
        # Macro USA fuerte → USD fuerte → RESTA (-)
        # Macro EU fuerte → EUR fuerte → SUMA (+)
        macro_score = -us_macro_score + eu_macro_score
        
        # 6. Risk score
        # Risk-on (SPY sube) → USD débil → SUMA (+)
        # Risk-off (SPY baja) → USD fuerte → RESTA (-)
        risk_score = 1 if spy_change > 0 else -1 if spy_change < 0 else 0
        risk_adjustment = risk_score * 0.5  # Risk-on suma, risk-off resta
        
        # SCORE FINAL CON LÓGICA CORREGIDA
        # Positivo = EUR fuerte, Negativo = USD fuerte
        score = (
            fed_score +              # NEGATIVO si Fed hawkish
            ecb_score +              # POSITIVO si ECB hawkish
            delta_fed_score +        # NEGATIVO si Fed se vuelve hawkish
            delta_ecb_score +        # POSITIVO si ECB se vuelve hawkish
            spread_score +           # NEGATIVO si spread alto
            delta_spread_score +     # NEGATIVO si spread aumenta
            macro_score +            # MACRO: US resta, EU suma
            risk_adjustment          # Risk-on suma, risk-off resta
        )
        
        # Guardar historial
        self.fed_history.append(fed_tone)
        self.ecb_history.append(ecb_tone)
        if yield_spread:
            self.spread_history.append(yield_spread)
        
        # Clasificación (sin cambios, ya funciona correctamente)
        bias, direction, sub_bias = self._classify_bias(score)
        confidence = min(abs(score) * 15, 100)
        
        # Detección de giros (ajustada para la nueva lógica)
        alerts = self._detect_turns_improved(delta_fed, delta_ecb, delta_spread, yield_spread)
        
        # Guardar historial de bias
        self.bias_history.append({
            'timestamp': datetime.now(),
            'score': score,
            'bias': bias,
            'sub_bias': sub_bias
        })
        self.bias_history = self.bias_history[-7:]
        
        # Calcular contribuciones para breakdown (ahora con signo correcto)
        contributions = {
            'fed': fed_score,
            'ecb': ecb_score,
            'delta_fed': delta_fed_score,
            'delta_ecb': delta_ecb_score,
            'spread': spread_score,
            'delta_spread': delta_spread_score,
            'us_macro': -us_macro_score,  # Mostrar impacto real
            'eu_macro': eu_macro_score,
            'risk': risk_adjustment
        }
        
        return {
            'score': score,
            'bias': bias,
            'direction': direction,
            'sub_bias': sub_bias,
            'confidence': confidence,
            'explanation': self._generate_professional_explanation(score, contributions, alerts, fed_tone, ecb_tone, yield_spread),
            'alerts': alerts,
            'components': {
                'fed_tone': fed_tone,
                'ecb_tone': ecb_tone,
                'fed_delta': delta_fed,
                'ecb_delta': delta_ecb,
                'yield_spread': yield_spread,
                'spread_delta': delta_spread,
                'us_macro': us_macro_score / 0.5 if us_macro_score else 0,
                'eu_macro': eu_macro_score / 0.5 if eu_macro_score else 0,
                'risk': risk_score
            },
            'contributions': contributions
        }
    
    def _improve_ecb_tone(self, ecb_tone: float) -> float:
        """Nunca devolver 0 para ECB tone"""
        if ecb_tone == 0 or ecb_tone is None:
            if len(self.ecb_history) > 0:
                historical_avg = sum(self.ecb_history) / len(self.ecb_history)
                return historical_avg
            else:
                return 0.15  # Ligéramente dovish por defecto
        return ecb_tone
    
    def _calculate_delta(self, current: float, series_name: str) -> float:
        """Calcula cambio vs media móvil"""
        if series_name == 'fed':
            history = list(self.fed_history)
        elif series_name == 'ecb':
            history = list(self.ecb_history)
        else:
            return 0
        
        if len(history) < 3:
            return 0
        
        lookback = min(5, len(history))
        historical_avg = sum(list(history)[-lookback:]) / lookback
        delta = current - historical_avg
        
        return max(min(delta, 0.5), -0.5)
    
    def _calculate_spread_delta(self, current_spread: float) -> float:
        """Calcula cambio del spread vs media 5 días"""
        if len(self.spread_history) < 3:
            return 0
        
        lookback = min(5, len(self.spread_history))
        historical_avg = sum(list(self.spread_history)[-lookback:]) / lookback
        delta = current_spread - historical_avg
        
        return max(min(delta / 0.5, 0.5), -0.5)
    
    def _calculate_macro_score(self, macro_data: Dict) -> float:
        """Calcula macro score con impacto reducido"""
        if not macro_data:
            return 0
        
        score = 0
        if macro_data.get('gdp_surprise', 0) > 0:
            score += 0.25
        elif macro_data.get('gdp_surprise', 0) < 0:
            score -= 0.25
        
        inflation = macro_data.get('inflation', 2)
        if inflation > 2.5:
            score += 0.25
        elif inflation < 1.5:
            score -= 0.25
        
        return max(min(score, 1), -1)
    
    def _classify_bias(self, score: float) -> Tuple[str, str, str]:
        """Clasificación según EUR/USD (positivo = EUR fuerte)"""
        if score > 2.5:
            return "🟢 BULLISH", "Alcista (EUR fuerte)", "Fuerte"
        elif score > 1.0:
            return "🟢 BULLISH", "Alcista (EUR fuerte)", "Moderado"
        elif score < -2.5:
            return "🔴 BEARISH", "Bajista (USD fuerte)", "Fuerte"
        elif score < -1.0:
            return "🔴 BEARISH", "Bajista (USD fuerte)", "Moderado"
        elif score > 0.5:
            return "⚪ NEUTRAL", "Neutral", "con sesgo alcista (EUR)"
        elif score < -0.5:
            return "⚪ NEUTRAL", "Neutral", "con sesgo bajista (USD)"
        else:
            return "⚪ NEUTRAL", "Neutral", "sin dirección clara"
    
    def _detect_turns_improved(self, delta_fed: float, delta_ecb: float, 
                                delta_spread: float, yield_spread: Optional[float]) -> list:
        """Detección de giros con lógica corregida"""
        alerts = []
        
        # Giro dovish en USD → potencialmente BULLISH para EUR/USD
        if delta_fed < -0.1 and delta_spread < 0:
            alerts.append({
                'type': 'dovish_usd_turn',
                'message': '⚠️ Posible giro dovish en USD - La Fed moderaría tono y los spreads caen (potencialmente BULLISH para EUR/USD)',
                'severity': 'high',
                'impact': 'Podría fortalecer al EUR en próximas sesiones'
            })
        elif delta_fed < -0.05 and delta_spread < 0:
            alerts.append({
                'type': 'dovish_usd_warning',
                'message': '⚠️ Señal temprana: posible giro dovish en USD',
                'severity': 'medium',
                'impact': 'Vigilar evolución de spreads y discurso de la Fed'
            })
        
        # Giro hawkish en ECB → potencialmente BULLISH para EUR/USD
        if delta_ecb > 0.1 and delta_spread < 0:
            alerts.append({
                'type': 'eur_strengthening',
                'message': '✅ Potencial fortalecimiento del EUR - BCE más hawkish',
                'severity': 'high',
                'impact': 'El Euro podría ganar tracción frente al USD'
            })
        
        # Spread warning
        if yield_spread and yield_spread < 0.5:
            alerts.append({
                'type': 'spread_warning',
                'message': '⚠️ Yield spread en niveles mínimos - Ventaja del USD por carry se reduce',
                'severity': 'medium',
                'impact': 'Posible soporte para EUR/USD'
            })
        
        return alerts
    
    def _generate_professional_explanation(self, score: float, contributions: Dict, 
                                           alerts: List, fed_tone: float, 
                                           ecb_tone: float, yield_spread: Optional[float]) -> str:
        """Genera explicación profesional con lógica corregida"""
        
        # Determinar fuerzas
        usd_factors = []
        eur_factors = []
        
        # Fed (USD)
        if fed_tone > 0.3:
            usd_factors.append("Fed restrictiva (hawkish)")
        elif fed_tone < -0.3:
            eur_factors.append("Fed dovish (debilitaría USD)")
        
        # ECB (EUR)
        if ecb_tone > 0.3:
            eur_factors.append("BCE hawkish")
        elif ecb_tone < -0.3:
            usd_factors.append("BCE dovish (debilitaría EUR)")
        
        # Spread
        if yield_spread:
            if yield_spread > 1.0:
                usd_factors.append(f"spread de yields favorable al USD ({yield_spread:.2f}%)")
            elif yield_spread < 0.5:
                eur_factors.append("spread de yields comprimido (reduce ventaja del USD)")
        
        # Generar explicación según situación
        if score > 2:
            # EUR fuerte
            explanation = f"**El Euro muestra fortaleza significativa frente al Dólar.** "
            if eur_factors:
                explanation += f"Factores que impulsan al EUR: {', '.join(eur_factors)}. "
            if usd_factors:
                explanation += f"Debilidad del USD por: {', '.join(usd_factors)}. "
            if not eur_factors and not usd_factors:
                explanation += "La combinación de factores favorece al Euro. "
        
        elif score < -2:
            # USD fuerte
            explanation = f"**El Dólar muestra fortaleza significativa frente al Euro.** "
            if usd_factors:
                explanation += f"Factores que impulsan al USD: {', '.join(usd_factors)}. "
            if eur_factors:
                explanation += f"Debilidad del EUR por: {', '.join(eur_factors)}. "
            if not usd_factors and not eur_factors:
                explanation += "La combinación de factores favorece al Dólar. "
        
        elif score > 1:
            explanation = f"**Ventaja moderada para el Euro.** "
            if eur_factors:
                explanation += f"Impulsado por: {', '.join(eur_factors)}. "
        elif score < -1:
            explanation = f"**Ventaja moderada para el Dólar.** "
            if usd_factors:
                explanation += f"Impulsado por: {', '.join(usd_factors)}. "
        else:
            explanation = f"**Mercado sin dirección clara.** "
            if score > 0:
                explanation += "Ligera ventaja para el Euro, pero sin suficiente convicción. "
            elif score < 0:
                explanation += "Ligera ventaja para el Dólar, pero sin suficiente convicción. "
            else:
                explanation += "Los factores alcistas y bajistas se compensan exactamente. "
        
        # Añadir contexto de giros si existen
        if alerts and alerts[0]['severity'] == 'high':
            explanation += f"\n\n🚨 **Alerta:** {alerts[0]['message']}"
        elif alerts:
            explanation += f"\n\n⚠️ **Nota:** {alerts[0]['message']}"
        
        return explanation
    
    def get_bias_evolution(self) -> pd.DataFrame:
        """Retorna evolución del bias"""
        if not self.bias_history:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.bias_history)
        return df
    
    def generate_natural_language_explanation(self, bias_result: Dict) -> str:
        """Wrapper para mantener compatibilidad con app.py"""
        components = bias_result.get('components', {})
        return self._generate_professional_explanation(
            bias_result['score'],
            bias_result.get('contributions', {}),
            bias_result.get('alerts', []),
            components.get('fed_tone', 0),
            components.get('ecb_tone', 0),
            components.get('yield_spread', None)
        )