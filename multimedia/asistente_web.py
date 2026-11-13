"""Módulo Asistente del aplicativo multimedia.bat: conversar por voz con el asistente de compras.

Qué hace:
- Carga el MISMO código del notebook (celdas de definiciones, igual que tests/verificar_regresiones.py):
  agente, herramientas, tienda, recuperación, ASR y TTS son exactamente los del laboratorio.
- Permite elegir con qué voz clonada responde (multimedia001, multimedia002, ...).
- Devuelve transcripción, respuesta (texto y audio), operaciones, productos, carrito, pedidos y tiempos por etapa.

Parámetros: los del tablero de control del notebook (celda "TABLERO DE CONTROL") y
output/resultados/recuperacion_parametros.json. Requiere haber ejecutado el notebook completo una vez.
Usa su propia copia de la tienda (output/tienda/tienda_aplicativo.sqlite): no toca la del notebook.
Lo generado queda en output/escenarios/aplicativo_web/ (audios y registro.jsonl).

Uso: doble clic en multimedia.bat; módulo Chat en http://localhost:5000/asistente (Configuración en http://localhost:5000).
En el Chat: «Preguntar» graba y envía solo tras la pausa configurada; el texto se envía con «Enviar».
"""
import json
import os
import re
import sys
import time
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from flask import Blueprint, abort, jsonify, request, send_from_directory

MULTI = Path(__file__).resolve().parent   # carpeta multimedia/
RAIZ = MULTI.parent                        # raíz del proyecto
NOTEBOOK = RAIZ / "Laboratorio4_Asistente.ipynb"
ACTIVA = MULTI / "ACTIVA.txt"
SALIDA = RAIZ / "output" / "escenarios" / "aplicativo_web"

# Celdas del notebook que solo definen el sistema (se ubican por su encabezado, no por número)
ENCABEZADOS = ["# ===== TABLERO DE CONTROL", "# ===== Bitacora", "# ===== Tienda simulada",
               "# ===== Recuperacion", "# ===== LLM local", "# ===== Voz:", "# ===== Herramientas",
               "# ===== Agente", "# ===== 20 escenarios"]

asistente = Blueprint("asistente", __name__, url_prefix="/asistente")
MAX_SESIONES = 30   # conversaciones simultáneas (cada navegador = una sesión con su carrito y su tienda)

# 1 · un solo hilo para todo el trabajo del asistente: SQLite no admite cambiar de hilo y la GPU se usa en serie
_HILO = ThreadPoolExecutor(max_workers=1)
S = {"cargado": False, "cargando": False, "error": None, "carga": [], "latentes": {}, "turno": 0, "sesiones": {}}


def en_hilo(fn, *args):
    return _HILO.submit(fn, *args).result()


def voces():
    activa = ACTIVA.read_text(encoding="utf-8").strip() if ACTIVA.exists() else ""
    filas = []
    for d in sorted(MULTI.glob("multimedia[0-9][0-9][0-9]")):
        meta = d / "meta.json"
        nombre = json.loads(meta.read_text(encoding="utf-8")).get("nombre", "") if meta.exists() else ""
        filas.append({"id": d.name, "nombre": nombre, "activa": d.name == activa,
                      "lista": (d / "referencia.wav").exists()})
    return filas


# 2 · carga del código del notebook y de los modelos (una sola vez)
def _codigo_notebook():
    if not NOTEBOOK.exists():
        raise RuntimeError(f"no existe el notebook {NOTEBOOK}")
    celdas = ["".join(c["source"]) for c in json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
              if c["cell_type"] == "code"]
    m = types.ModuleType("lab4_notebook")
    sys.modules[m.__name__] = m              # dataclasses necesitan encontrar el módulo
    m.C, m.np, m.pd, m.json, m.time, m.display = m, np, pd, json, time, print
    os.chdir(RAIZ)                           # el tablero usa Path.cwd() como raíz del proyecto
    for enc in ENCABEZADOS:
        fuente = [c for c in celdas if c.startswith(enc)]
        if len(fuente) != 1:
            raise RuntimeError(f"el notebook debe tener exactamente una celda que empiece con '{enc}'")
        exec(compile(fuente[0], enc, "exec"), m.__dict__)
        if enc == ENCABEZADOS[0]:
            import torch
            m.DISP = ("cuda" if torch.cuda.is_available() else "cpu") if m.DISPOSITIVO == "auto" else m.DISPOSITIVO
    return m


