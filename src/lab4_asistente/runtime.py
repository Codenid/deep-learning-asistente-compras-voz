"""Carga de los componentes necesarios para la integración final."""
import json
import time

import pandas as pd
import torch

from . import config as C
from .agente import Agente
from .escenarios import Sistema
from .modelos import LLMLocal
from .recuperacion import Recuperador
from .tienda import Tienda


def detectar_dispositivo(requerir_cuda=True):
    """Comprueba que CUDA funcione y deja el LLM asignado explícitamente a la GPU."""
    if not torch.cuda.is_available():
        if requerir_cuda:
            raise RuntimeError("No hay CUDA disponible. Activa la GPU y selecciona el kernel .venv-dl-cuda.")
        return "cpu"
    try:
        torch.cuda.init()
        torch.arange(1, device=C.DISPOSITIVO_LLM)
        torch.cuda.synchronize()
        libre, total = torch.cuda.mem_get_info(0)
        if libre < 8 * 1024**3:
            raise RuntimeError(f"VRAM libre insuficiente: {libre / 1024**3:.1f} de {total / 1024**3:.1f} GB. "
                               "Cierra procesos que usen la GPU y vuelve a ejecutar.")
        print(f"GPU lista: {torch.cuda.get_device_name(0)} | "
              f"VRAM libre: {libre / 1024**3:.1f}/{total / 1024**3:.1f} GB")
        return C.DISPOSITIVO_LLM
    except RuntimeError as exc:
        if requerir_cuda:
            raise RuntimeError(f"CUDA no pudo inicializarse en la GPU: {exc}") from exc
        return "cpu"


def cargar_sistema(cargar_llm=True):
    """Carga catálogo, recuperación, tienda y agente; registra por separado tiempos de carga."""
    C.RUTA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    catalogo = pd.read_parquet(C.RUTA_DATOS / "catalogo.parquet")
    consultas = pd.read_parquet(C.RUTA_DATOS / "consultas.parquet")
    qrels = pd.read_parquet(C.RUTA_EVAL / "qrels.parquet")
    dispositivo = detectar_dispositivo(requerir_cuda=cargar_llm)
    cargas = {}

    t0 = time.perf_counter()
    recuperador = Recuperador(catalogo)
    recuperador.cargar_denso(C.MODELO_EMB, C.DISPOSITIVO_RECUPERACION, C.RUTA_CACHE)
    recuperador.cargar_reranker(C.MODELO_RERANK, C.DISPOSITIVO_RECUPERACION)
    cargas["recuperacion"] = time.perf_counter() - t0

    parametros_path = C.RUTA_RESULTADOS / "recuperacion_parametros.json"
    parametros = json.loads(parametros_path.read_text()) if parametros_path.exists() else {"alpha": 0.7, "beta_sistema": 0.8}
    recuperador.alpha = float(parametros.get("alpha", 0.7))
    recuperador.beta = float(parametros.get("beta_sistema", 0.8))

    C.RUTA_TIENDA.mkdir(parents=True, exist_ok=True)
    base = C.RUTA_TIENDA / "tienda_base.sqlite"
    trabajo = C.RUTA_TIENDA / "tienda.sqlite"
    if not base.exists():
        Tienda.crear_base(base, catalogo.product_id, C.SEMILLA, *C.PRECIO_LOGNORMAL,
                          C.PRECIO_RANGO, C.PROB_AGOTADO, C.STOCK_MAX)
    tienda = Tienda(base, trabajo, C.CANTIDAD_MAX)
    tienda.restaurar()

    llm = None
    if cargar_llm:
        t0 = time.perf_counter()
        llm = LLMLocal(C.MODELO_LLM, cuatro_bits=True, dispositivo=C.DISPOSITIVO_LLM)
        cargas["llm"] = time.perf_counter() - t0

    sistema = Sistema(catalogo, recuperador, tienda, llm, C.K_RESULTADOS,
                      C.MAX_PASOS_AGENTE, C.TURNOS_HISTORIAL)
    return {"catalogo": catalogo, "consultas": consultas, "qrels": qrels,
            "recuperador": recuperador, "tienda": tienda, "llm": llm,
            "sistema": sistema, "cargas": cargas, "dispositivo": dispositivo,
            "dispositivos": {"llm": C.DISPOSITIVO_LLM if cargar_llm else None,
                             "recuperacion": C.DISPOSITIVO_RECUPERACION},
            "parametros_recuperacion": parametros}


def cargar_modelos_voz(voice_id, dispositivo=None):
    """Carga ASR y TTS; usa el perfil .pt preparado en el notebook de voz."""
    from .voz import ASR, TTSClonado
    voice_id = str(voice_id)
    rutas = C.rutas_voz(voice_id)
    referencia, perfil = rutas["referencia"], rutas["perfil"]
    if not referencia.exists() or not perfil.exists():
        raise FileNotFoundError(f"Se requieren {referencia} y {perfil}")
    t0 = time.perf_counter()
    asr = ASR(C.MODELO_ASR, -1)
    carga_asr = time.perf_counter() - t0
    t0 = time.perf_counter()
    tts = TTSClonado(C.MODELO_TTS, perfil, referencia, C.DISPOSITIVO_TTS)
    carga_tts = time.perf_counter() - t0
    return asr, tts, {"asr": carga_asr, "tts": carga_tts,
                       "dispositivo_asr": C.DISPOSITIVO_ASR,
                       "dispositivo_tts": C.DISPOSITIVO_TTS}
