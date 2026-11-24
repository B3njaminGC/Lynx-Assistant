"""Pruebas de los gestos de mano: con manos dibujadas a mano (sin cámara ni MediaPipe)."""

import gestos


def mano(estirados=(True, True, True, True), x=0.5, y=0.6, tam=1.0):
    """21 puntos de una mano con la muñeca abajo y los dedos hacia arriba. `estirados` = índice, medio, anular, meñique.
    `tam` achica o agranda la mano (una mano lejos de la cámara se ve más chica)."""
    p = [(x, y)] * 21
    p = list(p)
    p[gestos.MUNECA] = (x, y)
    p[9] = (x, y - 0.15 * tam)    # base del dedo medio (el centro de la palma)
    for (articulacion, punta), abierto in zip(gestos.DEDOS, estirados):
        p[articulacion] = (x, y - 0.25 * tam)
        p[punta] = (x, y - 0.38 * tam) if abierto else (x, y - 0.12 * tam)   # cerrado: la punta vuelve hacia la palma
    return p


PALMA, PUNO = mano(), mano((False,) * 4)


def correr(reconocedor, pasos):
    """pasos = [(tiempo, puntos)]. Devuelve [(tiempo, evento)]."""
    salida = []
    for t, puntos in pasos:
        salida += [(t, e) for e in reconocedor.paso(puntos, t)]
    return salida


def palma_quieta(desde, hasta, paso=0.1, x=0.5):
    n = int(round((hasta - desde) / paso))
    return [(round(desde + i * paso, 2), mano(x=x)) for i in range(n + 1)]


def activado(r=None):
    r = r or gestos.Reconocedor()
    assert [e for _, e in correr(r, palma_quieta(0, 1.2))] == ["activado"]
    return r


# ---------------------------------------------------------------- clasificar

def test_clasifica_palma_puno_y_otro():
    assert gestos.clasificar_mano(PALMA) == "palma"
    assert gestos.clasificar_mano(PUNO) == "puño"
    assert gestos.clasificar_mano(mano((True, True, False, False))) == "otro"
    assert gestos.clasificar_mano(None) is None
    assert gestos.clasificar_mano([(0, 0)] * 5) is None


def test_clasifica_aunque_la_mano_este_girada_de_lado():
    # misma mano pero apuntando hacia la derecha: las distancias no cambian
    girada = [(1 - y, x) for x, y in PALMA]
    assert gestos.clasificar_mano(girada) == "palma"


# ---------------------------------------------------------------- activar

def test_la_palma_quieta_un_segundo_activa():
    r = gestos.Reconocedor()
    assert correr(r, palma_quieta(0, 0.8)) == []
    assert r.armado is False
    assert [e for _, e in correr(r, palma_quieta(0.9, 1.2))] == ["activado"]
    assert r.armado


def test_una_palma_que_se_mueve_no_activa():
    r = gestos.Reconocedor()
    pasos = [(i * 0.1, mano(x=0.2 + i * 0.03)) for i in range(25)]   # se mueve todo el tiempo
    assert correr(r, pasos) == []


def test_un_puno_o_perder_la_mano_reinicia_la_cuenta():
    r = gestos.Reconocedor()
    correr(r, palma_quieta(0, 0.8))
    r.paso(None, 0.9)               # se fue la mano
    assert correr(r, palma_quieta(1.0, 1.6)) == []   # no alcanza: cuenta desde cero


def test_sin_activar_no_hay_gestos():
    r = gestos.Reconocedor()
    desliz = [(i * 0.1, mano(x=0.2 + i * 0.1)) for i in range(6)]
    assert correr(r, desliz) == []
    assert correr(r, [(2.0 + i * 0.1, PUNO) for i in range(10)]) == []


# ---------------------------------------------------------------- deslizar y puño

def test_deslizar_a_la_derecha_y_a_la_izquierda():
    r = activado()
    der = [(1.3 + i * 0.1, mano(x=0.5 + 0.1 * (i + 1))) for i in range(5)]   # sigue desde donde estaba la palma
    assert [e for _, e in correr(r, der)] == ["deslizar_der"]
    izq = [(3.0 + i * 0.1, mano(x=0.9 - i * 0.1)) for i in range(5)]
    assert [e for _, e in correr(r, izq)] == ["deslizar_izq"]


