"""Pruebas sin descargar ni cargar modelos: validadores, filtros y protocolo de acciones."""
import json
import sys
import tempfile
from pathlib import Path
from IPython.display import display
import numpy as np
import pandas as pd

nb=json.loads(Path('Laboratorio4_Asistente.ipynb').read_text(encoding='utf-8'))
C=sys.modules[__name__]
for i in [3,4,10,13,18,19,22,23,24,25]:
    exec(compile(''.join(nb['cells'][i]['source']), f'celda_{i}', 'exec'), globals())
autoprueba()

# El parser solo admite literales y llamadas del esquema; nunca evalua codigo arbitrario.
assert analizar_salida('cotizar()')['llamadas'] == [{'nombre':'cotizar','argumentos':{}}]
assert analizar_salida('agregar_al_carrito("real", cantidad=2), cotizar()')['llamadas'][0]['argumentos'] == {'product_id':'real','cantidad':2}
doble='<tool_call>{"name":"registrar_restricciones","arguments":{"presupuesto_max":30}}\n<tool_call>{"name":"buscar_productos","arguments":{"consulta":"pilas","cantidad":2}}'
assert [c['nombre'] for c in analizar_salida(doble)['llamadas']]==['registrar_restricciones','buscar_productos']
assert not es_confirmacion('Vale, agrega dos mas y cotiza.')
assert not es_confirmacion('Si, pero cambia la cantidad primero.')
assert es_confirmacion('De acuerdo, confirmo con el nuevo precio.')
for peligro in ['__import__("os").system("echo incorrecto")', 'cotizar(**dict())', 'cotizar(); x=1', 'cotizar(open("x"))']:
    assert not analizar_salida(peligro)['llamadas'], peligro

# Catalogo controlado: la opcion barata no puede violar color, marca, stock o total.
cat=pd.DataFrame([
    dict(product_id='uno',titulo='Mochila negra',marca='Marca A',color='Negro',descripcion='',caracteristicas=''),
    dict(product_id='dos',titulo='Mochila gris',marca='Marca A',color='Gris',descripcion='',caracteristicas=''),
    dict(product_id='tres',titulo='Mochila negra',marca='Marca B',color='Negro',descripcion='',caracteristicas='')])
tmp=Path(tempfile.mkdtemp())
Tienda.crear_base(tmp/'base.sqlite',cat.product_id,1,3,.8,(1.99,399.99),0,25)
tienda=Tienda(tmp/'base.sqlite',tmp/'trabajo.sqlite',20)
rec=Recuperador(cat)
sis=Sistema(cat,rec,tienda,None)
h=sis.h
h.metodo='bm25'
for pid,precio,stock in [('uno',1200,5),('dos',100,5),('tres',400,1)]:
    tienda.fijar_precio(pid,precio)
    tienda.fijar_stock(pid,stock)
h.registrar_restricciones(presupuesto_max=20)
r=h.buscar_productos('mochila',cantidad=2,marca='Marca A',color='Negro',ordenar='precio')
assert r['opciones_viables']==0 and 'presupuesto' in ' '.join(r['problemas'])
h.registrar_restricciones(presupuesto_max=30)
r=h.buscar_productos('mochila',cantidad=2,marca='Marca A',color='Negro',ordenar='precio')
assert [f['product_id'] for f in r['resultados']]==['uno']
h.agregar_al_carrito('uno',2)
h.cotizar()
h.estado.cotizacion_mostrada=True
h.registrar_restricciones(presupuesto_max=10)
h.estado.texto_usuario='confirmo'
assert not h.ejecutar('confirmar_pedido',{})['ok'], 'una restriccion nueva requiere nueva cotizacion'

# Una afirmacion del modelo no sustituye una llamada real: se obliga a continuar.
sis.reiniciar()
h=sis.h
h.metodo='bm25'
h.agregar_al_carrito('uno',1)
h.cotizar()
h.estado.cotizacion_mostrada=True
class BackendDePrueba:
    def __init__(self): self.salidas=iter(['Pedido confirmado.',llamada('confirmar_pedido'),'Pedido registrado.'])
    def generar(self,mensajes,herramientas): return analizar_salida(next(self.salidas))
ag=Agente(BackendDePrueba(),h)
r=ag.turno('Confirmo.')
assert len(tienda.resumen()['pedidos'])==1
assert any(o['herramienta']=='confirmar_pedido' for o in r['operaciones'])

