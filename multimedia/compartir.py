"""Compartir el Chat con los compañeros mediante un enlace público de Cloudflare (sin clave).

Qué hace:
- Levanta un segundo servidor SOLO con el chat (puerto PUERTO_CHAT). La configuración y las voces
  siguen disponibles únicamente en http://localhost:5000 (no se publican).
- Abre un túnel rápido de Cloudflare (cloudflared, sin cuenta) hacia ese servidor y devuelve el enlace
  https://....trycloudflare.com. El enlace cambia cada vez que se habilita.
- Al deshabilitar (o al cerrar multimedia.bat) se cierran el túnel y el servidor del chat.

Requiere cloudflared instalado (winget install Cloudflare.cloudflared).
Se usa desde el módulo Configuración: botón "Habilitar enlace público".
"""
import atexit
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, redirect
from werkzeug.serving import make_server

PUERTO_CHAT = 5001          # servidor que ve el túnel: solo el chat
ESPERA_ENLACE_S = 40        # tiempo máximo para que Cloudflare entregue el enlace
# winget instala aquí; la ventana de multimedia.bat puede no tener el PATH actualizado
RUTAS_CLOUDFLARED = [Path(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
                     Path(r"C:\Program Files\cloudflared\cloudflared.exe")]
ENLACE_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

E = {"activo": False, "url": None, "error": None, "servidor": None, "proceso": None}
_CANDADO = threading.Lock()


def _cloudflared():
    encontrado = shutil.which("cloudflared") or next((str(p) for p in RUTAS_CLOUDFLARED if p.exists()), None)
    if encontrado is None:
        raise RuntimeError("no se encontró cloudflared: instálalo con 'winget install Cloudflare.cloudflared'")
    return encontrado


def crear_app_chat(blueprint, leer_config, manejador_error):
    """App que solo expone el chat y la lectura de sus parámetros."""
    app = Flask("chat_publico")
    app.register_blueprint(blueprint)
    app.add_url_rule("/", "inicio", lambda: redirect("/asistente/"))
    app.add_url_rule("/api/config", "config", leer_config, methods=["GET"])
    app.register_error_handler(400, manejador_error)
    app.register_error_handler(404, manejador_error)
    return app


def _leer_enlace(proceso):
    # cloudflared escribe el enlace en su salida de errores; se sigue leyendo para que no se bloquee
    for linea in proceso.stderr:
        if E["url"] is None:
            m = ENLACE_RE.search(linea)
            if m:
                E["url"] = m.group(0)


def habilitar(app_chat):
    with _CANDADO:
        if E["activo"]:
            return estado()
        E.update(url=None, error=None)
        exe = _cloudflared()
        # 1 · servidor del chat en un hilo aparte
        servidor = make_server("127.0.0.1", PUERTO_CHAT, app_chat, threaded=True)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        E["servidor"] = servidor
        # 2 · túnel rápido de Cloudflare hacia el servidor del chat
        proceso = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PUERTO_CHAT}"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                                   encoding="utf-8", errors="replace",
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        E["proceso"] = proceso
        threading.Thread(target=_leer_enlace, args=(proceso,), daemon=True).start()
        limite = time.time() + ESPERA_ENLACE_S
        while E["url"] is None and proceso.poll() is None and time.time() < limite:
            time.sleep(0.3)
        if E["url"] is None:
            motivo = "cloudflared se cerró" if proceso.poll() is not None else f"no respondió en {ESPERA_ENLACE_S} s"
            _detener()
            raise RuntimeError(f"no se obtuvo el enlace de Cloudflare ({motivo}); revisa tu conexión a internet")
        E["activo"] = True
        return estado()


def _detener():
    if E["proceso"] is not None and E["proceso"].poll() is None:
        E["proceso"].terminate()
    if E["servidor"] is not None:
        E["servidor"].shutdown()
    E.update(activo=False, url=None, servidor=None, proceso=None)


def deshabilitar():
    with _CANDADO:
        _detener()
        return estado()


def estado():
    return {"activo": E["activo"], "url": E["url"], "puerto_chat": PUERTO_CHAT}


atexit.register(_detener)   # al cerrar multimedia.bat no queda el túnel abierto
