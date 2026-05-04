# Macro Currency App - EUR/USD Bias Predictor

Aplicación profesional para generar bias diario de EUR/USD basado en:
- Expectativas de política monetaria (Fed vs BCE) usando NLP con FinBERT
- Bonos (diferencial US2Y - DE2Y)
- Sorpresas macro (CPI, NFP, PMI)
- Riesgo global (tendencia S&P 500)

## Instalación

1. Clonar repositorio
2. Crear entorno virtual: `python -m venv venv`
3. Activar: `venv\Scripts\activate` (Windows) o `source venv/bin/activate` (Mac/Linux)
4. Instalar dependencias: `pip install -r requirements.txt`
5. Crear archivo `.env` a partir de `.env.example` y añadir tus API keys

## Ejecución

```bash
streamlit run app.py