"""Pruebas de la lista de apps instaladas (con la respuesta de PowerShell simulada)."""
import json
from types import SimpleNamespace

import apps_instaladas

JSON = json.dumps([
    {"Name": "Spotify", "AppID": "Spotify.exe"},
    {"Name": "Brave", "AppID": "{6D809377}\\BraveSoftware\\brave.exe"},
    {"Name": "Cámara", "AppID": "Microsoft.WindowsCamera_8wekyb3d8bbwe!App"},
    {"Name": "Spotify", "AppID": "Spotify.exe"},          # repetida
    {"Name": "", "AppID": "x"},                            # sin nombre
])


def falso(texto, codigo=0):
    return lambda args: SimpleNamespace(returncode=codigo, stdout=texto.encode("utf-8"))


def test_lista_ordenada_sin_repetidos_y_con_destino():
    apps = apps_instaladas.leer(falso(JSON))
    assert [a[0] for a in apps] == ["Brave", "Cámara", "Spotify"]
    assert apps[2][1] == "shell:AppsFolder\\Spotify.exe"


def test_con_una_sola_app_powershell_devuelve_un_objeto():
    apps = apps_instaladas.leer(falso(json.dumps({"Name": "OBS", "AppID": "obs"})))
    assert apps == [("OBS", "shell:AppsFolder\\obs")]


def test_bom_y_vacio():
    assert apps_instaladas.leer(falso("﻿" + JSON))
    assert apps_instaladas.leer(falso("")) == []


def test_si_powershell_falla():
    import pytest
    with pytest.raises(OSError):
        apps_instaladas.leer(falso("", codigo=1))
    with pytest.raises(OSError):
        apps_instaladas.leer(falso("esto no es json"))


def test_filtrar_ignora_tildes_y_mayusculas():
    apps = apps_instaladas.leer(falso(JSON))
    assert [a[0] for a in apps_instaladas.filtrar(apps, "camara")] == ["Cámara"]
    assert [a[0] for a in apps_instaladas.filtrar(apps, "SPOT")] == ["Spotify"]
    assert len(apps_instaladas.filtrar(apps, "")) == 3
    assert apps_instaladas.filtrar(apps, "zzz") == []


def test_exe_de_una_app_instalada():
    assert apps_instaladas.exe_de("shell:AppsFolder\\{6D809377}\\BraveSoftware\\brave.exe") == "brave.exe"
    assert apps_instaladas.exe_de("shell:AppsFolder\\Spotify.exe") == "Spotify.exe"
    assert apps_instaladas.exe_de("shell:AppsFolder\\Microsoft.WindowsCamera_8wekyb3d8bbwe!App") is None


def test_programas_abiertos_ahora():
    texto = json.dumps([{"Proceso": "brave.exe", "Nombre": "Brave Browser"}, {"Proceso": "obs64.exe", "Nombre": ""}])
    assert apps_instaladas.leer_abiertas(falso(texto)) == [("Brave Browser", "brave.exe"), ("obs64", "obs64.exe")]


def test_lista_para_cerrar_junta_abiertos_e_instalados_sin_repetir():
    abiertas = [("Brave Browser", "brave.exe"), ("Explorador", "explorer.exe"), ("Lynx", "Asistente.exe")]
    instaladas = [("Spotify", "shell:AppsFolder\\Spotify.exe"), ("Brave", "shell:AppsFolder\\x\\brave.exe"),
                  ("Cámara", "shell:AppsFolder\\Microsoft.WindowsCamera!App")]
    lista = apps_instaladas.para_cerrar(abiertas, instaladas)
    assert [exe for _, exe in lista] == ["brave.exe", "Spotify.exe"]   # sin escritorio, ni Lynx, ni apps sin .exe
    assert lista[0][0].endswith("abierto ahora")                        # lo abierto va primero
