# 📊 Macro Analysis EUR/USD

**Aplicación profesional de análisis macroeconómico para el par EUR/USD**

![Python Version](https://img.shields.io/badge/python-3.10-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.29.0-red)
![License](https://img.shields.io/badge/license-MIT-green)

---

## ⚠️ IMPORTANTE - LEE ESTO ANTES DE USAR LA APP

### 🚨 Aviso Legal y Advertencia

**Esta aplicación es una HERRAMIENTA EDUCATIVA y de ANÁLISIS, NO es un sistema de trading automatizado ni una recomendación financiera.**

La app se encuentra actualmente en **FASE DE DESARROLLO** y los resultados que genera:

- ❌ **NO** deben ser utilizados como única fuente para tomar decisiones de inversión
- ❌ **NO** garantizan rentabilidad en ningún mercado o plazo
- ❌ **NO** constituyen asesoramiento financiero personalizado
- ❌ **NO** están libres de errores, sesgos o limitaciones técnicas

### 📋 Lo que DEBES saber antes de usar:

1. **El análisis macro es una guía, no una predicción** - Los mercados financieros son impredecibles y están influenciados por múltiples factores no capturados por el modelo.

2. **La app está en desarrollo continuo** - Puede haber errores, cambios en la lógica de cálculo y ajustes en los pesos de los indicadores.

3. **Resultados con retraso** - Si las fuentes de datos en tiempo real (Yahoo Finance) no están disponibles, la app usa datos de respaldo con retraso de 1 día.

4. **Sin garantías** - El desarrollador no asume responsabilidad por pérdidas financieras derivadas del uso de esta herramienta.

### ✅ Uso recomendado:

- Como **complemento** a tu propio análisis técnico y fundamental
- Para **formarte y entender** cómo se relacionan los factores macroeconómicos
- Como **punto de partida** para tu investigación, nunca como conclusión final

> 💡 **Regla de oro:** Si la app te dice que compres o vendas, NO lo hagas sin antes contrastarlo con otras fuentes, análisis propio y, preferiblemente, asesoramiento profesional.

---

## 🎯 ¿Qué hace esta aplicación?

La app **analiza si el EUR/USD va a subir o bajar** basándose en factores macroeconómicos reales:

- 🗣️ **Política monetaria** - Sentimiento de la Fed y el BCE (hawkish/dovish)
- 📈 **Bonos** - Diferencia de rendimientos entre USA y Alemania (yield spread)
- 📰 **Sentimiento de mercado** - Noticias clasificadas con NLP (FinBERT)
- 🌍 **Apetito de riesgo** - Comportamiento del S&P 500
- 📊 **Datos macro** - Indicadores económicos (GDP, inflación)

### Output principal:

- 🟢 **BULLISH** → Se espera que el EUR se fortalezca frente al USD
- 🔴 **BEARISH** → Se espera que el USD se fortalezca frente al EUR  
- ⚪ **NEUTRAL** → Sin dirección clara

Además incluye:
- Explicación automática de los drivers
- Zonas técnicas de soporte/resistencia
- Alertas de cambios en política monetaria
- Calendario de eventos económicos

---

## 🚀 Demo en vivo

> 🔗 **URL de la app desplegada:** [https://soletion-biasapp-app-gqykhg.streamlit.app](https://soletion-biasapp-app-gqykhg.streamlit.app)

*Nota: La disponibilidad puede variar según el plan gratuito de Streamlit Cloud.*

---

## 🛠️ Instalación local

### Requisitos previos

- Python 3.10 o superior
- pip (gestor de paquetes de Python)
- (Opcional) API keys para funcionalidades completas

### Paso 1: Clonar el repositorio

```
git clone https://github.com/TU_USUARIO/biasapp.git
cd biasapp
```

### Paso 2: Crear entorno virtual
# Windows
```
python -m venv venv
venv\Scripts\activate
```
# macOS / Linux
```
python3 -m venv venv
source venv/bin/activate
```

### Paso 3: Instalar dependencias
```
pip install -r requirements.txt
```

### Paso 4: Configurar API keys (opcional)
Crea un archivo .env en la raíz del proyecto:
```
# Obtén tu API key de FRED: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=tu_api_key_aqui

# Obtén tu API key de NewsAPI: https://newsapi.org/register
NEWSAPI_KEY=tu_api_key_aqui
```

### Paso 5: Ejecutar la aplicación
```
streamlit run app.py
```

## 📁 Estructura del proyecto
```
biasapp/
├── app.py                          # Main Streamlit app
├── requirements.txt                # Dependencias Python
├── runtime.txt                     # Versión de Python para Cloud
├── .python-version                 # Versión de Python (local)
├── packages.txt                    # Dependencias de sistema
├── modules/
│   ├── __init__.py
│   ├── data_ingestion.py          # Obtención de datos (Yahoo Finance + fallback)
│   ├── data_processing.py         # Cálculo del bias macro
│   ├── news_analyzer.py           # NLP con FinBERT (fallback básico)
│   ├── technical_analysis.py      # Soportes, resistencias, pivotes
│   └── utils.py                   # Sistema de caché
├── data/
│   └── cache/                      # Archivos de caché (ignorados por git)
└── .env.example                    # Template para API keys
```

## 🔧 Dependencias principales

Este proyecto utiliza un conjunto cuidadosamente seleccionado de librerías para garantizar un equilibrio entre funcionalidad, rendimiento y compatibilidad en entornos cloud.

| Paquete | Versión | Uso en la app |
|---------|---------|----------------|
| `streamlit` | 1.29.0 | Framework principal para la interfaz web y el dashboard interactivo |
| `pandas` | 2.0.3 | Manipulación y análisis de datos (series temporales, DataFrames) |
| `numpy` | 1.24.3 | Cálculos numéricos y operaciones vectoriales |
| `yfinance` | 0.2.33 | Descarga de datos históricos y en tiempo real de Yahoo Finance |
| `plotly` | 5.17.0 | Generación de gráficos interactivos (velas, líneas, áreas) |
| `fredapi` | 0.5.1 | Conexión con la API de la Reserva Federal (FRED) para bonos |
| `newsapi-python` | 0.2.7 | Obtención de noticias financieras en tiempo real |
| `transformers` | 4.35.0 | Modelos NLP (FinBERT para análisis de sentimiento) |
| `beautifulsoup4` | 4.12.2 | Web scraping del calendario económico (ForexFactory) |
| `requests` | 2.31.0 | Peticiones HTTP a APIs alternativas (Frankfurter, exchanges) |
| `python-dotenv` | 1.0.0 | Gestión segura de variables de entorno y API keys |

## 📊 Fuentes de datos

| Tipo | Fuente principal | Fallback | Estado |
|------|------------------|----------|--------|
| **Precio EUR/USD** | Yahoo Finance (tiempo real) | Frankfurter API (EOD con retraso) | ✅ Activo |
| **Bonos (yields)** | FRED API (DGS2) | N/A (requiere API key) | ⚠️ Opcional |
| **Noticias** | NewsAPI | Análisis básico por palabras clave | ⚠️ Opcional |
| **Eventos económicos** | ForexFactory (web scraping) | N/A | ✅ Activo |
| **S&P 500 (riesgo)** | Yahoo Finance | N/A | ✅ Activo |

### Detalle de cada fuente:

#### 📈 Yahoo Finance (principal)
- **Qué datos:** Precio EUR/USD en tiempo real, velas históricas (Open, High, Low, Close)
- **Frecuencia:** Actualización continua durante mercado abierto
- **Ventaja:** Datos reales sin retraso, OHLC completos
- **Limitación:** Puede bloquear requests frecuentes (error 429)

#### 📉 Frankfurter API (fallback)
- **Qué datos:** Tipos de cambio USD/EUR del Banco Central Europeo
- **Frecuencia:** Actualización diaria (EOD - End of Day)
- **Uso:** Solo cuando Yahoo Finance no está disponible
- **⚠️ Advertencia:** Los datos tienen aproximadamente 1 día de retraso

#### 🏦 FRED API (bonos)
- **Qué datos:** Yield del bono US 2 años (DGS2) y Germany 2 años (IRLTLT01DEM156N)
- **Requisito:** API key gratuita desde [FRED](https://fred.stlouisfed.org/docs/api/api_key.html)
- **Sin API key:** El componente de yield spread se omite (bias menos preciso)

#### 📰 NewsAPI (noticias)
- **Qué datos:** Noticias relacionadas con Fed, FOMC, Powell, ECB, Lagarde
- **Requisito:** API key gratuita desde [NewsAPI](https://newsapi.org/register)
- **Sin API key:** No hay noticias; el análisis de sentimiento se basa solo en palabras clave básicas

#### 📅 ForexFactory (eventos)
- **Qué datos:** Calendario económico con eventos de USD y EUR
- **Método:** Web scraping de la página pública
- **Sin API key:** Totalmente gratuito y sin necesidad de registro

---

## ⚙️ Estado del desarrollo

### ✅ Implementado (funcional)
- [x] Bias macro basado en política monetaria, bonos y sentimiento
- [x] Análisis técnico separado (soportes, resistencias, pivotes)
- [x] Obtención de datos en tiempo real (Yahoo Finance)
- [x] Fallback a datos EOD cuando Yahoo no está disponible
- [x] Explicación automática en lenguaje natural
- [x] Alertas de giros en política monetaria
- [x] Calendario de eventos económicos
- [x] Despliegue en Streamlit Cloud
- [x] Sistema de caché para reducir requests

### 🚧 En desarrollo (próximas versiones)
- [ ] Mejora en la detección de giros macro (deltas más sensibles)
- [ ] Ajuste de pesos en la fórmula del score basado en backtesting
- [ ] Integración de más indicadores macro (PMI, empleo, CPI)
- [ ] Backtesting histórico del modelo (últimos 5 años)
- [ ] Soporte para más pares de divisas (GBP/USD, USD/JPY)
- [ ] Modo oscuro/claro en la interfaz
- [ ] Exportación de análisis a PDF

### 🐛 Problemas conocidos
| Problema | Estado | Solución temporal |
|----------|--------|-------------------|
| Yahoo Finance puede bloquear requests frecuentes (error 429) | ⚠️ Ocasional | Esperar 5-10 minutos o usar VPN |
| FinBERT (torch) no se instala en Streamlit Cloud | ❌ Persistente | Fallback automático a análisis básico |
| Los datos de bonos requieren API key de FRED | ⚠️ Opcional | El bias funciona sin ellos (menos preciso) |
| Frankfurter API tiene 1 día de retraso | ✅ Por diseño | Mostrar advertencia cuando se usa fallback |

---

## 🤝 Cómo contribuir

Si encuentras errores o tienes sugerencias para mejorar la app:

1. **Abre un Issue** en GitHub describiendo el problema o mejora propuesta
2. **Incluye logs o capturas de pantalla** si es un error técnico
3. **Si quieres contribuir con código**, abre un Pull Request con la descripción de los cambios

### Áreas donde se necesita ayuda:
- 🔧 Backtesting del modelo macro (validación histórica)
- 📊 Mejora de la detección de soportes/resistencias
- 🌐 Integración con más fuentes de datos macro
- 🧪 Tests unitarios y de integración

---

## 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Puedes usarlo, modificarlo y distribuirlo libremente, siempre manteniendo el aviso de responsabilidad y atribución al autor original.

---

## 👨‍💻 Autor

Desarrollado como herramienta educativa de análisis macroeconómico para traders y analistas financieros.

---

## ⚠️ Última advertencia (en serio, léela de nuevo)

> **Esta aplicación NO es un bróker, NO es un asesor financiero, NO es un sistema de trading automatizado.**
>
> **Los mercados financieros conllevan riesgos significativos. Puedes perder parte o la totalidad de tu capital.**
>
> **Siempre consulta con un asesor financiero profesional antes de tomar decisiones de inversión.**
>
> **La app está en desarrollo continuo - los resultados pueden cambiar entre versiones sin previo aviso.**

---

## 📞 Contacto y soporte

- **Reportar errores:** [GitHub Issues](https://github.com/soleetionbiasapp/issues)
- **Demo en vivo:** [https://soletion-biasapp-app-gqykhg.streamlit.app](https://soletion-biasapp-app-gqykhg.streamlit.app)
- **Consultas generales:** Abre un Issue con etiqueta "question"

---

*Última actualización: Mayo 2026*