def test_un_movimiento_corto_o_en_diagonal_no_cuenta():
    r = activado()
    corto = [(1.3 + i * 0.1, mano(x=0.5 + i * 0.03)) for i in range(5)]
    assert correr(r, corto) == []
    diagonal = [(2.0 + i * 0.1, mano(x=0.3 + i * 0.1, y=0.3 + i * 0.1)) for i in range(5)]
    assert correr(r, diagonal) == []


def test_el_puno_dispara_una_sola_vez():
    r = activado()
    pasos = [(1.3 + i * 0.1, PUNO) for i in range(12)]
    assert [e for _, e in correr(r, pasos)] == ["puño"]
    # abre y vuelve a cerrar: otra vez
    pasos = [(3.0, PALMA)] + [(3.1 + i * 0.1, PUNO) for i in range(8)]
    assert [e for _, e in correr(r, pasos)] == ["puño"]


def test_un_puno_demasiado_corto_no_cuenta():
    r = activado()
    assert correr(r, [(1.3, PUNO), (1.4, PUNO), (1.5, PALMA)]) == []


def test_se_desactiva_solo_y_hay_que_volver_a_activar():
    r = gestos.Reconocedor(segundos_atento=3)
    activado(r)
    eventos = correr(r, [(5.0, PALMA)])      # pasaron más de 3 s desde la activación
    assert [e for _, e in eventos] == ["desactivado"] and not r.armado
    assert correr(r, [(5.1 + i * 0.1, mano(x=0.2 + i * 0.1)) for i in range(6)]) == []


def test_cada_gesto_mantiene_atento_un_rato_mas():
    r = gestos.Reconocedor(segundos_atento=3)
    activado(r)
    correr(r, [(2.5 + i * 0.1, mano(x=0.3 + i * 0.1)) for i in range(5)])   # gesto a los ~2.9 s
    assert r.armado
    assert r.segundos_atento_restantes(3.0) > 2.5


def test_enfriamiento_entre_gestos():
    r = activado()
    der = [(1.3 + i * 0.1, mano(x=0.5 + 0.1 * (i + 1))) for i in range(5)]
    seguido = [(1.6 + i * 0.1, mano(x=0.4 + i * 0.1)) for i in range(5)]   # otro enseguida: dentro del enfriamiento
    eventos = [e for _, e in correr(r, der + seguido)]
    assert eventos.count("deslizar_der") == 1


# ---------------------------------------------------------------- qué hace cada gesto

def test_perfil_por_aplicacion_y_perfil_general():
    assert gestos.valor_de_gesto("deslizar_der", "chrome.exe") == "pestana_siguiente"
    assert gestos.valor_de_gesto("deslizar_der", "Spotify.exe") == "media:siguiente"
    assert gestos.valor_de_gesto("deslizar_izq", "POWERPNT.EXE") == "teclas:izquierda"
    assert gestos.valor_de_gesto("deslizar_der", "bloc.exe") == "cambiar_ventana"   # app sin perfil: escritorio
    assert gestos.valor_de_gesto("puño", "") == "mostrar_escritorio"


def test_tus_cambios_en_la_config_ganan():
    config = {"gestos": {"general": {"puño": "bloquear"},
                         "apps": {"Chrome.exe": {"deslizar_der": "teclas:ctrl+r"}}}}
    assert gestos.valor_de_gesto("deslizar_der", "chrome.exe", config) == "teclas:ctrl+r"
    assert gestos.valor_de_gesto("deslizar_izq", "chrome.exe", config) == "pestana_anterior"  # lo demás sigue igual
    assert gestos.valor_de_gesto("puño", "bloc.exe", config) == "bloquear"
    assert gestos.valor_de_gesto("deslizar_der", "bloc.exe", {"gestos": "roto"}) == "cambiar_ventana"


def test_todos_los_valores_por_defecto_existen():
    import acciones_pc
    import teclas
    perfiles = [gestos.PERFIL_GENERAL, *gestos.PERFILES_POR_APP.values()]
    for perfil in perfiles:
        assert set(perfil) <= set(gestos.GESTOS)
        for valor in perfil.values():
            if valor == "selector:abrir":
                continue
            if valor.startswith("teclas:"):
                teclas.analizar(valor[len("teclas:"):])
            elif valor.startswith("media:"):
                import nucleo
                assert valor[len("media:"):] in nucleo.TECLAS_MULTIMEDIA
            else:
                assert valor in acciones_pc.POR_CLAVE


