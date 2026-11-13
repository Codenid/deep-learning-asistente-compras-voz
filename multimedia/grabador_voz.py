"""Grabador de voces para el Laboratorio 4 (independiente del notebook).

Uso:  doble clic en multimedia.bat (raíz del proyecto); abre http://localhost:5000
Cada voz se guarda junto a este archivo, en multimedia/multimediaNNN/:
    referencia.wav, referencia_2.wav (opcional), audios/E01_t1.wav ... E06_t5.wav
    entrenamiento/ latentes.pt (XTTS), prueba.wav, informe.json
La voz elegida con "Usar en el programa" queda en multimedia/ACTIVA.txt y el notebook la lee.
"""
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from flask import Flask, abort, jsonify, request, send_from_directory

MULTI = Path(__file__).resolve().parent  # carpeta multimedia/
RAIZ = MULTI.parent                       # raíz del proyecto (docs/)
ACTIVA = MULTI / "ACTIVA.txt"
CONFIG = MULTI / "configuracion.json"  # parámetros del chat; se editan en el módulo Configuración
# Rangos válidos de cada parámetro del chat
LIMITES = {"pausa_s": (1, 15), "max_grabacion_s": (5, 120), "umbral_voz_dbfs": (-70, -20)}
MODELO_TTS = "tts_models/multilingual/multi-dataset/xtts_v2"
SR = 22050  # formato de guardado: WAV PCM 16 bits, mono, 22 050 Hz

# Mismo texto que TEXTO_REF del notebook (el TTS nunca lo repite)
TEXTO_REF = ("Hola, esta es mi voz de referencia para el asistente de compras. "
             "La grabo en un lugar tranquilo, hablando con calma y a un ritmo natural.")
TEXTO_REF2 = ("Prefiero comprar por voz porque es rápido y cómodo, "
              "sobre todo cuando tengo las manos ocupadas en la cocina.")
TEXTO_PRUEBA = ("Tu pedido de dos paquetes de pilas quedó confirmado, "
                "el total es de dieciocho euros con noventa y ocho céntimos.")

# Ítems a grabar: 2 de clonación + 23 frases de docs/GUION_GRABACION.md
ITEMS = {
    "referencia": {"archivo": "referencia.wav", "texto": TEXTO_REF, "grupo": "Clonación (obligatorio, 6-15 s)"},
    "referencia_2": {"archivo": "referencia_2.wav", "texto": TEXTO_REF2, "grupo": "Clonación (opcional: techo de semejanza)"},
}
_guion = (RAIZ / "docs" / "GUION_GRABACION.md").read_text(encoding="utf-8")
for _id, _txt in re.findall(r"^\| `(E\d\d_t\d+)\.wav` \| (.+?) \|\s*$", _guion, re.M):
    ITEMS[_id] = {"archivo": f"audios/{_id}.wav", "texto": _txt, "grupo": f"Escenario {_id[:3]} (por voz)"}
ITEMS["E05_t1"]["nota"] = 'Di "A4" como "a cuatro" (caso de corrección de transcripción).'
OBLIGATORIOS = [k for k in ITEMS if k != "referencia_2"]

app = Flask(__name__)

from asistente_web import asistente  # módulo Asistente: conversar con el asistente eligiendo la voz (/asistente)
import compartir                       # enlace público de Cloudflare solo para el chat
app.register_blueprint(asistente)


def carpeta(sid):
    if not re.fullmatch(r"multimedia\d{3}", sid or ""):
        abort(400, "id de voz inválido")
    d = MULTI / sid
    if not d.is_dir():
        abort(404, "no existe la voz")
    return d


def calidad(ruta, es_ref=False):
    x, sr = sf.read(str(ruta), dtype="float32")
    x = x.mean(1) if x.ndim > 1 else x
    if not len(x):
        return {"seg": 0, "avisos": ["vacío"]}
    f = int(sr * 0.03)
    n = len(x) // f
    tramas = np.sqrt((x[:n * f].reshape(n, f) ** 2).mean(1)) if n else np.zeros(1)
    db = lambda v: round(20 * np.log10(max(float(v), 1e-9)), 1)
    q = {"seg": round(len(x) / sr, 2), "pico_dbfs": db(np.abs(x).max()), "rms_dbfs": db(np.sqrt((x ** 2).mean())),
         "voz_activa": round(float((tramas > 0.01).mean()), 2), "saturacion": round(float((np.abs(x) >= 0.99).mean()), 4)}
    av = []
    if q["saturacion"] > 0.001:
        av.append("saturado: aleja el micrófono")
    if q["rms_dbfs"] < -40:
        av.append("muy bajo: acércate o sube la ganancia")
    if q["voz_activa"] < 0.4:
        av.append("mucho silencio")
    if es_ref and not 6 <= q["seg"] <= 15:
        av.append("la referencia debe durar 6-15 s")
    q["avisos"] = av
    return q


