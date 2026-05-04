"""
Utilidades y sistema de cache para la app macroeconómica
"""

import os
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional
import pandas as pd
from pathlib import Path

# Directorio de cache
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Tiempo de expiración por defecto: 1 hora
DEFAULT_EXPIRY_HOURS = 1

def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """Genera una key única para cache basada en parámetros"""
    data = f"{prefix}_{str(args)}_{str(sorted(kwargs.items()))}"
    return hashlib.md5(data.encode()).hexdigest()

def save_to_cache(key: str, data: Any, expiry_hours: int = DEFAULT_EXPIRY_HOURS):
    """Guarda datos en cache con timestamp"""
    cache_file = CACHE_DIR / f"{key}.pkl"
    cache_data = {
        'timestamp': datetime.now(),
        'expiry_hours': expiry_hours,
        'data': data
    }
    with open(cache_file, 'wb') as f:
        pickle.dump(cache_data, f)

def load_from_cache(key: str, max_age_hours: Optional[int] = None) -> Optional[Any]:
    """Carga datos del cache si no han expirado"""
    cache_file = CACHE_DIR / f"{key}.pkl"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'rb') as f:
            cache_data = pickle.load(f)
        
        age = datetime.now() - cache_data['timestamp']
        expiry_hours = max_age_hours or cache_data.get('expiry_hours', DEFAULT_EXPIRY_HOURS)
        
        if age.total_seconds() / 3600 < expiry_hours:
            return cache_data['data']
        else:
            # Cache expirado
            cache_file.unlink()
            return None
    except Exception as e:
        print(f"Error loading cache: {e}")
        return None

def clear_cache():
    """Limpia todo el cache"""
    for cache_file in CACHE_DIR.glob("*.pkl"):
        cache_file.unlink()