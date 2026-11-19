"""El archivo de pendientes y la búsqueda del más parecido."""
import json
from datetime import datetime, timedelta

import pytest

import pendientes
from pendientes import Pendientes

AHORA = datetime(2026, 11, 19, 15, 0, 0)


@pytest.fixture
def lista(tmp_path):
    return Pendientes(tmp_path / "pendientes.json", ahora=lambda: AHORA)


def con(lista, *textos):
    for texto in textos:
        lista.agregar(texto)
    return lista


# ---------------------------------------------------------------- archivo
def test_sin_archivo_empieza_vacia(lista):
    assert lista.items == [] and lista.para_leer() == []


def test_lo_que_se_agrega_queda_guardado_y_se_vuelve_a_leer(lista, tmp_path):
    con(lista, "comprar pan", "llamar al médico")
    otra = Pendientes(tmp_path / "pendientes.json", ahora=lambda: AHORA)
    assert [i["texto"] for i in otra.para_leer()] == ["comprar pan", "llamar al médico"]


def test_los_ids_no_se_repiten_aunque_se_borre(lista):
    con(lista, "uno", "dos")
    lista.borrar(2)
    nuevo, _ = lista.agregar("tres")
    assert nuevo["id"] == 3


def test_no_repite_un_pendiente_igual(lista):
    primero, nuevo1 = lista.agregar("Comprar pan")
    segundo, nuevo2 = lista.agregar("comprar  PAN")
    assert nuevo1 and not nuevo2 and segundo["id"] == primero["id"] and len(lista.items) == 1


def test_no_acepta_un_pendiente_vacio(lista):
    with pytest.raises(ValueError):
        lista.agregar("   ")


def test_un_archivo_roto_se_aparta_y_no_se_pierde(tmp_path):
    ruta = tmp_path / "pendientes.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    avisos = []
    lista = Pendientes(ruta, ahora=lambda: AHORA, avisar=lambda *a: avisos.append(a))
    assert lista.items == [] and avisos
    apartados = list(tmp_path.glob("pendientes.roto-*.json"))
    assert len(apartados) == 1 and apartados[0].read_text(encoding="utf-8") == "{esto no es json"


def test_un_pendiente_sin_texto_tambien_cuenta_como_archivo_roto(tmp_path):
    ruta = tmp_path / "pendientes.json"
    ruta.write_text(json.dumps({"pendientes": [{"id": 1, "texto": ""}]}), encoding="utf-8")
    assert Pendientes(ruta).items == [] and list(tmp_path.glob("pendientes.roto-*.json"))


def test_guardar_no_deja_archivos_temporales(lista, tmp_path):
    con(lista, "comprar pan")
    assert [p.name for p in tmp_path.iterdir()] == ["pendientes.json"]


# ---------------------------------------------------------------- estados
def test_marcar_hecho_lo_saca_de_lo_que_se_lee(lista):
    con(lista, "comprar pan", "pagar la luz")
    lista.marcar_hecho(1)
    assert [i["texto"] for i in lista.para_leer()] == ["pagar la luz"]
    assert lista.por_id(1)["hecho_en"] == AHORA.isoformat(timespec="seconds")


def test_un_pospuesto_no_se_lee_hasta_que_pasa_la_hora(tmp_path):
    reloj = {"ahora": AHORA}
    lista = Pendientes(tmp_path / "p.json", ahora=lambda: reloj["ahora"])
    con(lista, "comprar pan")
    lista.posponer(1, AHORA + timedelta(hours=1))
    assert lista.para_leer() == [] and len(lista.abiertos()) == 1
    reloj["ahora"] = AHORA + timedelta(hours=1, minutes=1)
    assert len(lista.para_leer()) == 1


def test_los_hechos_viejos_se_limpian_y_los_recientes_no(tmp_path):
    reloj = {"ahora": AHORA}
    lista = Pendientes(tmp_path / "p.json", ahora=lambda: reloj["ahora"])
    con(lista, "viejo", "reciente", "abierto")
    lista.marcar_hecho(1)
    reloj["ahora"] = AHORA + timedelta(days=20)
    lista.marcar_hecho(2)
    reloj["ahora"] = AHORA + timedelta(days=40)
    assert lista.limpiar_hechos_viejos() == 1
    assert sorted(i["texto"] for i in lista.items) == ["abierto", "reciente"]


# ---------------------------------------------------------------- búsqueda
def test_encuentra_el_pendiente_aunque_digas_menos_palabras(lista):
    con(lista, "comprar pan y leche", "pagar la luz")
    eleccion = lista.elegir("comprar pan")
    assert eleccion.tipo == "uno" and eleccion.items[0]["texto"] == "comprar pan y leche"


def test_tolera_una_palabra_mal_reconocida(lista):
    con(lista, "comprar pan", "pagar la luz")
    assert lista.elegir("comprar pa").items[0]["texto"] == "comprar pan"


def test_si_podrian_ser_varios_pregunta(lista):
    con(lista, "comprar pan", "pan para el cumple", "pagar la luz")
    eleccion = lista.elegir("pan")
    assert eleccion.tipo == "dudas" and len(eleccion.items) == 2


def test_si_no_se_parece_a_nada_dice_ninguno(lista):
    con(lista, "comprar pan", "pagar la luz")
    assert lista.elegir("sacar al perro").tipo == "ninguno"


def test_no_busca_entre_los_hechos(lista):
    con(lista, "comprar pan")
    lista.marcar_hecho(1)
    assert lista.elegir("comprar pan").tipo == "ninguno"


def test_por_numero_usa_la_lista_como_se_leyo(lista):
    con(lista, "uno", "dos", "tres")
    leida = lista.para_leer()
    assert lista.elegir("el dos", leida).items[0]["texto"] == "dos"
    assert lista.elegir("tercero", leida).items[0]["texto"] == "tres"
    assert lista.elegir("numero 2", leida).items[0]["texto"] == "dos"
    assert lista.elegir("el siete", leida).tipo == "ninguno"


@pytest.mark.parametrize("texto,esperado", [("el dos", 2), ("2", 2), ("segundo", 2), ("número tres", 3),
                                            ("comprar pan", None), ("dos panes", None), ("", None)])
def test_numero_de(texto, esperado):
    assert pendientes.numero_de(texto) == esperado


def test_normalizar():
    assert pendientes.normalizar("¿Comprar PAN, mañana?") == "comprar pan manana"


def test_el_contador_de_ids_sobrevive_al_reinicio(lista, tmp_path):
    con(lista, "uno", "dos")
    lista.borrar(2)
    otra = Pendientes(tmp_path / "pendientes.json", ahora=lambda: AHORA)
    assert otra.agregar("tres")[0]["id"] == 3
