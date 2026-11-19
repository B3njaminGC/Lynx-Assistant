"""Cómo se interpretan las órdenes de voz sobre pendientes."""
from datetime import datetime

import pytest

from pendientes_voz import Orden, interpretar

AHORA = datetime(2026, 11, 19, 15, 0)


def orden(texto):
    return interpretar(texto, AHORA)


@pytest.mark.parametrize("dicho,accion,texto", [
    ("terminé comprar pan", "terminar", "comprar pan"),
    ("termine comprar pan", "terminar", "comprar pan"),
    ("ya hice llamar al médico", "terminar", "llamar al medico"),
    ("terminé el dos", "terminar", "el dos"),
    ("terminé", "terminar", ""),
    ("marca como hecho comprar pan", "terminar", "comprar pan"),
    ("agregá pendiente comprar pan", "agregar", "comprar pan"),
    ("agrega pendiente llamar al médico", "agregar", "llamar al medico"),
    ("anotá un pendiente de pagar la luz", "agregar", "pagar la luz"),
    ("agregá pendiente", "agregar", ""),
    ("borrá pendiente comprar pan", "borrar", "comprar pan"),
    ("eliminá el pendiente dos", "borrar", "dos"),
    ("qué tengo pendiente", "listar", ""),
    ("qué pendientes tengo", "listar", ""),
    ("leeme mis pendientes", "listar", ""),
    ("cuáles son mis pendientes", "listar", ""),
])
def test_acciones_y_texto(dicho, accion, texto):
    assert orden(dicho) == Orden(accion, texto, None)


@pytest.mark.parametrize("dicho", ["abrí youtube", "subí el volumen", "hola", "", "apagá la pc", "pendiente"])
def test_lo_que_no_es_de_pendientes_se_ignora(dicho):
    assert orden(dicho) is None


def test_ignora_por_favor_y_el_nombre_al_principio():
    assert orden("por favor terminé comprar pan").texto == "comprar pan"
    assert orden("lynx terminé comprar pan").accion == "terminar"


@pytest.mark.parametrize("dicho,texto,hasta", [
    ("posponé comprar pan una hora", "comprar pan", datetime(2026, 11, 19, 16, 0)),
    ("posponé comprar pan media hora", "comprar pan", datetime(2026, 11, 19, 15, 30)),
    ("posponé comprar pan dos horas", "comprar pan", datetime(2026, 11, 19, 17, 0)),
    ("posponé comprar pan una hora y media", "comprar pan", datetime(2026, 11, 19, 16, 30)),
    ("posponé comprar pan por treinta y cinco minutos", "comprar pan", datetime(2026, 11, 19, 15, 35)),
    ("posponé comprar pan quince minutos", "comprar pan", datetime(2026, 11, 19, 15, 15)),
    ("posponé comprar pan 20 minutos", "comprar pan", datetime(2026, 11, 19, 15, 20)),
    ("posponé pagar la luz mañana", "pagar la luz", datetime(2026, 11, 20, 9, 0)),
])
def test_posponer_con_tiempo(dicho, texto, hasta):
    assert orden(dicho) == Orden("posponer", texto, hasta)


def test_posponer_sin_decir_cuanto_deja_el_tiempo_vacio():
    assert orden("posponé comprar pan") == Orden("posponer", "comprar pan", None)
