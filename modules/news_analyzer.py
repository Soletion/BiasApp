"""
NLP con FinBERT para análisis de sentimiento de noticias
OPTIMIZADO para Streamlit Cloud - Con cache persistente y manejo de memoria
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import gc
import streamlit as st

class FinBERTAnalyzer:
    def __init__(self):
        """Inicializa el analizador y carga el modelo con cache de Streamlit"""
        self.model, self.tokenizer, self.device = self._load_model_cached()
        self.available = self.model is not None
    
    @staticmethod
    @st.cache_resource
    def _load_model_cached():
        """
        Carga el modelo UNA SOLA VEZ y lo reutiliza en todas las sesiones.
        CRÍTICO para evitar el error "exceeded fair-use limits" en Streamlit Cloud.
        """
        try:
            print("🔄 Cargando modelo FinBERT (esto ocurre solo una vez)...")
            
            tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            
            model.to(device)
            model.eval()
            
            print(f"✅ FinBERT cargado correctamente en {device}")
            return model, tokenizer, device
            
        except Exception as e:
            print(f"❌ Error cargando FinBERT: {e}")
            return None, None, None
    
    def classify_news(self, news_list: List[Dict]) -> Tuple[float, float]:
        """
        Clasifica noticias relacionadas con FED y ECB
        Returns: (fed_score, ecb_score) donde:
            >0.3: hawkish
            < -0.3: dovish
        """
        if not self.available or not news_list:
            return 0.0, 0.0
        
        # Limitar noticias para reducir uso de memoria
        news_list = news_list[:15]
        
        fed_texts = []
        ecb_texts = []
        
        for news in news_list:
            title = news.get('title', '')
            description = news.get('description', '')
            text = f"{title}. {description}"
            
            # Filtrar por relevancia (solo noticias relevantes)
            text_lower = text.lower()
            if any(word in text_lower for word in ['fed', 'federal reserve', 'powell', 'fomc']):
                fed_texts.append(text)
            if any(word in text_lower for word in ['ecb', 'european central bank', 'lagarde']):
                ecb_texts.append(text)
        
        # Calcular scores (limitar a 5 noticias por categoría para rendimiento)
        fed_score = self._calculate_tone_score(fed_texts[:5])
        ecb_score = self._calculate_tone_score(ecb_texts[:5])
        
        # Liberar memoria después del procesamiento
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return fed_score, ecb_score
    
    def _calculate_tone_score(self, texts: List[str]) -> float:
        """Calcula el tone score promedio (hawkish = positivo, dovish = negativo)"""
        if not texts:
            return 0.0
        
        scores = []
        
        for text in texts[:5]:  # Máximo 5 noticias por categoría
            if not text or len(text.strip()) < 10:
                continue
                
            try:
                # Truncar textos muy largos
                if len(text) > 1000:
                    text = text[:1000]
                
                inputs = self.tokenizer(
                    text, 
                    return_tensors="pt", 
                    truncation=True, 
                    max_length=256,  # Reducido de 512 para mejor rendimiento
                    padding=True
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                
                # FinBERT classes: 0=negative (dovish), 1=neutral, 2=positive (hawkish)
                prob_negative = probabilities[0][0].item()
                prob_positive = probabilities[0][2].item()
                
                score = prob_positive - prob_negative  # Range: -1 to 1
                scores.append(score)
                
            except Exception as e:
                print(f"Error clasificando texto: {e}")
                continue
        
        # Liberar tensores de GPU si existen
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return np.mean(scores) if scores else 0.0
    
    def get_sentiment_label(self, score: float) -> str:
        """Convierte score numérico a etiqueta"""
        if score > 0.3:
            return "🔴 Hawkish (USD fuerte)"
        elif score < -0.3:
            return "🟢 Dovish (USD débil)"
        else:
            return "⚪ Neutral"
    
    def get_sentiment_impact(self, score: float, is_fed: bool = True) -> str:
        """Devuelve el impacto en EUR/USD según el sentimiento"""
        if is_fed:
            if score > 0.3:
                return "Fed hawkish → USD fuerte → BEARISH para EUR/USD"
            elif score < -0.3:
                return "Fed dovish → USD débil → BULLISH para EUR/USD"
            else:
                return "Fed neutral → sin impacto direccional claro"
        else:
            if score > 0.3:
                return "ECB hawkish → EUR fuerte → BULLISH para EUR/USD"
            elif score < -0.3:
                return "ECB dovish → EUR débil → BEARISH para EUR/USD"
            else:
                return "ECB neutral → sin impacto direccional claro"