def _cronometrar(nombre, fn):
    t0 = time.perf_counter()
    obj = fn()
    S["carga"].append({"modelo": nombre, "carga_s": round(time.perf_counter() - t0, 1)})
    return obj


def _cargar():
    m = _codigo_notebook()
    base = m.RUTA_TIENDA / "tienda_base.sqlite"
    necesarios = [m.RUTA_DATOS / "catalogo.parquet", base, m.RUTA_RES / "recuperacion_parametros.json"]
    faltan = [str(p) for p in necesarios if not p.exists()]
    if faltan:
        raise RuntimeError("ejecuta primero el notebook completo; faltan: " + ", ".join(faltan))
    voz = next((v for v in voces() if v["activa"] and v["lista"]), None) or next((v for v in voces() if v["lista"]), None)
    if voz is None:
        raise RuntimeError("no hay ninguna voz con referencia.wav: grábala en la pantalla de voces")

    cat = pd.read_parquet(m.RUTA_DATOS / "catalogo.parquet")
    rec = _cronometrar("BM25", lambda: m.Recuperador(cat, m.MAX_CHARS_TEXTO))
    _cronometrar(m.MODELO_EMB, lambda: rec.cargar_denso(m.MODELO_EMB, m.DISP, m.RUTA_INDICE))
    _cronometrar(m.MODELO_RERANK, lambda: rec.cargar_reranker(m.MODELO_RERANK, m.DISP))
    param = json.loads((m.RUTA_RES / "recuperacion_parametros.json").read_text(encoding="utf-8"))
    rec.alpha, rec.beta = param["alpha"], param["beta_sistema"]       # misma configuración que usa el agente
    llm = _cronometrar(m.MODELO_LLM, lambda: m.LLMLocal(m.MODELO_LLM, m.LLM_4BIT, m.LLM_MAX_TOKENS))
    S["asr"] = _cronometrar(m.MODELO_ASR, lambda: m.ASR(m.MODELO_ASR, m.DISP))
    ref = MULTI / voz["id"] / "referencia.wav"
    S["tts"] = _cronometrar(m.MODELO_TTS, lambda: m.TTSClonado(m.MODELO_TTS, ref, m.TEXTO_REF, m.DISP))
    S["latentes"][voz["id"]] = (S["tts"].lat, S["tts"].spk)
    S.update(m=m, cat=cat, rec=rec, llm=llm, base=base)
    (m.RUTA_TIENDA / "aplicativo").mkdir(parents=True, exist_ok=True)
    SALIDA.mkdir(parents=True, exist_ok=True)


def _sistema(sid):
    # 2b · cada sesión tiene su propia copia de la tienda; catálogo, índice y modelos se comparten
    if sid not in S["sesiones"]:
        if len(S["sesiones"]) >= MAX_SESIONES:
            raise RuntimeError(f"se alcanzó el máximo de {MAX_SESIONES} conversaciones simultáneas")
        m = S["m"]
        tienda = m.Tienda(S["base"], m.RUTA_TIENDA / "aplicativo" / f"tienda_{sid}.sqlite", m.CANTIDAD_MAX)
        S["sesiones"][sid] = m.Sistema(S["cat"], S["rec"], tienda, S["llm"], m.K_RESULTADOS, m.MAX_PASOS_AGENTE,
                                       m.TURNOS_HISTORIAL)
    return S["sesiones"][sid]


def _sesion():
    sid = request.headers.get("X-Sesion", "")
    if not re.fullmatch(r"[0-9a-f]{16}", sid):
        abort(400, "sesión inválida: recarga la página")
    return sid


def _fijar_voz(sid):
    # 3 · cambiar de voz solo recalcula los latentes de su referencia; el modelo XTTS se carga una vez
    if not re.fullmatch(r"multimedia\d{3}", sid or ""):
        raise ValueError("id de voz inválido")
    ref = MULTI / sid / "referencia.wav"
    if not ref.exists():
        raise ValueError(f"la voz {sid} no tiene referencia.wav")
    if sid not in S["latentes"]:
        S["latentes"][sid] = S["tts"].m.get_conditioning_latents(audio_path=[str(ref)])
    S["tts"].lat, S["tts"].spk = S["latentes"][sid]


def _transcribir(ruta):
    t0 = time.perf_counter()
    texto = S["asr"].transcribir(ruta)
    return {"texto": texto, "t_asr": round(time.perf_counter() - t0, 2)}


