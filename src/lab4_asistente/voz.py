# ===== Voz: ASR, TTS clonado, semejanza y metricas =====
"""Voz: ASR (Whisper), TTS con clonacion (XTTS-v2), semejanza de voz (WavLM x-vector) y metricas.

Metricas:
- wer / cer normalizados (minusculas, sin tildes ni puntuacion).
- errores en entidades: cantidades, importes (numeros seguidos de euros) y terminos de producto.
- inteligibilidad del TTS: WER entre el texto sintetizado y su re-transcripcion con el ASR.
- semejanza: coseno entre x-vectors de la voz sintetizada y la referencia.
"""
import os
import re
from collections import Counter

import numpy as np

from .recuperacion import STOP, normalizar



def cargar_audio(ruta, sr=16000):
    import soundfile as sf
    x, s = sf.read(str(ruta), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if s != sr:
        import librosa
        x = librosa.resample(x, orig_sr=s, target_sr=sr)
    return x


def grabar(ruta, segundos=7, sr=16000):
    """Graba del microfono (sounddevice) y guarda WAV. La medicion de latencia empieza al terminar."""
    import sounddevice as sd
    import soundfile as sf
    x = sd.rec(int(segundos * sr), samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    sf.write(str(ruta), x[:, 0], sr)
    return ruta


class ASR:
    def __init__(self, modelo, dispositivo):
        import torch
        from transformers import pipeline
        es_gpu = (isinstance(dispositivo, int) and dispositivo >= 0) or str(dispositivo).startswith("cuda")
        dtype = torch.float16 if es_gpu else torch.float32
        self.p = pipeline("automatic-speech-recognition", model=modelo, torch_dtype=dtype, device=dispositivo)

    def transcribir(self, ruta):
        audio = cargar_audio(ruta, 16000)
        out = self.p({"raw": audio, "sampling_rate": 16000}, chunk_length_s=30,
                     generate_kwargs={"language": "spanish", "task": "transcribe"})
        return out["text"].strip()


class TTSClonado:
    def __init__(self, modelo, perfil_path, referencia_path, dispositivo="cpu"):
        """Carga latentes ya preparados y conserva el WAV original para medir semejanza."""
        import torch
        from TTS.api import TTS
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import XttsAudioConfig
        from TTS.config.shared_configs import BaseDatasetConfig

        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, BaseDatasetConfig])
        # XTTS-v2 oficial guarda objetos de configuración en su checkpoint. El ajuste se limita
        # al instante de carga y se restaura inmediatamente después.
        anterior = os.environ.get("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD")
        os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"
        try:
            self.api = TTS(modelo).to(dispositivo)
        finally:
            if anterior is None:
                os.environ.pop("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", None)
            else:
                os.environ["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = anterior

        self.m = self.api.synthesizer.tts_model
        self.sr = self.api.synthesizer.output_sample_rate
        perfil = torch.load(perfil_path, map_location=dispositivo, weights_only=True)
        self.lat = perfil["gpt_cond_latent"].to(dispositivo)
        self.spk = perfil["speaker_embedding"].to(dispositivo)
        # Se guarda la frase solo si existe en meta.json; nunca se exige un .txt.
        self.reference_text = str(perfil.get("reference_text", "")).strip()
        self.ref = set(palabras(self.reference_text))
        self.referencia_path = str(referencia_path)

    def sintetizar(self, texto, ruta, semilla=0):
        import soundfile as sf
        import torch
        texto_tokens = set(palabras(texto))
        if self.ref and texto_tokens:
            solapamiento = len(texto_tokens & self.ref) / len(texto_tokens | self.ref)
            if solapamiento > 0.8:
                raise ValueError("El texto sintetizado debe ser distinto al texto de referencia")
        torch.manual_seed(semilla)
        wav = self.m.inference(texto, "es", self.lat, self.spk, temperature=0.7, enable_text_splitting=True)["wav"]
        sf.write(str(ruta), np.asarray(wav, dtype=np.float32), self.sr)
        return ruta


class Semejanza:
    def __init__(self, modelo, dispositivo="cpu"):
        from transformers import AutoFeatureExtractor, WavLMForXVector
        self.fe = AutoFeatureExtractor.from_pretrained(modelo)
        self.m = WavLMForXVector.from_pretrained(modelo).to(dispositivo).eval()
        self.disp = dispositivo

    def embedding(self, ruta):
        import torch
        x = cargar_audio(ruta, 16000)
        enc = self.fe(x, sampling_rate=16000, return_tensors="pt").to(self.disp)
        with torch.inference_mode():
            e = self.m(**enc).embeddings[0]
        return torch.nn.functional.normalize(e, dim=-1).cpu().numpy()

    def coseno(self, a, b):
        return float(np.dot(self.embedding(a), self.embedding(b)))


# --- metricas de texto ---
def palabras(t):
    return re.findall(r"[a-z0-9]+(?:[.,][0-9]+)?|€", normalizar(t))


def wer(ref, hip):
    import jiwer
    r, h = " ".join(palabras(ref)), " ".join(palabras(hip))
    return float(jiwer.wer(r, h)) if r else float(bool(h))


def cer(ref, hip):
    import jiwer
    r, h = " ".join(palabras(ref)), " ".join(palabras(hip))
    return float(jiwer.cer(r, h)) if r else float(bool(h))


UNI = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
       "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
       "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
       "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
       "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29}
DEC = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90}
CEN = {"cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200, "trescientos": 300, "trescientas": 300,
       "cuatrocientos": 400, "cuatrocientas": 400, "quinientos": 500, "quinientas": 500, "seiscientos": 600,
       "seiscientas": 600, "setecientos": 700, "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
       "novecientos": 900, "novecientas": 900}
