"""Rutas y parámetros comunes del Laboratorio 4."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
RUTA_INPUT = ROOT / "input"
if (not (RUTA_INPUT / "shopping_queries_dataset_products.parquet").exists()
        and (ROOT / "data" / "raw" / "shopping_queries_dataset_products.parquet").exists()):
    RUTA_INPUT = ROOT / "data" / "raw"

RUTA_OUTPUT = ROOT / "output"
RUTA_DATOS = RUTA_OUTPUT / "datos"
RUTA_EVAL = RUTA_DATOS / "evaluacion"
RUTA_CACHE = RUTA_OUTPUT / "indice"
RUTA_TIENDA = RUTA_OUTPUT / "tienda"
RUTA_ESCENARIOS = RUTA_OUTPUT / "escenarios"
RUTA_RESULTADOS = RUTA_OUTPUT / "resultados"
RUTA_VOICE_SAMPLES = ROOT / "data" / "voice_samples"
RUTA_VOICE_PROFILES = ROOT / "data" / "voice_profiles"
RUTA_AUDIO_ESCENARIOS = ROOT / "data" / "scenario_audio"

# Perfil de recursos para el equipo local: el LLM usa la GPU; los modelos de
# recuperación y voz usan CPU durante la integración para reservar VRAM.
DISPOSITIVO_LLM = "cuda:0"
DISPOSITIVO_RECUPERACION = "cpu"
DISPOSITIVO_ASR = "cpu"
DISPOSITIVO_TTS = "cpu"

SEMILLA = 2026
N_CONSULTAS_EVAL = 250
N_CONSULTAS_DEV = 150
MIN_CATALOGO = 5000
GANANCIAS = {"E": 1.0, "S": 0.1, "C": 0.01, "I": 0.0}

MODELO_EMB = "intfloat/multilingual-e5-base"
MODELO_RERANK = "BAAI/bge-reranker-v2-m3"
MODELO_LLM = "Qwen/Qwen2.5-7B-Instruct"
MODELO_ASR = "openai/whisper-large-v3-turbo"
MODELO_TTS = "tts_models/multilingual/multi-dataset/xtts_v2"
MODELO_SEMEJANZA = "microsoft/wavlm-base-plus-sv"

TOP_CANDIDATOS = 50
TOP_RERANK = 30
K_RESULTADOS = 5
K_NDCG = 10
MAX_PASOS_AGENTE = 8
TURNOS_HISTORIAL = 6
CANTIDAD_MAX = 20
PRECIO_LOGNORMAL = (3.0, 0.8)
PRECIO_RANGO = (1.99, 399.99)
PROB_AGOTADO = 0.08
STOCK_MAX = 25
GRID = [i / 10 for i in range(11)]


def voces_disponibles():
    """Descubre perfiles de voz en multimedia/ o data/voice_samples/."""
    voces = {}
    for meta_path in sorted((ROOT / "multimedia").glob("multimedia*/meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        voz_id = str(meta.get("nombre", "")).strip()
        referencia = meta_path.parent / "referencia.wav"
        if voz_id and referencia.exists():
            voces[voz_id] = {
                "referencia": referencia,
                "referencia_2": meta_path.parent / "referencia_2.wav",
                "audios": meta_path.parent / "audios",
                "texto_referencia": str(meta.get("texto_referencia", "")).strip(),
                "metadata": meta_path,
            }
    for referencia in sorted(RUTA_VOICE_SAMPLES.glob("*.wav")):
        voz_id = referencia.stem
        voces.setdefault(voz_id, {
            "referencia": referencia,
            "referencia_2": referencia.with_name("referencia_2.wav"),
            "audios": RUTA_AUDIO_ESCENARIOS / voz_id,
            "texto_referencia": "",
            "metadata": None,
        })
    return voces


def rutas_voz(voice_id):
    """Resuelve grabación, perfil y audios de escenario para una identidad."""
    voz = voces_disponibles().get(str(voice_id))
    if voz is None:
        raise FileNotFoundError(f"No existe la voz {voice_id!r}. Disponibles: {sorted(voces_disponibles())}")
    return {**voz, "perfil": RUTA_VOICE_PROFILES / f"{voice_id}.pt"}
