import json
import zipfile

import pytest

import nucleo
import respaldo

COMANDOS = [
    {"frase": "abrí obs", "tipo": "abrir_programa", "valor": "obs"},
    {"frase": "a dibujar", "tipo": "abrir_programa", "valor": "x"},
]


@pytest.fixture
def datos(tmp_path, monkeypatch):
    """Una instalación de mentira: comandos y ajustes (con un token secreto) en una carpeta temporal."""
    monkeypatch.setattr(nucleo, "BASE", tmp_path)
    monkeypatch.setattr(nucleo, "ARCHIVO_COMANDOS", tmp_path / "comandos.json")
    monkeypatch.setattr(nucleo, "ARCHIVO_CONFIG", tmp_path / "config.json")
    monkeypatch.setattr(respaldo, "CARPETA_RESPALDOS", tmp_path / "respaldos")
    config = dict(nucleo.CONFIG_BASE, personaje="Taeyai", telegram_token="SECRETO:123", telegram_usuario=42)
    nucleo.guardar_comandos(COMANDOS)
    nucleo.guardar_config(config)
    return tmp_path, config


def test_exportar_no_incluye_el_token(datos):
    tmp, _ = datos
    destino = tmp / "r.zip"
    assert respaldo.exportar(destino) == 2
    with zipfile.ZipFile(destino) as z:
        assert "SECRETO" not in z.read("config.json").decode()
        assert "abrí obs" in z.read("comandos.json").decode()
    comandos, config = respaldo.leer_respaldo(destino)
    assert comandos == COMANDOS and config["personaje"] == "Taeyai"


def test_restaurar_guarda_antes_lo_que_habia_y_conserva_el_token_actual(datos):
    tmp, config = datos
    destino = tmp / "r.zip"
    respaldo.exportar(destino)
    nucleo.guardar_comandos([{"frase": "otra cosa", "tipo": "abrir_programa", "valor": "y"}])

    actual = dict(config, personaje=None, telegram_token="TOKEN-NUEVO")
    cantidad, nueva = respaldo.restaurar(destino, actual)

    assert cantidad == 2
    assert json.loads(nucleo.ARCHIVO_COMANDOS.read_text(encoding="utf-8")) == COMANDOS
    assert nueva["personaje"] == "Taeyai" and nueva["telegram_token"] == "TOKEN-NUEVO"
    copias = list(respaldo.CARPETA_RESPALDOS.glob("respaldo-*-antes-de-restaurar.zip"))
    assert len(copias) == 1
    with zipfile.ZipFile(copias[0]) as z:
        assert "otra cosa" in z.read("comandos.json").decode()


@pytest.mark.parametrize("contenido", [b"no es un zip", b""])
def test_rechaza_archivos_que_no_son_un_respaldo(datos, contenido):
    tmp, _ = datos
    malo = tmp / "malo.zip"
    malo.write_bytes(contenido)
    with pytest.raises(respaldo.ErrorRespaldo):
        respaldo.leer_respaldo(malo)