def _turno(sid, texto, voz, con_voz, t_asr, transcripcion):
    sis = _sistema(sid)
    S["turno"] += 1
    n = S["turno"]
    r = sis.agente.turno(texto)
    tiempos = {"asr": t_asr, "recuperacion": r["t_recuperacion"], "llm": r["t_llm"],
               "herramientas": r["t_herramientas"], "tts": 0.0}
    audio = None
    if con_voz:
        _fijar_voz(voz)
        audio = f"respuesta_{sid}_{n:05d}_{voz}.wav"   # el id de sesión hace que el nombre no se pueda adivinar
        t0 = time.perf_counter()
        S["tts"].sintetizar(r["respuesta"], SALIDA / audio, semilla=n)
        tiempos["tts"] = time.perf_counter() - t0
    tiempos = {k: round(v, 2) for k, v in tiempos.items()}
    tiempos["total"] = round(sum(tiempos.values()), 2)

    e = sis.h.estado
    out = {"turno": n, "sesion": sid, "texto": texto, "transcripcion_asr": transcripcion, "respuesta": r["respuesta"],
           "voz": voz if con_voz else None, "audio": audio, "pasos_llm": r["pasos_llm"], "tiempos": tiempos,
           "operaciones": [{"paso": o["paso"], "herramienta": o["herramienta"],
                            "argumentos": json.dumps(o["argumentos"], ensure_ascii=False, default=str),
                            "resultado": "ok" if o["resultado"].get("ok")
                            else str(o["resultado"].get("error", o["resultado"].get("estado")))}
                           for o in r["operaciones"]],
           "productos": [{k: p.get(k) for k in ("posicion", "product_id", "titulo", "marca", "color", "precio", "stock")}
                         for p in e.mostrados],
           # la tabla de productos se muestra a la vista solo si el agente buscó en este turno
           "busco": any(o["herramienta"] == "buscar_productos" and o["resultado"].get("ok") for o in r["operaciones"]),
           "carrito": sis.h._carrito(),
           "presupuesto": e.presupuesto_cent / 100 if e.presupuesto_cent else None,
           "pedidos": [{"pedido_id": p["pedido_id"], "cotizacion_id": p["cotizacion_id"],
                        "total": p["total_cent"] / 100} for p in e.pedidos]}
    with open(SALIDA / "registro.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False, default=str) + "\n")
    return json.loads(json.dumps(out, ensure_ascii=False, default=str))


def _reiniciar(sid):
    sis = _sistema(sid)
    sis.reiniciar()
    return {"huella": sis.tienda.huella()}


def _requiere_carga():
    if not S["cargado"]:
        abort(400, "primero pulsa 'Iniciar asistente'")


def _error(ex):
    return jsonify({"error": f"{type(ex).__name__}: {ex}"}), 500


# 4 · rutas
@asistente.get("/api/estado")
def estado():
    return jsonify({k: S[k] for k in ("cargado", "cargando", "error", "carga")} | {"voces": voces()})


@asistente.post("/api/iniciar")
def iniciar():
    if S["cargado"] or S["cargando"]:
        return estado()
    S["cargando"], S["error"] = True, None
    try:
        en_hilo(_cargar)
        S["cargado"] = True
    except Exception as ex:
        S["error"] = f"{type(ex).__name__}: {ex}"
    finally:
        S["cargando"] = False
    return estado()


@asistente.post("/api/transcribir")
def transcribir():
    _requiere_carga()
    sid = _sesion()
    S["turno"] += 1
    ruta = SALIDA / f"usuario_{sid}_{S['turno']:05d}.wav"
    ruta.write_bytes(request.get_data())
    try:
        return jsonify(en_hilo(_transcribir, ruta))
    except Exception as ex:
        return _error(ex)


@asistente.post("/api/turno")
def turno():
    _requiere_carga()
    sid = _sesion()
    j = request.get_json(silent=True) or {}
    texto = str(j.get("texto", "")).strip()
    if not texto:
        abort(400, "escribe o dicta una consulta")
    try:
        return jsonify(en_hilo(_turno, sid, texto, j.get("voz"), bool(j.get("con_voz")),
                               float(j.get("t_asr") or 0), j.get("transcripcion")))
    except Exception as ex:
        return _error(ex)


@asistente.post("/api/reiniciar")
def reiniciar():
    _requiere_carga()
    sid = _sesion()
    try:
        return jsonify(en_hilo(_reiniciar, sid))
    except Exception as ex:
        return _error(ex)


@asistente.get("/audio/<nombre>")
def audio(nombre):
    if not re.fullmatch(r"(respuesta|usuario)_[0-9a-f]{16}_\d{5}(_multimedia\d{3})?\.wav", nombre):
        abort(400, "nombre de audio inválido")
    return send_from_directory(SALIDA, nombre, max_age=0)


@asistente.get("/")
def pagina():
    return PAGINA


PAGINA = r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Chat del asistente de compras</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font:15px system-ui,sans-serif;margin:0 auto;max-width:1000px;padding:16px;background:#fafafa;color:#222}
h1{font-size:20px}h3{font-size:14px;margin:12px 0 4px}table{border-collapse:collapse;width:100%;background:#fff;font-size:13px}
td,th{border-bottom:1px solid #e5e5e5;padding:4px 8px;text-align:left;vertical-align:top}th{background:#f0f0f0}
button,select,input[type=text]{font:inherit;padding:6px 12px;border:1px solid #bbb;border-radius:6px;background:#fff}
button{cursor:pointer;white-space:nowrap}button.p{background:#1d4ed8;color:#fff;border-color:#1d4ed8}
button.r{background:#dc2626;color:#fff;border-color:#dc2626}button:disabled{opacity:.5;cursor:default}
.nav{display:flex;gap:8px;margin-bottom:8px}.nav a{padding:6px 14px;border-radius:6px;text-decoration:none;color:#1d4ed8;border:1px solid #1d4ed8}
.nav a.on{background:#1d4ed8;color:#fff}
.panel{display:grid;grid-template-columns:260px 1fr;gap:16px;align-items:start}
@media(max-width:700px){.panel{grid-template-columns:1fr}}
.caja{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px}
#voz{width:100%;padding:4px}.barra{display:flex;flex-wrap:wrap;gap:8px;align-items:center}#txt{flex:1;min-width:200px}
.turno{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:12px;margin:12px 0}
.u{color:#1d4ed8}.a{font-size:16px;margin:6px 0}.gris{color:#666;font-size:13px}.err{color:#dc2626}#msg{min-height:20px;margin:8px 0}
table.prod{font-size:14px;margin:8px 0;border:1px solid #e5e5e5}table.prod th{background:#1d4ed8;color:#fff}
table.prod td.n{text-align:right;white-space:nowrap}table.prod td.cod{font-family:monospace;white-space:nowrap}.agotado{color:#dc2626;font-weight:600}
#medidor{height:8px;background:#e5e5e5;border-radius:4px;overflow:hidden;margin-top:8px}#nivel{height:100%;width:0;background:#15803d}
</style></head><body>
<div class=nav><a href="/">Configuración</a><a class=on href="/asistente">Chat</a></div>
<h1>Chat del asistente de compras</h1>
<div class=panel>
 <div class=caja>
  <label for=voz><b>Voz de respuesta</b></label>
  <select id=voz size=5></select>
  <p><label><input type=checkbox id=conVoz checked> Responder con voz</label></p>
  <div id=estado class=gris>Cargando modelos…</div>
  <p><button id=bRst onclick="reiniciar()" disabled>Reiniciar tienda</button></p>
  <div id=carga></div>
 </div>
 <div>
  <div class=caja>
   <div class=barra><button class=p id=bMic onclick="preguntar()" disabled>🎤 Preguntar</button>
    <span class=gris id=ayudaMic></span></div>
   <div id=medidor><div id=nivel></div></div>
   <div class=barra style="margin-top:12px">
    <input type=text id=txt placeholder="O escribe tu consulta y pulsa Enviar" onkeydown="if(event.key==='Enter')enviar()">
    <button id=bEnv onclick="enviar()" disabled>Enviar</button></div>
   <div id=msg></div>
  </div>
  <div id=chat></div>
 </div>
</div>
<script>
const $=s=>document.querySelector(s);const msg=(t,e)=>{$('#msg').textContent=t||'';$('#msg').className=e?'err':''};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>'&#'+c.charCodeAt(0)+';');
// cada pestaña del navegador es una conversación aparte (su propio carrito y tienda)
const SESION=(()=>{const nuevo=()=>[...crypto.getRandomValues(new Uint8Array(8))].map(b=>b.toString(16).padStart(2,'0')).join('');
  try{let s=sessionStorage.getItem('sesion');if(!s){s=nuevo();sessionStorage.setItem('sesion',s)}return s}catch(e){return nuevo()}})();
async function api(u,o={}){o.headers={...(o.headers||{}),'X-Sesion':SESION};const r=await fetch(u,o);const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j}
// fuera del aplicativo local (enlace compartido) solo se muestra el chat
if(location.port!=='5000')document.querySelector('.nav').style.display='none';
let CFG=null, ESCUCHA=null, OCUPADO=false;
function tabla(filas,cols){if(!filas||!filas.length)return'';return'<table><tr>'+cols.map(c=>`<th>${c}</th>`).join('')+'</tr>'+
  filas.map(f=>'<tr>'+cols.map(c=>`<td>${esc(f[c])}</td>`).join('')+'</tr>').join('')+'</table>'}
function pintarEstado(j){
  const sel=$('#voz'),antes=sel.value;
  sel.innerHTML=j.voces.map(v=>`<option value="${v.id}" ${v.lista?'':'disabled'}>${v.id} — ${esc(v.nombre)||'sin nombre'}${v.activa?' ★':''}${v.lista?'':' (sin referencia)'}</option>`).join('');
  sel.value=antes||(j.voces.find(v=>v.activa&&v.lista)||j.voces.find(v=>v.lista)||{}).id||'';
  ['#bMic','#bEnv','#bRst'].forEach(b=>$(b).disabled=!j.cargado);
  $('#estado').innerHTML=j.cargado?'<span style="color:#15803d">● Asistente listo</span> · ★ = voz por defecto':j.error?`<span class=err>Error al cargar: ${esc(j.error)}</span>`:'Cargando modelos… (≈1 min la primera vez)';
  $('#carga').innerHTML=j.carga.length?'<h3>Carga inicial (s)</h3>'+tabla(j.carga,['modelo','carga_s']):'';
}
async function preparar(){
  try{CFG=await api('/api/config');$('#ayudaMic').textContent=`Habla; se envía solo tras ${CFG.pausa_s} s de silencio (máx. ${CFG.max_grabacion_s} s).`}
  catch(e){msg('Configuración inválida: '+e.message+' (revísala en Configuración)',1);return}
  let j=await api('/asistente/api/estado');pintarEstado(j);
  if(!j.cargado&&!j.cargando){j=await api('/asistente/api/iniciar',{method:'POST'});pintarEstado(j)}
  while(j.cargando){await new Promise(r=>setTimeout(r,2000));j=await api('/asistente/api/estado');pintarEstado(j)}
}
async function preguntar(){
  if(ESCUCHA){ESCUCHA.parar();return}
  if(OCUPADO)return;
  let st;try{st=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1}})}catch(e){msg('Micrófono no disponible: '+e.message,1);return}
  const ctx=new AudioContext(),an=ctx.createAnalyser();an.fftSize=2048;ctx.createMediaStreamSource(st).connect(an);
  const buf=new Float32Array(an.fftSize),ch=[],rec=new MediaRecorder(st);rec.ondataavailable=e=>ch.push(e.data);
  const t0=performance.now();let hablo=false,ultimaVoz=t0;
  // 1 · cada 100 ms mide el volumen; tras haber hablado, una pausa de CFG.pausa_s detiene y envía
  const tic=setInterval(()=>{
    an.getFloatTimeDomainData(buf);let s=0;for(const v of buf)s+=v*v;
    const db=10*Math.log10(s/buf.length+1e-12),ahora=performance.now();
    if(db>CFG.umbral_voz_dbfs){hablo=true;ultimaVoz=ahora}
    $('#nivel').style.width=Math.max(0,Math.min(100,(db+70)*1.6))+'%';
    const sil=(ahora-ultimaVoz)/1000,tot=(ahora-t0)/1000;
    msg(hablo?`Escuchando… silencio ${sil.toFixed(1)} / ${CFG.pausa_s} s`:'Escuchando… empieza a hablar');
    if((hablo&&sil>=CFG.pausa_s)||tot>=CFG.max_grabacion_s)parar();
  },100);
  function parar(){clearInterval(tic);ESCUCHA=null;if(rec.state!=='inactive')rec.stop()}
  rec.onstop=async()=>{
    st.getTracks().forEach(t=>t.stop());ctx.close();$('#nivel').style.width='0';
    $('#bMic').className='p';$('#bMic').textContent='🎤 Preguntar';
    if(!hablo){msg('No se detectó voz. Revisa el micrófono o baja el umbral en Configuración.',1);return}
    OCUPADO=true;msg('Transcribiendo…');
    try{const j=await api('/asistente/api/transcribir',{method:'POST',body:await aWav(new Blob(ch))});
      await turno(j.texto,j.t_asr,j.texto)}catch(e){msg(e.message,1)}finally{OCUPADO=false}
  };
  rec.start();ESCUCHA={parar};$('#bMic').className='r';$('#bMic').textContent='■ Detener y enviar';
}
async function enviar(){
  const texto=$('#txt').value.trim();if(!texto||OCUPADO)return;
  OCUPADO=true;$('#bEnv').disabled=true;
  try{await turno(texto,0,null);$('#txt').value=''}catch(e){msg(e.message,1)}finally{OCUPADO=false;$('#bEnv').disabled=false}
}
async function turno(texto,t_asr,transcripcion){
  msg('El asistente está buscando…');
  const j=await api('/asistente/api/turno',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({texto,voz:$('#voz').value,con_voz:$('#conVoz').checked,t_asr,transcripcion})});
  msg('');pintarTurno(j);
}
const euro=v=>v==null?'':Number(v).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})+' €';
function tablaProductos(ps){
  return '<table class=prod><tr><th>N°</th><th>Código</th><th>Descripción</th><th>Precio</th><th>Stock</th></tr>'+
    ps.map(p=>`<tr><td class=n>${esc(p.posicion)}</td><td class=cod>${esc(p.product_id)}</td><td>${esc(p.titulo)}</td>
    <td class=n>${euro(p.precio)}</td><td class=n>${p.stock>0?esc(p.stock):'<span class=agotado>agotado</span>'}</td></tr>`).join('')+'</table>'}
function pintarTurno(j){
  const verProd=j.busco&&j.productos.length;
  const car=j.carrito.items.length?`<h3>Carrito en la base de datos (total ${j.carrito.total} €; presupuesto ${j.presupuesto??'no indicado'})</h3>`+tabla(j.carrito.items,['titulo','cantidad','precio','subtotal','stock']):'';
  const d=document.createElement('div');d.className='turno';
  d.innerHTML=`<div class=u><b>Tú${j.transcripcion_asr?' (voz)':''}:</b> ${esc(j.texto)}</div><div class=a><b>Asistente:</b> ${esc(j.respuesta)}</div>
  ${j.audio?`<audio controls autoplay src="/asistente/audio/${j.audio}"></audio> <span class=gris>voz ${j.voz}</span>`:''}
  ${verProd?'<h3>Productos encontrados</h3>'+tablaProductos(j.productos):''}
  <details><summary class=gris>Detalle: operaciones, ${verProd?'':'productos de la última búsqueda, '}carrito, pedidos y tiempos</summary>
  ${j.operaciones.length?'<h3>Operaciones ejecutadas</h3>'+tabla(j.operaciones,['paso','herramienta','argumentos','resultado']):''}
  ${!verProd&&j.productos.length?'<h3>Productos de la última búsqueda</h3>'+tablaProductos(j.productos):''}
  ${car}${j.pedidos.length?'<h3>Pedidos registrados</h3>'+tabla(j.pedidos,['pedido_id','cotizacion_id','total']):''}
  <h3>Tiempo por etapa (s) · ${j.pasos_llm} pasos del LLM</h3>${tabla([j.tiempos],['asr','recuperacion','llm','herramientas','tts','total'])}</details>`;
  $('#chat').append(d);d.scrollIntoView({behavior:'smooth',block:'end'});
}
async function reiniciar(){try{const j=await api('/asistente/api/reiniciar',{method:'POST'});$('#chat').innerHTML='';msg('Tienda restaurada al estado inicial (huella '+j.huella+').')}catch(e){msg(e.message,1)}}
async function aWav(blob){
  const buf=await new AudioContext().decodeAudioData(await blob.arrayBuffer());
  const SR=16000,off=new OfflineAudioContext(1,Math.ceil(buf.duration*SR),SR),s=off.createBufferSource();
  s.buffer=buf;s.connect(off.destination);s.start();const x=(await off.startRendering()).getChannelData(0);
  const v=new DataView(new ArrayBuffer(44+x.length*2)),w=(o,t)=>[...t].forEach((c,i)=>v.setUint8(o+i,c.charCodeAt(0)));
  w(0,'RIFF');v.setUint32(4,36+x.length*2,true);w(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);
  v.setUint32(24,SR,true);v.setUint32(28,SR*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);w(36,'data');v.setUint32(40,x.length*2,true);
  x.forEach((s,i)=>v.setInt16(44+i*2,Math.max(-1,Math.min(1,s))*32767,true));return new Blob([v],{type:'audio/wav'});
}
preparar().catch(e=>msg(e.message,1));
</script></body></html>"""