def test_ejecutar_valor():
    hecho = []
    args = dict(acciones_pc_ejecutar=lambda c: hecho.append(("accion", c)), claves_de_acciones={"cambiar_ventana"},
                pulsar=lambda t: hecho.append(("teclas", t)), multimedia=lambda n: hecho.append(("media", n)))
    assert gestos.ejecutar_valor("cambiar_ventana", **args)
    assert gestos.ejecutar_valor("teclas:ctrl+tab", **args)
    assert gestos.ejecutar_valor("media:pausa", **args)
    assert not gestos.ejecutar_valor("", **args)
    assert not gestos.ejecutar_valor("cosa_rara", **args)
    assert hecho == [("accion", "cambiar_ventana"), ("teclas", "ctrl+tab"), ("media", "pausa")]


def test_sin_mediapipe_no_rompe_y_dice_por_que(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "mediapipe", None)   # como si no estuviera instalado
    monkeypatch.setattr(gestos, "MOTIVO_FALLA", "")
    assert gestos.mediapipe_disponible() is False
    assert gestos.detector_por_defecto() is None
    assert "mediapipe" in gestos.MOTIVO_FALLA.lower() or "import" in gestos.MOTIVO_FALLA.lower()


# ---------------------------------------------------------------- el modelo de manos y MediaPipe (con uno de juguete)

def test_asegurar_modelo_baja_una_sola_vez(tmp_path):
    ruta = str(tmp_path / "modelo.task")
    llamadas = []

    def bajar(url, destino):
        llamadas.append(url)
        with open(destino, "wb") as f:
            f.write(b"x" * 2_000_000)
    assert gestos.asegurar_modelo(ruta, bajar) == ruta
    assert gestos.asegurar_modelo(ruta, bajar) == ruta
    assert llamadas == [gestos.URL_MODELO]
    assert not (tmp_path / "modelo.task.descarga").exists()


def test_asegurar_modelo_si_falla_dice_que_hacer(tmp_path):
    import pytest
    ruta = str(tmp_path / "modelo.task")

    def bajar(url, destino):
        raise OSError("sin internet")
    with pytest.raises(OSError) as error:
        gestos.asegurar_modelo(ruta, bajar)
    assert "sin internet" in str(error.value) and gestos.URL_MODELO in str(error.value)
    assert not (tmp_path / "modelo.task").exists()


def test_detector_con_la_interfaz_nueva_de_mediapipe(monkeypatch, tmp_path):
    import sys
    import types
    import numpy as np
    vistos = []

    class Punto:
        def __init__(self, x, y):
            self.x, self.y = x, y

    class Marcador:
        def detect_for_video(self, imagen, ms):
            vistos.append(ms)
            hay = len(vistos) != 3     # en la tercera llamada no se ve ninguna mano
            return types.SimpleNamespace(hand_landmarks=[[Punto(i / 21, 0.5) for i in range(21)]] if hay else [])

        def close(self):
            vistos.append("cerrado")

    vision = types.SimpleNamespace(
        HandLandmarkerOptions=lambda **kw: kw, RunningMode=types.SimpleNamespace(VIDEO="video"),
        HandLandmarker=types.SimpleNamespace(create_from_options=lambda opciones: Marcador()))
    falso = types.SimpleNamespace(
        tasks=types.SimpleNamespace(vision=vision, BaseOptions=lambda **kw: kw),
        Image=lambda image_format, data: data, ImageFormat=types.SimpleNamespace(SRGB=1))
    monkeypatch.setitem(sys.modules, "mediapipe", falso)
    modelo = tmp_path / "m.task"
    modelo.write_bytes(b"x" * 2_000_000)
    d = gestos.DetectorDeManos(str(modelo))
    rgb = np.zeros((240, 320, 3), dtype=np.uint8)
    puntos = d.buscar(rgb)
    assert len(puntos) == 21 and puntos[0] == (0.0, 0.5, 0.0)
    d.buscar(rgb)
    assert d.buscar(rgb) is None
    assert vistos[0] < vistos[1] < vistos[2]       # las marcas de tiempo siempre crecen
    d.cerrar()
    assert vistos[-1] == "cerrado"


