import hashlib
import io
import json
import zipfile

import pytest

import actualizar as a
import empaquetar

GH = "https://github.com/x/y/releases/download/v9/"


class Respuesta:
    """Respuesta HTTP de mentira: sirve JSON (consultar) o bytes en trozos (descargas)."""

    def __init__(self, cuerpo):
        self.cuerpo = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
        self.headers = {"Content-Length": str(len(self.cuerpo))}

    def read(self, n=-1):
        if n < 0:
            n = len(self.cuerpo)
        trozo, self.cuerpo = self.cuerpo[:n], self.cuerpo[n:]
        return trozo

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


def activo(nombre, contenido=b"x", url=None, con_sha=True):
    d = {"name": nombre, "browser_download_url": url or GH + nombre}
    if con_sha:
        d["digest"] = "sha256:" + hashlib.sha256(contenido).hexdigest().upper()
    return d


def release(assets, tag="v9.0", **extra):
    return dict({"tag_name": tag, "html_url": "https://github.com/x/y/releases/tag/" + tag, "assets": assets}, **extra)


def consultar(datos):
    return a.consultar(lambda *_, **__: Respuesta(datos))


def test_comparacion_de_versiones():
    assert a.es_mas_nueva("v1.5") and a.es_mas_nueva("2.0.1")
    assert not a.es_mas_nueva(a.VERSION)
    assert not a.es_mas_nueva("basura")


def test_release_sin_archivos():
    r = consultar(release([]))
    assert r.version == "9.0" and r.descarga is None and r.codigo is None


def test_release_con_instalador_y_parche():
    r = consultar(release([activo("Instalar-Lynx.exe", b"i"), activo("codigo-base1.zip", b"c")]))
    assert r.descarga and r.sha256
    assert r.codigo.endswith("codigo-base1.zip") and r.codigo_sha and r.base == 1
    assert consultar(release([activo("codigo-base2.zip")])).base == 2


def test_no_confia_en_descargas_dudosas():
    # solo https de github, y siempre con suma de control
    assert consultar(release([activo("Instalar-Lynx.exe", url="http://malo.com/x.exe")])).descarga is None
    assert consultar(release([activo("Instalar-Lynx.exe", con_sha=False)])).descarga is None
    assert consultar(release([], html_url="http://malo.com")).enlace.startswith("https://github.com/")


@pytest.mark.parametrize("extra,tag", [({}, "v0.1"), ({"draft": True}, "v9.0"), ({"prerelease": True}, "v9.0")])
def test_ignora_releases_viejos_borradores_y_prerelease(extra, tag):
    assert consultar(release([], tag=tag, **extra)) is None


def test_sin_internet_no_falla():
    def sin_red(*_, **__):
        raise OSError("sin internet")

    assert a.consultar(sin_red) is None


# ---------- parches de código ----------
def zipear(archivos):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for nombre, contenido in archivos.items():
            z.writestr(nombre, contenido)
    return b.getvalue()


def info_de(datos, version=a.VERSION, base=1):
    return a.Nueva(version, GH, None, None, GH + "c.zip", hashlib.sha256(datos).hexdigest(), base)


@pytest.fixture
def programa(tmp_path):
    carpeta = tmp_path / "programa"
    carpeta.mkdir()
    return carpeta


def preparar(info, datos, programa):
    return a.preparar_parche(info, programa, abrir=lambda *_, **__: Respuesta(datos))


def test_parche_real_se_arma_se_descarga_y_se_activa(tmp_path, programa, monkeypatch):
    monkeypatch.setenv("TEMP", str(tmp_path))
    zip_real, huella, modulos = empaquetar.empaquetar(tmp_path)
    assert "nucleo.py" in modulos and "remoto.py" in modulos
    assert "lanzador.py" not in modulos and "empaquetar.py" not in modulos

    datos = zip_real.read_bytes()
    avance = []
    nuevo = a.preparar_parche(info_de(datos, base=1)._replace(codigo_sha=huella), programa, avance.append,
                              lambda *_, **__: Respuesta(datos))
    assert (nuevo / "app.py").exists() and (nuevo / "manifiesto.json").exists() and avance[-1] == 1.0

    (programa / "codigo").mkdir()
    (programa / "codigo" / "app.py").write_text("viejo")
    a.activar_parche(programa)
    assert (programa / "codigo" / "manifiesto.json").exists()
    assert (programa / "codigo.anterior" / "app.py").read_text() == "viejo"
    assert not (programa / "codigo.nuevo").exists()


MANIFIESTO = json.dumps({"version": a.VERSION, "base": 1})


@pytest.mark.parametrize("archivos,fragmento", [
    ({"manifiesto.json": MANIFIESTO, "../evil.py": "x = 1"}, "inesperado"),
    ({"manifiesto.json": MANIFIESTO, "sub/evil.py": "x = 1"}, "inesperado"),
    ({"manifiesto.json": MANIFIESTO, "programa.exe": "MZ"}, "inesperado"),
    ({"manifiesto.json": json.dumps({"version": a.VERSION, "base": 5}), "app.py": "x=1"}, "base"),
])
def test_rechaza_parches_peligrosos(programa, archivos, fragmento):
    datos = zipear(archivos)
    with pytest.raises((RuntimeError, SyntaxError, KeyError, ValueError)) as e:
        preparar(info_de(datos), datos, programa)
    assert fragmento in str(e.value)
    assert not (programa / "codigo.nuevo").exists(), "no debe quedar nada a medio instalar"


def test_rechaza_parche_con_suma_de_control_incorrecta(programa):
    datos = zipear({"manifiesto.json": MANIFIESTO, "app.py": "x=1"})
    with pytest.raises(RuntimeError, match="no coincide"):
        preparar(info_de(b"otra cosa"), datos, programa)


def test_rechaza_parche_con_version_distinta_a_la_del_release(programa):
    datos = zipear({"manifiesto.json": MANIFIESTO, "app.py": "x=1"})
    with pytest.raises(RuntimeError, match="no coincide"):
        preparar(info_de(datos, version="9.9"), datos, programa)


def test_rechaza_parche_con_codigo_roto_o_sin_manifiesto(programa):
    roto = zipear({"manifiesto.json": MANIFIESTO, "app.py": "def (:"})
    with pytest.raises((RuntimeError, SyntaxError)):
        preparar(info_de(roto), roto, programa)
    sin = zipear({"app.py": "x=1"})
    with pytest.raises(RuntimeError):
        preparar(info_de(sin), sin, programa)


def test_fuera_del_exe_instalado_no_se_aplican_parches():
    assert not a.puede_aplicar_parche(info_de(b"x"))
