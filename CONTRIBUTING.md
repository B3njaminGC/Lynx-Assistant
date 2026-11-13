# Cómo colaborar

¡Gracias por el interés! Algunas pautas para que los cambios sean fáciles de revisar.

- **Una idea por cambio**, con un mensaje de commit que explique el *porqué*.
- **Pruebas**: si tocás lógica que se puede verificar sin micrófono ni ventanas, sumá o ajustá una prueba en
  `tests/` y corré `python -m pytest tests`.
- **Probalo en Windows de verdad** cuando el cambio afecte la voz, la bandeja o las ventanas; esas partes no
  tienen pruebas automáticas.
- **Nada personal en el repo**: `comandos.json`, `config.json`, tokens, voces y modelos están en `.gitignore`.
  No subas voces de personajes ni modelos de terceros.
- **Seguridad**: el control por Telegram solo debe obedecer a la cuenta configurada, y el token no debe aparecer
  en logs ni mensajes de error. Si encontrás algo que lo rompa, avisá por un *issue* sin pegar tu token.

Si usás una herramienta de IA para programar, está bien; lo que importa es que entiendas el cambio, lo hayas
probado y lo expliques en la descripción.