def leer_meta(sid):
    m = MULTI / sid / "meta.json"
    return json.loads(m.read_text(encoding="utf-8")) if m.exists() else {"id": sid}


def resumen(sid):
    d = MULTI / sid
    hechos = [k for k, it in ITEMS.items() if (d / it["archivo"]).exists()]
    inf = d / "entrenamiento" / "informe.json"
    inf = json.loads(inf.read_text(encoding="utf-8")) if inf.exists() else None
    activa = ACTIVA.read_text().strip() if ACTIVA.exists() else ""
    return {"id": sid, "nombre": leer_meta(sid).get("nombre", ""), "grabados": len(hechos), "total": len(ITEMS),
            "completa": all(k in hechos for k in OBLIGATORIOS), "hechos": hechos,
            "semejanza": inf and inf.get("semejanza_prueba"), "entrenada": bool(inf), "activa": activa == sid}


@app.get("/api/voces")
def voces():
    MULTI.mkdir(exist_ok=True)
    return jsonify([resumen(p.name) for p in sorted(MULTI.glob("multimedia[0-9][0-9][0-9]")) if p.is_dir()])


@app.post("/api/voces")
def nueva():
    MULTI.mkdir(exist_ok=True)
    nums = [int(p.name[10:]) for p in MULTI.glob("multimedia[0-9][0-9][0-9]")]
    sid = f"multimedia{max(nums, default=0) + 1:03d}"
    (MULTI / sid / "audios").mkdir(parents=True)
    meta = {"id": sid, "nombre": str((request.get_json(silent=True) or {}).get("nombre", "")).strip()[:60], "creado": time.strftime("%Y-%m-%d %H:%M:%S"), "formato": f"WAV PCM 16 bits mono {SR} Hz",
            "texto_referencia": TEXTO_REF}
    (MULTI / sid / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify(resumen(sid))


@app.get("/api/voces/<sid>")
def detalle(sid):
    d = carpeta(sid)
    filas = []
    for k, it in ITEMS.items():
        p = d / it["archivo"]
        filas.append({"id": k, **it, "existe": p.exists(),
                      "calidad": calidad(p, k.startswith("referencia")) if p.exists() else None})
    inf = d / "entrenamiento" / "informe.json"
    return jsonify({**resumen(sid), "items": filas,
                    "informe": json.loads(inf.read_text(encoding="utf-8")) if inf.exists() else None})


@app.post("/api/voces/<sid>/<item>")
def guardar(sid, item):
    d = carpeta(sid)
    if item not in ITEMS:
        abort(400, "ítem desconocido")
    p = d / ITEMS[item]["archivo"]
    p.parent.mkdir(exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(request.get_data())
    try:
        sf.info(str(tmp))  # valida que sea un WAV legible
    except Exception:
        tmp.unlink()
        abort(400, "audio inválido")
    tmp.replace(p)
    return jsonify(calidad(p, item.startswith("referencia")))


_TTS = None


def xtts():
    global _TTS
    if _TTS is None:
        os.environ.setdefault("COQUI_TOS_AGREED", "1")  # licencia CPML (uso no comercial)
        import torch
        from TTS.api import TTS
        _TTS = TTS(MODELO_TTS).to("cuda" if torch.cuda.is_available() else "cpu")
    return _TTS


@app.post("/api/voces/<sid>/entrenar")
def entrenar(sid):
    d = carpeta(sid)
    ref, ref2 = d / "referencia.wav", d / "referencia_2.wav"
    if not ref.exists():
        abort(400, "falta referencia.wav")
    out = d / "entrenamiento"
    out.mkdir(exist_ok=True)
    inf = {"voz": sid, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "modelo": MODELO_TTS,
           "calidad": {k: calidad(d / it["archivo"], k.startswith("referencia"))
                       for k, it in ITEMS.items() if (d / it["archivo"]).exists()}}
    inf["avisos"] = sum(len(q["avisos"]) for q in inf["calidad"].values())
    try:
        import torch
        t0 = time.perf_counter()
        api = xtts()
        inf["seg_carga_modelo"] = round(time.perf_counter() - t0, 1)
        m, sr = api.synthesizer.tts_model, api.synthesizer.output_sample_rate
        t0 = time.perf_counter()
        lat, spk = m.get_conditioning_latents(audio_path=[str(ref)])
        inf["seg_latentes"] = round(time.perf_counter() - t0, 2)
        torch.save({"gpt_cond_latent": lat.cpu(), "speaker_embedding": spk.cpu(), "modelo": MODELO_TTS}, out / "latentes.pt")
        torch.manual_seed(0)
        t0 = time.perf_counter()
        wav = m.inference(TEXTO_PRUEBA, "es", lat, spk, temperature=0.7)["wav"]
        inf["seg_sintesis"] = round(time.perf_counter() - t0, 2)
        sf.write(str(out / "prueba.wav"), np.asarray(wav, dtype=np.float32), sr)
        emb = lambda p: m.get_conditioning_latents(audio_path=[str(p)])[1].flatten().float()
        cos = lambda a, b: round(float(torch.nn.functional.cosine_similarity(a, b, dim=0)), 3)
        base = spk.flatten().float()
        inf["semejanza_prueba"] = cos(emb(out / "prueba.wav"), base)  # voz clonada vs referencia
        if ref2.exists():
            inf["techo_ref2"] = cos(emb(ref2), base)  # misma persona, otra grabación
        inf["texto_prueba"] = TEXTO_PRUEBA
    except ImportError as e:
        inf["tts"] = f"XTTS no disponible ({e}): solo control de calidad"
    (out / "informe.json").write_text(json.dumps(inf, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify(inf)


@app.post("/api/voces/<sid>/nombre")
def renombrar(sid):
    carpeta(sid)
    meta = leer_meta(sid)
    meta["nombre"] = str((request.get_json(silent=True) or {}).get("nombre", "")).strip()[:60]
    (MULTI / sid / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return jsonify(resumen(sid))


@app.post("/api/voces/<sid>/activar")
def activar(sid):
    carpeta(sid)
    ACTIVA.write_text(sid, encoding="utf-8")
    return jsonify({"activa": sid})


def validar_config(c):
    faltan = [k for k in LIMITES if k not in c]
    if faltan:
        abort(400, f"faltan parámetros: {', '.join(faltan)}")
    out = {}
    for k, (minimo, maximo) in LIMITES.items():
        try:
            v = float(c[k])
        except (TypeError, ValueError):
            abort(400, f"{k} debe ser un número")
        if not minimo <= v <= maximo:
            abort(400, f"{k} debe estar entre {minimo} y {maximo}")
        out[k] = v
    return out


@app.get("/api/config")
def leer_config():
    if not CONFIG.exists():
        abort(404, f"falta multimedia/{CONFIG.name}")
    return jsonify(validar_config(json.loads(CONFIG.read_text(encoding="utf-8"))))


@app.post("/api/config")
def guardar_config():
    c = validar_config(request.get_json(silent=True) or {})
    CONFIG.write_text(json.dumps(c, indent=1), encoding="utf-8")
    return jsonify(c)


@app.get("/api/compartir")
def estado_compartir():
    return jsonify(compartir.estado())


@app.post("/api/compartir")
def cambiar_compartir():
    activar = bool((request.get_json(silent=True) or {}).get("activar"))
    try:
        if activar:
            return jsonify(compartir.habilitar(compartir.crear_app_chat(asistente, leer_config, error)))
        return jsonify(compartir.deshabilitar())
    except (RuntimeError, OSError) as ex:   # OSError: el puerto del chat ya está en uso
        return jsonify({"error": str(ex)}), 500


@app.get("/archivo/<sid>/<path:ruta>")
def archivo(sid, ruta):
    return send_from_directory(carpeta(sid), ruta, max_age=0)


@app.errorhandler(400)
@app.errorhandler(404)
def error(e):
    return jsonify({"error": e.description}), e.code


@app.get("/")
def inicio():
    return PAGINA


PAGINA = r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Grabador de voces</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font:15px system-ui,sans-serif;margin:0 auto;max-width:1000px;padding:16px;background:#fafafa;color:#222}
h1{font-size:20px}h2{font-size:17px;margin-top:28px}table{border-collapse:collapse;width:100%;background:#fff}
td,th{border-bottom:1px solid #e5e5e5;padding:6px 8px;text-align:left;vertical-align:middle}th{background:#f0f0f0}
button{font:inherit;padding:5px 12px;white-space:nowrap;border:1px solid #bbb;border-radius:6px;background:#fff;cursor:pointer}
button.p{background:#1d4ed8;color:#fff;border-color:#1d4ed8}button.r{background:#dc2626;color:#fff;border-color:#dc2626}
button:disabled{opacity:.5;cursor:default}.ok{color:#15803d}.av{color:#b45309;font-size:13px}.g td{background:#eef2ff;font-weight:600}
.txt{font-size:16px}.nota{color:#b45309;font-size:13px}audio{height:30px;width:200px}#msg{margin:10px 0;min-height:20px}
.nav{display:flex;gap:8px;margin-bottom:8px}.nav a{padding:6px 14px;border-radius:6px;text-decoration:none;color:#1d4ed8;border:1px solid #1d4ed8}
.nav a.on{background:#1d4ed8;color:#fff}.cfg{display:flex;flex-wrap:wrap;gap:14px;align-items:end;background:#fff;padding:12px;border:1px solid #e5e5e5;border-radius:8px}
.cfg label{display:flex;flex-direction:column;font-size:13px;gap:4px}.cfg input{font:inherit;width:110px;padding:4px 6px}
</style></head><body>
<div class=nav><a class=on href="/">Configuración</a><a href="/asistente">Chat</a></div>
<h1>Configuración — Laboratorio 4</h1>
<h2>Parámetros del chat</h2>
<div class=cfg>
<label>Pausa para enviar (s)<input type=number id=pausa_s min=1 max=15 step=0.5></label>
<label>Grabación máxima (s)<input type=number id=max_grabacion_s min=5 max=120 step=1></label>
<label>Umbral de voz (dBFS)<input type=number id=umbral_voz_dbfs min=-70 max=-20 step=1></label>
<button class=p onclick="guardarCfg()">Guardar</button><span id=msgCfg></span></div>
<p class=nota>En el chat, al pulsar «Preguntar», la grabación se envía sola cuando hay una pausa de este largo.
Si el micrófono capta mucho ruido, sube el umbral (p. ej. −40); si no detecta tu voz, bájalo (p. ej. −55).</p>
<h2>Compartir el chat con compañeros</h2>
<div class=cfg><button class=p id=bComp onclick="compartir()" disabled>Habilitar enlace público (sin clave)</button><span id=enlace></span></div>
<p class=nota>Solo se publica el chat; esta página de configuración sigue siendo privada. Mientras esté habilitado, cualquiera con el
enlace puede usar el chat sin clave. Tu PC debe seguir encendida con multimedia.bat abierto. Hay una sola GPU: si varios preguntan
a la vez, las respuestas salen en orden. Cada compañero tiene su propio carrito. El enlace cambia cada vez que lo habilitas.</p>
<h2>Voces</h2>
<p>Cada voz se guarda en <code>multimedia/multimediaNNN/</code>. Graba, prueba la clonación y elige la voz por defecto (la usan el chat y el notebook).</p>
<button class="p" onclick="nueva()">+ Nueva voz</button>
<table id="lista"></table><div id="msg"></div><div id="voz"></div>
<script>
let SID=null, REC=null, VOZ_NOMBRE='';
const $=s=>document.querySelector(s);
const msg=t=>$('#msg').textContent=t||'';
async function api(u,o){const r=await fetch(u,o);const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j}
async function lista(){
  const v=await api('/api/voces');
  $('#lista').innerHTML='<tr><th>Voz</th><th>De quién es</th><th>Grabados</th><th>Completa</th><th>Semejanza XTTS</th><th>Por defecto</th><th></th></tr>'+
  v.map(x=>`<tr><td>${x.id}</td><td><b>${esc(x.nombre)||'<i>sin nombre</i>'}</b> <button onclick="renombrar('${x.id}','${esc(x.nombre)}')">✎</button></td><td>${x.grabados}/${x.total}</td><td>${x.completa?'<span class=ok>sí</span>':'no'}</td>
  <td>${x.semejanza??(x.entrenada?'solo calidad':'—')}</td><td>${x.activa?'<b class=ok>POR DEFECTO</b>':`<button onclick="predeterminar('${x.id}')">Elegir</button>`}</td>
  <td><button onclick="abrir('${x.id}')">Abrir</button></td></tr>`).join('');
}
const esc=s=>(s||'').replace(/[&<>"']/g,c=>'&#'+c.charCodeAt(0)+';');
const JS={'Content-Type':'application/json'};
async function nueva(){const n=prompt('¿De quién es esta voz? (nombre)');if(n===null)return;
  const j=await api('/api/voces',{method:'POST',headers:JS,body:JSON.stringify({nombre:n})});await lista();abrir(j.id)}
async function renombrar(id,actual){const n=prompt('Nombre de la voz '+id,actual);if(n===null)return;
  await api(`/api/voces/${id}/nombre`,{method:'POST',headers:JS,body:JSON.stringify({nombre:n})});await lista();if(SID===id)abrir(id)}
function q(c){if(!c)return'';const a=c.avisos.length?`<div class=av>${c.avisos.join(' · ')}</div>`:'<span class=ok>ok</span>';
  return `${c.seg}s · ${c.rms_dbfs} dB ${a}`}
async function abrir(id){
  SID=id;const j=await api('/api/voces/'+id);VOZ_NOMBRE=j.nombre;let g='',h='';
  for(const it of j.items){
    if(it.grupo!==g){g=it.grupo;h+=`<tr class=g><td colspan=4>${g}</td></tr>`}
    h+=`<tr><td style="width:110px">${it.archivo}</td><td class=txt>${it.texto}${it.nota?`<div class=nota>${it.nota}</div>`:''}</td>
    <td>${it.existe?`<audio controls src="/archivo/${id}/${it.archivo}?t=${Date.now()}"></audio><br>${q(it.calidad)}`:''}</td>
    <td><button class="${it.existe?'':'p'} rec" onclick="grabar('${it.id}',this)">● ${it.existe?'Regrabar':'Grabar'}</button></td></tr>`}
  const inf=j.informe;let ih='';
  if(inf){ih=`<h2>Entrenamiento (${inf.fecha})</h2><p>${inf.tts||`Semejanza voz clonada vs referencia: <b>${inf.semejanza_prueba}</b>`+
    (inf.techo_ref2!=null?` · techo (referencia_2): <b>${inf.techo_ref2}</b>`:'')+` · latentes ${inf.seg_latentes}s · síntesis ${inf.seg_sintesis}s`}
    · avisos de calidad: ${inf.avisos}</p>${inf.texto_prueba?`<p>«${inf.texto_prueba}»<br><audio controls src="/archivo/${id}/entrenamiento/prueba.wav?t=${Date.now()}"></audio></p>`:''}`}
  $('#voz').innerHTML=`<h2>${id} — ${esc(j.nombre)||'sin nombre'} ${j.activa?'(POR DEFECTO)':''}</h2>
  <button class=p onclick="entrenar()">Entrenar / probar clonación</button>
  <button onclick="activar()">Usar por defecto</button>${ih}<table>${h}</table>`;
}
async function grabar(item,btn){
  if(REC){REC.stop();return}
  try{
    const st=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
    const ch=[];REC=new MediaRecorder(st);REC.ondataavailable=e=>ch.push(e.data);
    REC.onstop=async()=>{st.getTracks().forEach(t=>t.stop());REC=null;msg('Guardando…');
      try{const c=await api(`/api/voces/${SID}/${item}`,{method:'POST',body:await aWav(new Blob(ch))});
        msg(`Guardado ${item}: ${c.seg}s `+(c.avisos.join(' · ')||'ok'))}catch(e){msg('Error: '+e.message)}
      await abrir(SID);lista()};
    REC.start();document.querySelectorAll('.rec').forEach(b=>b.disabled=b!==btn);
    btn.className='r rec';btn.textContent='■ Detener';msg('Grabando… lee el texto y pulsa Detener');
  }catch(e){msg('Micrófono no disponible: '+e.message)}
}
async function aWav(blob){
  const buf=await new AudioContext().decodeAudioData(await blob.arrayBuffer());
  const SR=22050,off=new OfflineAudioContext(1,Math.ceil(buf.duration*SR),SR),s=off.createBufferSource();
  s.buffer=buf;s.connect(off.destination);s.start();const x=(await off.startRendering()).getChannelData(0);
  const v=new DataView(new ArrayBuffer(44+x.length*2)),w=(o,t)=>[...t].forEach((c,i)=>v.setUint8(o+i,c.charCodeAt(0)));
  w(0,'RIFF');v.setUint32(4,36+x.length*2,true);w(8,'WAVEfmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);
  v.setUint32(24,SR,true);v.setUint32(28,SR*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);w(36,'data');v.setUint32(40,x.length*2,true);
  x.forEach((s,i)=>v.setInt16(44+i*2,Math.max(-1,Math.min(1,s))*32767,true));return new Blob([v],{type:'audio/wav'});
}
async function entrenar(){msg('Entrenando… la primera vez descarga XTTS (~1,8 GB) y tarda varios minutos');
  try{const j=await api(`/api/voces/${SID}/entrenar`,{method:'POST'});msg(j.tts||'Listo: semejanza '+j.semejanza_prueba)}catch(e){msg('Error: '+e.message)}
  await abrir(SID);lista()}
async function activar(){await api(`/api/voces/${SID}/activar`,{method:'POST'});msg(SID+(VOZ_NOMBRE?' ('+VOZ_NOMBRE+')':'')+' es la voz por defecto (multimedia/ACTIVA.txt)');await abrir(SID);lista()}
async function predeterminar(id){await api(`/api/voces/${id}/activar`,{method:'POST'});msg(id+' es la voz por defecto');if(SID===id)abrir(id);lista()}
const CAMPOS=['pausa_s','max_grabacion_s','umbral_voz_dbfs'];
async function cargarCfg(){try{const c=await api('/api/config');CAMPOS.forEach(k=>$('#'+k).value=c[k])}catch(e){$('#msgCfg').textContent='Error: '+e.message}}
async function guardarCfg(){try{const c=await api('/api/config',{method:'POST',headers:JS,body:JSON.stringify(Object.fromEntries(CAMPOS.map(k=>[k,$('#'+k).value])))});
  CAMPOS.forEach(k=>$('#'+k).value=c[k]);$('#msgCfg').textContent=' Guardado ✓'}catch(e){$('#msgCfg').textContent=' Error: '+e.message}}
function pintarComp(j){const b=$('#bComp');b.disabled=false;
  if(j.activo){b.className='r';b.textContent='Deshabilitar enlace';
    $('#enlace').innerHTML=`<a href="${esc(j.url)}" target=_blank><b>${esc(j.url)}</b></a> <button onclick="copiar('${esc(j.url)}')">Copiar</button>`}
  else{b.className='p';b.textContent='Habilitar enlace público (sin clave)';$('#enlace').textContent=''}}
async function compartir(){const activar=!$('#bComp').textContent.startsWith('Deshabilitar');$('#bComp').disabled=true;
  $('#enlace').textContent=activar?' Abriendo el túnel de Cloudflare… (hasta 40 s)':' Cerrando…';
  try{pintarComp(await api('/api/compartir',{method:'POST',headers:JS,body:JSON.stringify({activar})}))}
  catch(e){$('#enlace').textContent=' Error: '+e.message;$('#bComp').disabled=false}}
function copiar(u){navigator.clipboard.writeText(u).then(()=>msg('Enlace copiado: pégalo en el chat de tus compañeros'))}
api('/api/compartir').then(pintarComp);cargarCfg();lista();
</script></body></html>"""

if __name__ == "__main__":
    import threading, webbrowser
    threading.Timer(1.5, webbrowser.open, ["http://localhost:5000"]).start()
    print("Configuracion (voces y parametros): http://localhost:5000  (cerrar esta ventana para detenerlo)")
    print("Chat con el asistente:              http://localhost:5000/asistente")
    app.run(host="127.0.0.1", port=5000, threaded=True)
