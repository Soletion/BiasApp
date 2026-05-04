"""
NLP con FinBERT para análisis de sentimiento de noticias
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple

class FinBERTAnalyzer:
    def __init__(self):
        """Inicializa el modelo FinBERT local"""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
            self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
            self.model.eval()
            self.available = True
        except Exception as e:
            print(f"Error cargando FinBERT: {e}")
            self.available = False
    
    def classify_news(self, news_list: List[Dict]) -> Tuple[float, float]:
        """
        Clasifica noticias relacionadas con FED y ECB
        Returns: (fed_score, ecb_score) donde:
            >0.5: hawkish
            < -0.5: dovish
        """
        if not self.available or not news_list:
            return 0.0, 0.0
        
        fed_texts = []
        ecb_texts = []
        
        for news in news_list:
            text = f"{news['title']}. {news['description']}"
            
            # Filtrar por relevancia
            if any(word in text.lower() for word in ['fed', 'federal reserve', 'powell', 'fomc']):
                fed_texts.append(text)
            if any(word in text.lower() for word in ['ecb', 'european central bank', 'lagarde']):
                ecb_texts.append(text)
        
        fed_score = self._calculate_tone_score(fed_texts)
        ecb_score = self._calculate_tone_score(ecb_texts)
        
        return fed_score, ecb_score
    
    def _calculate_tone_score(self, texts: List[str]) -> float:
        """Calcula el tone score promedio (hawkish = positivo, dovish = negativo)"""
        if not texts:
            return 0.0
        
        scores = []
        
        for text in texts[:10]:  # Limitar a 10 noticias por rendimiento
            try:
                inputs = self.tokenizer(text, return_tensors="pt", 
                                       truncation=True, max_length=512, 
                                       padding=True)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
                
                # FinBERT classes: 0=negative (dovish), 1=neutral, 2=positive (hawkish)
                # Mapear a score entre -1 (dovish) y +1 (hawkish)
                prob_negative = probabilities[0][0].item()
                prob_positive = probabilities[0][2].item()
                
                score = prob_positive - prob_negative  # Range: -1 to 1
                scores.append(score)
                
            except Exception as e:
                print(f"Error clasificando texto: {e}")
                continue
        
        return np.mean(scores) if scores else 0.0
    
    def get_sentiment_label(self, score: float) -> str:
        """Convierte score numérico a etiqueta"""
        if score > 0.3:
            return "Hawkish (USD fuerte)"
        elif score < -0.3:
            return "Dovish (USD débil)"
        else:
            return "Neutral"