def test_deslizar_cuenta_aunque_la_mano_salga_borrosa():
    r = activado()
    pasos = []
    for i in range(5):
        puntos = mano(x=0.5 + 0.1 * (i + 1))
        if i == 2:
            puntos = mano((True, True, False, True), x=0.5 + 0.1 * (i + 1))   # un cuadro mal reconocido
        pasos.append((1.3 + i * 0.1, puntos))
    assert [e for _, e in correr(r, pasos)] == ["deslizar_der"]


def test_un_deslizar_lento_no_cuenta():
    r = activado()
    lento = [(1.3 + i * 0.25, mano(x=0.5 + 0.03 * i)) for i in range(10)]   # 0.27 de recorrido en 2 s
    assert correr(r, lento) == []


def test_un_giro_de_muñeca_de_cerca_o_una_mano_lejana_tambien_cuentan():
    r = activado()
    # mano chica (lejos): el recorrido necesario se achica con ella
    lejos = [(1.3 + i * 0.1, mano(x=0.5 + 0.03 * (i + 1), tam=0.4)) for i in range(6)]
    assert [e for _, e in correr(r, lejos)] == ["deslizar_der"]
    r2 = activado()
    # la misma distancia con una mano grande (cerca) no alcanza: se mueve poco comparado con su tamaño
    cerca = [(1.3 + i * 0.1, mano(x=0.5 + 0.03 * (i + 1), tam=1.6)) for i in range(6)]
    assert correr(r2, cerca) == []


def test_deslizar_hacia_arriba_y_hacia_abajo():
    r = activado()
    arriba = [(1.3 + i * 0.1, mano(y=0.7 - 0.07 * (i + 1))) for i in range(5)]
    assert [e for _, e in correr(r, arriba)] == ["deslizar_arriba"]
    abajo = [(3.0 + i * 0.1, mano(y=0.3 + 0.07 * i)) for i in range(5)]
    assert [e for _, e in correr(r, abajo)] == ["deslizar_abajo"]


def test_un_movimiento_en_diagonal_no_es_ni_vertical_ni_horizontal():
    r = activado()
    diagonal = [(1.3 + i * 0.1, mano(x=0.5 + 0.08 * (i + 1), y=0.6 + 0.08 * (i + 1))) for i in range(5)]
    assert correr(r, diagonal) == []


# ---------------------------------------------------------------- el selector de aplicaciones

def test_selector_de_apps_como_las_recientes_del_celular():
    t = gestos.Traductor()
    assert t.valor("deslizar_arriba", "chrome.exe") == "teclas:win+tab"      # sirve en cualquier app
    assert t.selector_abierto
    assert t.valor("deslizar_der", "chrome.exe") == "teclas:derecha"         # ya no cambia de pestaña
    assert t.valor("deslizar_izq", "chrome.exe") == "teclas:izquierda"
    assert t.valor("deslizar_abajo", "chrome.exe") == "teclas:abajo"
    assert t.valor("puño", "chrome.exe") == "teclas:enter"                   # abre la marcada
    assert not t.selector_abierto
    assert t.valor("deslizar_der", "chrome.exe") == "pestana_siguiente"      # todo vuelve a la normalidad


def test_selector_se_cierra_solo_si_no_se_toca_nada():
    t = gestos.Traductor()
    t.valor("deslizar_arriba", "")
    assert t.valor("desactivado", "") == "teclas:esc" and not t.selector_abierto
    assert t.valor("desactivado", "") == ""    # sin selector abierto, no aprieta nada


def test_se_puede_cambiar_el_gesto_que_abre_el_selector():
    t = gestos.Traductor()
    config = {"gestos": {"general": {"deslizar_arriba": "mostrar_escritorio"}}}
    assert t.valor("deslizar_arriba", "bloc.exe", config) == "mostrar_escritorio"
    assert not t.selector_abierto


def test_reiniciar_cierra_el_modo_selector():
    t = gestos.Traductor()
    t.valor("deslizar_arriba", "")
    t.reiniciar()
    assert not t.selector_abierto