# Cambiar un precio exige una cotizacion nueva antes del consentimiento siguiente.
sis.reiniciar();h=sis.h;h.metodo='bm25'
h.agregar_al_carrito('uno',1);h.cotizar();h.estado.cotizacion_mostrada=True
precio=tienda.producto('uno')['precio_cent']+300
tienda.fijar_precio('uno',precio)
class BackendPrecio:
    def __init__(self):self.salidas=iter([llamada('confirmar_pedido'),'El precio cambio.',llamada('cotizar'),'Nueva cotizacion.',llamada('confirmar_pedido'),'Registrado.'])
    def generar(self,mensajes,herramientas):return analizar_salida(next(self.salidas))
ag=Agente(BackendPrecio(),h)
r=ag.turno('Si, confirmo.')
assert not tienda.resumen()['pedidos'] and h.estado.cotizacion_mostrada
assert any(o['herramienta']=='cotizar' for o in r['operaciones'])
ag.turno('De acuerdo, confirmo con el nuevo precio.')
assert tienda.resumen()['pedidos'][0]['total_cent']==precio

# Los filtros se aplican al titulo completo y completan los candidatos truncados.
filas=[
 dict(product_id='agotado',titulo='Termo acero inoxidable',marca='Original',color='Negro',descripcion='',caracteristicas=''),
 dict(product_id='alternativa',titulo='Botella de acero inoxidable para viajes '+('descripcion larga '*10)+'Termo',marca='Alternativa',color='Negro',descripcion='',caracteristicas=''),
 dict(product_id='base12',titulo='Funda iPhone 12 negro',marca='FundaMarca',color='Negro',descripcion='',caracteristicas=''),
 dict(product_id='max12',titulo='Funda iPhone 12 Pro MAX negro',marca='FundaMarca',color='Negro',descripcion='',caracteristicas=''),
 dict(product_id='altavoz',titulo='Altavoz Bluetooth',marca='AudioMarca',color='Negro',descripcion='',caracteristicas=''),
 dict(product_id='cinta',titulo='Cinta de correr con altavoces Bluetooth',marca='GymMarca',color='Negro',descripcion='',caracteristicas=''),
 dict(product_id='cinta_comas',titulo='GymMarca Cinta de Correr Motor 440W, Altavoces Bluetooth, Pantalla LCD',marca='GymMarca',color='Negro',descripcion='',caracteristicas='')]
cat2=pd.DataFrame(filas)
class CandidatosTruncados(Recuperador):
    def buscar(self,*a,**kw):return [0]
rec2=CandidatosTruncados(cat2)
Tienda.crear_base(tmp/'base2.sqlite',cat2.product_id,1,3,.8,(1.99,399.99),0,25)
t2=Tienda(tmp/'base2.sqlite',tmp/'trabajo2.sqlite',20)
s2=Sistema(cat2,rec2,t2,None);h2=s2.h
t2.fijar_stock('agotado',0)
assert h2.buscar_productos('termo acero inoxidable Original',cantidad=1)['resultados'][0]['product_id']=='alternativa'
assert h2.buscar_productos('termo acero inoxidable Ori-ginal',marca='Ori-ginal',cantidad=1)['resultados'][0]['product_id']=='alternativa'
assert [f['product_id'] for f in h2.buscar_productos('funda iphone 12 negro',cantidad=1)['resultados']]==['base12']
assert [f['product_id'] for f in h2.buscar_productos('altavoces bluetooth',cantidad=1,ordenar='precio')['resultados']]==['altavoz']

# Agregar un solo tipo no completa una solicitud explicita de dos productos.
s2.reiniciar();h2=s2.h
class BackendMulti:
    def __init__(self):self.salidas=iter([
        llamada('buscar_productos',consulta='altavoz bluetooth',cantidad=1),
        llamada('buscar_productos',consulta='funda iphone 12',cantidad=1),
        llamada('agregar_al_carrito',product_id='base12',cantidad=1),
        'Listo.',
        llamada('agregar_al_carrito',product_id='altavoz',cantidad=1),
        'Listo.'])
    def generar(self,mensajes,herramientas):return analizar_salida(next(self.salidas))
ag=Agente(BackendMulti(),h2)
ag.turno('Agrega un altavoz bluetooth y una funda para iPhone 12.')
assert {i['product_id'] for i in h2._carrito()['items']}=={'base12','altavoz'}
h2.estado.texto_usuario='Quita la funda y cotiza solo el altavoz.'
h2.cambiar_cantidad('base12',0)
assert not h2.ejecutar('agregar_al_carrito',{'product_id':'altavoz','cantidad':1})['ok']
assert h2._carrito()['items'][0]['cantidad']==1
print('REGRESION OK: parser seguro, filtros, presupuesto por cantidad, invalidacion y confirmacion real')
