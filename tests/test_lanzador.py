import json
import sys

import pytest

import actualizar
import lanzador


def con_parche(tmp_path, version, base=1, archivos=None):
    codigo = tmp_path / "codigo"
    codigo.mkdir()
    (codigo / "manifiesto.json").write_text(json.dumps({"version": version, "base": base}))
    for nombre, texto in (archivos or {"app.py": "def main(): pass"}).items():
        (codigo / nombre).write_text(texto)
    return tmp_path


@pytest.fixture(autouse=True)
def limpiar_importador():
    """Cada prueba deja sys.meta_path y sys.modules como los encontró."""
    antes = list(sys.meta_path)
    yield
    sys.meta_path[:] = antes
    sys.modules.pop("app", None)
    sys.modules.pop("modfalso", None)


def test_solo_se_usa_un_parche_mas_nuevo_y_compatible(tmp_path):
    assert lanzador.parche_utilizable(con_parche(tmp_path, "99.0")) is not None


@pytest.mark.parametrize("version,base", [("0.5", 1), (actualizar.VERSION, 1), ("99.0", 2)])
def test_ignora_parches_viejos_iguales_o_de_base_mayor(tmp_path, version, base):
    assert lanzador.parche_utilizable(con_parche(tmp_path, version, base)) is None


def test_ignora_parches_rotos_o_incompletos(tmp_path):
    assert lanzador.parche_utilizable(tmp_path) is None  # sin carpeta
    base = con_parche(tmp_path, "99.0")
    (base / "codigo" / "manifiesto.json").write_text("{roto")
    assert lanzador.parche_utilizable(base) is None


def test_un_parche_sin_app_py_no_sirve(tmp_path):
    assert lanzador.parche_utilizable(con_parche(tmp_path, "99.0", archivos={"nucleo.py": "x = 1"})) is None


def test_el_modulo_del_parche_gana_y_al_quitarlo_vuelve_el_original(tmp_path, monkeypatch):
    original = tmp_path / "original"
    original.mkdir()
    (original / "modfalso.py").write_text("ORIGEN = 'exe'")
    monkeypatch.syspath_prepend(str(original))
    programa = tmp_path / "programa"
    programa.mkdir()
    base = con_parche(programa, "99.0", archivos={"app.py": "def main(): pass", "modfalso.py": "ORIGEN = 'parche'"})

    assert lanzador.activar_parche(base) is not None
    import modfalso
    assert modfalso.ORIGEN == "parche"

    sys.meta_path.pop(0)
    sys.modules.pop("modfalso")
    import modfalso as otra_vez
    assert otra_vez.ORIGEN == "exe"


def test_un_parche_que_falla_al_arrancar_se_aparta_y_se_reabre_el_original(tmp_path, monkeypatch):
    base = con_parche(tmp_path, "99.0", archivos={"app.py": "def main():\n    raise RuntimeError('parche roto')"})
    abiertos = []
    monkeypatch.setattr(lanzador.subprocess, "Popen", lambda *a, **k: abiertos.append(a))
    monkeypatch.setattr(lanzador, "carpeta_del_programa", lambda: base)

    with pytest.raises(SystemExit) as salida:
        lanzador.main()

    assert salida.value.code == 1
    assert abiertos, "debía relanzar el programa"
    assert not (base / "codigo").exists() and (base / "codigo.fallido" / "app.py").exists()
    assert "parche roto" in (base / "asistente.log").read_text()
