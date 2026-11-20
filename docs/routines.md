# Tareas programadas (Claude Code, nube)

Dos tareas de Claude Code creadas el 2026-11-20. Cada ejecución clona este repo público y lee el informe que deja
GitHub Actions (`reports/latest.md`, `reports/latest.json`, `data/predictions.csv`, `data/managers_track.json`).

| Tarea | Horario (Bogotá) | Cron (UTC) | Enlace |
|---|---|---|---|
| Informe diario de trading | lun-vie 6:37 a. m. | `37 11 * * 1-5` | https://claude.ai/code/routines/trig_012ZWviUWMxCQpBovLFejmk3 |
| Revisión semanal de trading | sáb 8:35 a. m. | `35 13 * * 6` | https://claude.ai/code/routines/trig_01PeSjegApFFNmuBA29ciG5h |

GitHub Actions corre antes: lun-vie 5:10 a. m. y sáb 6:40 a. m. (Bogotá), para que el informe esté listo.

## Configuración
- Modelo: `claude-sonnet-5-5`. Entorno: el predeterminado de Anthropic Cloud.
- Repo: `https://github.com/delarge95/trading-lab` (público; no necesita token).
- Conectores adjuntos al crearlas: Claude Docs, Gmail, Claude Code Remote y Wolfram.
- Para: la cuenta Gmail conectada. **Copia (CC):** la dirección va en la línea `COPIA_CC=` del texto de cada tarea
  (ya configurada en las dos). Se edita desde claude.ai/code/routines; nunca se escribe en el repo, que es público.
- Si Gmail pide aprobación para enviar, la tarea deja un borrador. Para envío automático, en los permisos del
  conector Gmail poner "Enviar correo" en "Permitir siempre".

## Tareas anteriores (creadas desde el chat del proyecto "Trading")
`trig_01RXE1epMfD9iGpJn9yhBSaZ` (diaria) y `trig_0131SuUnRf1TkCewCqSwSkZX` (semanal) quedaron **pausadas** el
2026-11-20 (sin Gmail ni acceso al repo). Se pueden borrar desde claude.ai/code/routines.

## Verificación
1. Abrir cada tarea y pulsar "Run now" una vez; confirmar el correo.
2. Si llega como borrador: revisar el permiso "Enviar correo" del conector Gmail.
3. Si el correo dice que los datos del repo son de otra fecha, revisar la pestaña Actions del repo.