# ---------------------------------------------------------------- la mano que vuelve, sale o entra

def test_la_mano_que_vuelve_no_es_otro_gesto():
    r = activado()
    ida = [(1.3 + i * 0.1, mano(x=0.5 + 0.1 * (i + 1))) for i in range(3)]
    assert [e for _, e in correr(r, ida)] == ["deslizar_der"]
    vuelta = [(1.7 + i * 0.1, mano(x=0.85 - 0.1 * i)) for i in range(6)]   # vuelve para el otro lado, enseguida
    assert correr(r, vuelta) == []
    # mucho después, un deslizar a la izquierda sí vale
    despues = [(4.0 + i * 0.1, mano(x=0.8 - 0.1 * i)) for i in range(5)]
    assert [e for _, e in correr(r, despues)] == ["deslizar_izq"]


def test_subir_el_brazo_y_salir_por_arriba_cuenta_como_deslizar_arriba():
    r = activado()
    # mano grande (cerca): el recorrido normal no llega, pero se va por el borde de arriba yendo hacia arriba
    subida = [(1.3 + i * 0.1, mano(y=0.78 - 0.05 * i, tam=2.0)) for i in range(6)]
    assert correr(r, subida) == []
    assert [e for _, e in correr(r, [(1.9, None)])] == ["deslizar_arriba"]


def test_perder_la_mano_en_el_medio_de_la_imagen_no_cuenta():
    r = activado()
    subida = [(1.3 + i * 0.1, mano(y=0.9 - 0.04 * i, tam=2.0)) for i in range(5)]
    correr(r, subida)
    assert correr(r, [(1.9, None)]) == []


def test_una_mano_que_recien_entra_a_la_imagen_no_hace_gestos():
    r = activado()
    r.paso(None, 1.3)                                                # salió de la imagen
    entra = [(1.5 + i * 0.1, mano(y=0.3 + 0.07 * i)) for i in range(5)]   # baja entrando por arriba
    assert correr(r, entra) == []


# ---------------------------------------------------------------- manos de verdad: de frente, en movimiento

def test_una_mano_abierta_con_los_dedos_hacia_la_camara_no_es_un_puño():
    # los dedos apuntan a la cámara: en la imagen las puntas casi no se alejan de la muñeca, pero la profundidad (z) sí
    p = mano()
    for articulacion, punta in gestos.DEDOS:
        p[articulacion] = (p[articulacion][0], p[gestos.MUNECA][1] - 0.10, -0.12)
        p[punta] = (p[punta][0], p[gestos.MUNECA][1] - 0.11, -0.28)
    assert gestos.clasificar_mano(p) == "palma"


def test_dedos_a_medio_doblar_no_son_puño_ni_palma():
    p = mano()
    for articulacion, punta in gestos.DEDOS:
        p[punta] = (p[punta][0], p[gestos.MUNECA][1] - 0.25)   # la punta a la misma distancia que la articulación
    assert gestos.clasificar_mano(p) == "otro"


def test_un_puno_mientras_la_mano_se_mueve_no_dispara():
    r = activado()
    en_movimiento = [(1.3 + i * 0.1, mano((False,) * 4, x=0.3 + 0.05 * i)) for i in range(12)]
    assert [e for _, e in correr(r, en_movimiento) if e == "puño"] == []


def test_un_cuadro_que_parece_puño_no_corta_un_deslizar():
    r = activado()
    pasos = []
    for i in range(5):
        puntos = mano(x=0.5 + 0.1 * (i + 1))
        if i == 1:
            puntos = mano((False,) * 4, x=0.5 + 0.1 * (i + 1))   # un cuadro borroso que parece puño
        pasos.append((1.3 + i * 0.1, puntos))
    assert [e for _, e in correr(r, pasos)] == ["deslizar_der"]


def test_con_poca_velocidad_de_camara_alcanzan_dos_cuadros_si_el_movimiento_es_grande():
    r = activado()
    pasos = [(1.3, mano(x=0.5)), (1.65, mano(x=0.5 + 0.30))]   # cámara lenta: solo dos cuadros
    assert [e for _, e in correr(r, pasos)] == ["deslizar_der"]
