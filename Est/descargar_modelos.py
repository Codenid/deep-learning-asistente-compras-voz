"""Descarga (o verifica en cache) todos los modelos del laboratorio. Opcional: el notebook los descarga al usarlos.
Uso: python descargar_modelos.py"""
import os

import configuracion as C

os.environ.setdefault("COQUI_TOS_AGREED", "1")
from huggingface_hub import snapshot_download  # noqa: E402

for m in (C.MODELO_LLM, C.MODELO_ASR, C.MODELO_EMB, C.MODELO_RERANK, C.MODELO_SEMEJANZA):
    print("descargando", m)
    snapshot_download(m)
from TTS.utils.manage import ModelManager  # noqa: E402
ModelManager().download_model(C.MODELO_TTS)
print("Modelos listos en cache")