MONEDA = {"euro", "euros", "€", "eur"}


def _es_num(w):
    return w in UNI or w in DEC or w in CEN or w == "mil" or re.fullmatch(r"\d+(?:[.,]\d+)?", w) is not None


def _leer_numero(ws, i):
    """Lee un numero (palabras o digitos) desde ws[i]. Devuelve (valor, siguiente_indice)."""
    w = ws[i]
    if re.fullmatch(r"\d+(?:[.,]\d+)?", w):
        return float(w.replace(",", ".")), i + 1
    total, actual = 0, 0
    while i < len(ws):
        w = ws[i]
        if w in CEN:
            actual += CEN[w]
        elif w in DEC:
            actual += DEC[w]
        elif w in UNI:
            actual += UNI[w]
        elif w == "mil":
            total += max(actual, 1) * 1000
            actual = 0
        elif w == "y" and i + 1 < len(ws) and ws[i + 1] in UNI and actual % 10 == 0 and actual >= 30:
            pass
        else:
            break
        i += 1
    return float(total + actual), i


def entidades(texto):
    """Cantidades e importes (Counter de valores) y terminos de producto (set) de una frase."""
    ws = palabras(texto)
    cant, imp, i = Counter(), Counter(), 0
    while i < len(ws):
        if not _es_num(ws[i]):
            i += 1
            continue
        v, j = _leer_numero(ws, i)
        if j < len(ws) - 1 and ws[j] == "con" and _es_num(ws[j + 1]):        # "doce con cincuenta"
            d, j = _leer_numero(ws, j + 1)
            v += d / 100 if d < 100 else 0
        es_imp = (j < len(ws) and ws[j] in MONEDA) or (i > 0 and ws[i - 1] == "€")
        (imp if es_imp else cant)[round(v, 2)] += 1
        i = j
    conversa = {"quiero", "comprar", "compra", "agrega", "agregar", "anade", "anadir", "pon", "carrito", "confirmo",
                "confirma", "confirmar", "si", "vale", "presupuesto", "maximo", "total", "cotizacion", "pedido",
                "favor", "opcion", "primera", "segunda", "tercera", "mejor", "entonces", "dame", "prepara",
                "preparame", "necesito", "busco", "unidades", "unidad", "mas", "menos", "barato", "barata",
                "euros", "euro", "con", "hola", "gracias", "otra", "otro", "vez", "esa", "ese", "eso", "por",
                "son", "sean", "dije", "perdon", "cambia", "cambiala", "quita", "tambien", "solo", "cuesta"}
    prod = {w for w in ws if len(w) >= 3 and w not in STOP and w not in conversa and not _es_num(w)}
    return {"cantidades": cant, "importes": imp, "productos": prod}


def errores_entidades(ref, hip):
    a, b = entidades(ref), entidades(hip)
    dif = lambda x, y: max(sum((x - y).values()), sum((y - x).values()))   # sustitucion = 1 error
    return {"err_cantidades": dif(a["cantidades"], b["cantidades"]), "err_importes": dif(a["importes"], b["importes"]),
            "err_productos": len(a["productos"] - b["productos"]),
            "n_cantidades": sum(a["cantidades"].values()), "n_importes": sum(a["importes"].values()),
            "n_productos": len(a["productos"])}
