"""Control por Telegram: quién obedece, qué ejecuta y que el token no se filtre."""
import time
import types

import pytest

import nucleo
import remoto

TOKEN = "123456:SECRETO-ABC"
DUENIO = 42


class MotorFalso:
    listo = True

    def __init__(self):
        self.ejecutados = []

    def ejecutar_remoto(self, cmd, timeout=25):
        self.ejecutados.append(cmd["frase"])
        return "Abriendo."


COMANDOS = [
    {"frase": "abri obs", "tipo": "abrir_programa", "valor": "obs"},
    {"frase": "terminamos por hoy", "tipo": "apagar", "confirmar": True},
]


@pytest.fixture
def bot(tmp_path, monkeypatch):
    enviados, apagados = [], []
    monkeypatch.setattr(nucleo, "ARCHIVO_LOG", tmp_path / "a.log")
    monkeypatch.setattr(remoto, "_llamar", lambda token, metodo, datos=None, timeout=20:
                        enviados.append((datos["chat_id"], datos["text"])) if metodo == "sendMessage" else {})
    monkeypatch.setattr(remoto, "_correr", apagados.append)
    monkeypatch.setattr(remoto, "bateria", lambda: "Batería: 64%.")
    motor = MotorFalso()
    app = types.SimpleNamespace(
        config={"telegram_activo": True, "telegram_token": TOKEN, "telegram_usuario": 0,
                "carpetas_descarga": [str(tmp_path)]},
        motor=motor)
    monkeypatch.setattr(nucleo, "leer_comandos", lambda: COMANDOS)
    app.motor.comandos = COMANDOS
    r = remoto.Remoto(app)

    def decir(texto, quien=DUENIO, edad=0):
        enviados.clear()
        r.procesar({"update_id": 1, "message": {"text": texto, "from": {"id": quien, "first_name": "Ana"},
                                                "date": time.time() - edad}})
        return [t for _, t in enviados]

    return types.SimpleNamespace(r=r, app=app, motor=motor, decir=decir, apagados=apagados)


def test_sin_duenio_configurado_no_obedece_pero_anota_quien_escribio(bot):
    respuesta = bot.decir("apagá la pc")
    assert bot.r.candidato == (DUENIO, "Ana") and "42" in respuesta[0]
    assert bot.apagados == [] and bot.motor.ejecutados == []


def test_ignora_a_otros_usuarios_y_mensajes_viejos(bot):
    bot.app.config["telegram_usuario"] = DUENIO
    assert bot.decir("abri obs", quien=99) == []
    assert bot.decir("abri obs", edad=900) == []
    assert bot.motor.ejecutados == []


def test_ejecuta_tus_comandos(bot):
    bot.app.config["telegram_usuario"] = DUENIO
    assert bot.decir("abri obs")[0].startswith("Hecho")
    assert bot.motor.ejecutados == ["abri obs"]


def test_un_comando_con_confirmacion_espera_el_si(bot):
    bot.app.config["telegram_usuario"] = DUENIO
    assert "confirmación" in bot.decir("terminamos por hoy")[0] and bot.motor.ejecutados == []
    assert bot.decir("sí")[0].startswith("Hecho") and bot.motor.ejecutados == ["terminamos por hoy"]
    bot.decir("terminamos por hoy")
    assert bot.decir("no") == ["Listo, no hice nada."]


def test_apagar_directo_pide_confirmacion_y_se_puede_cancelar(bot):
    bot.app.config["telegram_usuario"] = DUENIO
    assert "¿Apago" in bot.decir("apagá la compu")[0] and bot.apagados == []
    assert "60 segundos" in bot.decir("dale")[0]
    assert bot.apagados == [["shutdown", "/s", "/t", "60"]]
    assert "Cancelé el apagado" in bot.decir("cancelar")[0] and ["shutdown", "/a"] in bot.apagados


def test_el_token_nunca_aparece_en_los_errores(monkeypatch):
    import importlib
    import urllib.request

    def explota(*_, **__):
        raise OSError(f"fallo en https://api.telegram.org/bot{TOKEN}/getMe")

    monkeypatch.setattr(urllib.request, "urlopen", explota)
    real = importlib.reload(remoto)  # la fixture reemplaza _llamar; acá probamos la verdadera
    with pytest.raises(RuntimeError) as e:
        real._llamar(TOKEN, "getMe")
    assert "SECRETO" not in str(e.value)
