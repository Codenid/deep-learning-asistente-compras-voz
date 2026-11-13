"""TABLERO DE CONTROL -- Laboratorio 4 ML: asistente de compras por voz (ESCI + RAG + agente + TTS clonado).

Edita SOLO este archivo, reinicia el kernel y ejecuta el notebook.
Cada paso guarda un hash de su configuracion: se vuelve a ejecutar solo lo que cambio o falta
(output/resultados/registro.json).
"""
from pathlib import Path

# Raiz del proyecto = carpeta donde esta este archivo (igual en Windows, Linux y Colab)
RAIZ = Path(__file__).resolve().parent

# ===== 1. RUTAS =====
RUTA_INPUT = RAIZ / "input"                         # data descargada + grabaciones (solo lectura)
RUTA_AUDIOS = RUTA_INPUT / "audios"                 # audios de los escenarios por voz (ver GUION_GRABACION.md)
RUTA_VOZ_REF = RUTA_INPUT / "voz" / "referencia.wav"  # voz propia o autorizada para clonar
TEXTO_REF = ("Hola, esta es mi voz de referencia para el asistente de compras. "
             "La grabo en un lugar tranquilo, hablando con calma y a un ritmo natural.")  # lo que se lee en referencia.wav
RUTA_OUTPUT = RAIZ / "output"                       # todo lo generado
RUTA_DATOS = RUTA_OUTPUT / "datos"                  # catalogo y consultas
RUTA_EVAL = RUTA_DATOS / "evaluacion"               # etiquetas ESCI: solo evaluacion, el agente nunca las lee
RUTA_INDICE = RUTA_OUTPUT / "indice"                # embeddings del catalogo
RUTA_TIENDA = RUTA_OUTPUT / "tienda"                # base SQLite (base restaurable + copia de trabajo)
RUTA_ESC = RUTA_OUTPUT / "escenarios"               # registros, audios y estado final por escenario
RUTA_RES = RUTA_OUTPUT / "resultados"               # bitacora, metricas, figuras

# ===== 2. DATOS (ESCI small, locale es) =====
SEMILLA = 2026
N_CONSULTAS_EVAL = 250      # split test (enunciado: >= 200)
N_CONSULTAS_DEV = 150       # split train: desarrollo y ajuste
MIN_CATALOGO = 5000         # enunciado: >= 5000 productos (se completa con distractores si falta)
MAX_CHARS_TEXTO = 600       # recorte de descripcion y caracteristicas al indexar

# ===== 3. TIENDA SIMULADA =====
PRECIO_LOGNORMAL = (3.0, 0.8)   # log-precio ~ N(mu, sigma): mediana ~20 euros
PRECIO_RANGO = (1.99, 399.99)
PROB_AGOTADO = 0.08
STOCK_MAX = 25
CANTIDAD_MAX = 20               # unidades por producto en un pedido

# ===== 4. RECUPERACION (RAG) =====
MODELO_EMB = "intfloat/multilingual-e5-base"
MODELO_RERANK = "BAAI/bge-reranker-v2-m3"
TOP_CANDIDATOS = 50             # top de BM25 y de denso antes de fusionar
TOP_RERANK = 30                 # candidatos que pasan al reranker
GRID = [i / 10 for i in range(11)]   # alpha (denso vs BM25) y beta (reranker vs hibrido), ajustados en dev
K_NDCG = 10
GANANCIAS = {"E": 1.0, "S": 0.1, "C": 0.01, "I": 0.0}   # enunciado

# ===== 5. AGENTE (LLM local) =====
MODELO_LLM = "Qwen/Qwen2.5-7B-Instruct"
LLM_4BIT = True                 # nf4: ~5.5 GB de VRAM
LLM_MAX_TOKENS = 384
MAX_PASOS_AGENTE = 8            # llamadas al LLM por turno
TURNOS_HISTORIAL = 6
K_RESULTADOS = 5                # productos que devuelve buscar_productos

# ===== 6. VOZ =====
MODELO_ASR = "openai/whisper-large-v3-turbo"
MODELO_TTS = "tts_models/multilingual/multi-dataset/xtts_v2"
MODELO_SEMEJANZA = "microsoft/wavlm-base-plus-sv"
SR_ASR = 16000
SEGUNDOS_GRABACION = 7
TTS_EN_ESCENARIOS_TEXTO = False  # True: tambien sintetiza voz en los 14 escenarios de texto (mas lento)
DISPOSITIVO = "auto"             # "auto" usa cuda si hay GPU

# ===== 7. EJECUCION =====
EJECUTAR_EVAL_RECUPERACION = True
EJECUTAR_ESCENARIOS_TEXTO = True
EJECUTAR_ESCENARIOS_VOZ = True   # requiere input/voz/referencia.wav y los audios de input/audios
MODO_INTERACTIVO = False         # True: habilita la demo con microfono (no usar con nbconvert)
FORZAR_REEJECUTAR = False        # True: ignora lo ya ejecutado (luego volver a False)
