"""Pruebas de los gestos de mano: con manos dibujadas a mano (sin cámara ni MediaPipe)."""

import gestos


def mano(estirados=(True, True, True, True), x=0.5, y=0.6):
    """21 puntos de una mano con la muñeca abajo y los dedos hacia arriba. `estirados` = índice, medio, anular, meñique."""
    p = [(x, y)] * 21
    p = list(p)
    p[gestos.MUNECA] = (x, y)
    p[9] = (x, y - 0.15)    # base del dedo medio (el centro de la palma)
    for (articulacion, punta), abierto in zip(gestos.DEDOS, estirados):
        p[articulacion] = (x, y - 0.25)
        p[punta] = (x, y - 0.38) if abierto else (x, y - 0.12)   # cerrado: la punta vuelve hacia la palma
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
    seguido = [(1.8 + i * 0.1, mano(x=0.4 + i * 0.1)) for i in range(5)]   # otro enseguida: dentro del enfriamiento
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
        assert set(perfil) == set(gestos.GESTOS)
        for valor in perfil.values():
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
