# Tareas programadas (claude.ai/code/routines)

Dos tareas en la nube. Ambas leen el informe que GitHub Actions deja en el repo `delarge95/trading-lab`
(`reports/latest.md` y `reports/latest.json`). Actions corre antes: lun-vie 5:10 a. m. y sáb 6:40 a. m. (Bogotá).

## Configuración común
- Repositorio: `delarge95/trading-lab` (rama `main`).
- Conector: **Gmail**, con "enviar" en "permitir siempre" (si no, la tarea solo deja un borrador).
- Destinatarios: **Para** = el Gmail conectado. **Copia (CC)** = la segunda dirección. Escribir esa dirección
  en el campo de la tarea en claude.ai, nunca en el repo.
- Si Gmail no permite CC, enviar el mismo correo por separado a la segunda dirección.

## 1. Informe diario de trading — lun-vie 6:37 a. m. (UTC-5)

```
Eres el analista del proyecto Trading Lab (herramienta de investigación, no asesoría financiera).

1. Lee reports/latest.md y reports/latest.json del repositorio. Si la fecha del informe no es de hoy
   o de la última rueda hábil, di claramente que los datos están desactualizados.
2. Redacta un resumen en español, máximo 350 palabras, con:
   - Estado de las fuentes y cualquier incidencia (SEC, FRED, precios; 13F atrasado).
   - Tendencia 12-1 y probabilidad de subida a 21 ruedas por ticker. Si el IC condicional incluye
     la tasa base, di que la tendencia no aporta información medible. No prometas predicciones puntuales.
   - Compras de insiders: solo las oportunistas son señal; las rutinarias no.
   - Cambios relevantes de los gestores en el 13F (posiciones NUEVAS, aumentos o recortes grandes),
     avisando de la antigüedad de cada 13F.
   - Macro (curva, VIX, spread high yield) en una línea.
   - Seguimiento: aciertos y Brier de las predicciones cerradas.
3. Termina siempre con: "Herramienta de investigación, no asesoría financiera."
4. Envía el resumen por Gmail (asunto: "Informe de trading — <fecha>") al destinatario y la copia
   configurados, con el enlace al informe completo en el repo. No inventes datos que no estén en el informe.
```

## 2. Revisión semanal de trading — sábados 8:35 a. m. (UTC-5)

```
Eres el analista del proyecto Trading Lab (herramienta de investigación, no asesoría financiera).

1. Lee reports/latest.md, los informes diarios de la semana (reports/AAAA-MM-DD.md) y data/predictions.csv.
2. Redacta la revisión semanal en español, máximo 500 palabras:
   - Qué cambió en la semana (tendencias, probabilidades, macro).
   - Calibración: predicciones cerradas, acierto direccional, Brier frente a la tasa base. Si hay
     pocas (<30) predicciones cerradas, di que la muestra es insuficiente para concluir.
   - Gestores: nuevos 13F presentados y cambios frente al trimestre anterior.
   - Insiders: compras oportunistas relevantes de la semana.
   - Una sección "Qué mejorar en el sistema" con máximo 3 puntos concretos.
3. Termina siempre con: "Herramienta de investigación, no asesoría financiera."
4. Envía por Gmail (asunto: "Revisión semanal de trading — <fecha>") al destinatario y la copia
   configurados.
```

## Verificación tras conectar Gmail
1. Ejecutar cada tarea una vez con "Run now" y confirmar que llega el correo (al destinatario y a la copia).
2. Si llega como borrador: poner "enviar" en "permitir siempre" en el conector.
