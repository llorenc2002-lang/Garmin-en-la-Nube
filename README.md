# Garmin en la Nube

Sincronización diaria de solo lectura desde Garmin Connect Personal API a PostgreSQL en Neon. El repositorio es público y contiene solo código. Los datos pasan temporalmente por un runner alojado de GitHub Actions durante la sincronización y se guardan en Neon; el código no los escribe en el repositorio ni en los registros de ejecución.

## Preparación

1. Usa el proyecto Neon **my-first-project**, que está en el plan Free. En Neon, abre **Connect** y copia la cadena de conexión de PostgreSQL con SSL activado.
2. En GitHub, abre **Settings → Secrets and variables → Actions → New repository secret**.
3. Crea estos dos secretos y pega cada valor directamente en su campo:
   - `GARMIN_PERSONAL_API_KEY`: la Personal API Key de Garmin.
   - `DATABASE_URL`: la cadena de conexión de Neon.
4. Abre **Actions → Garmin to Neon sync → Run workflow**. La ejecución manual importa hasta 90 días por defecto. Después, la tarea programada refresca los últimos 7 días cada día a las 04:37 UTC.

No pegues ninguna clave en una incidencia, archivo del repositorio o chat. Los registros de Actions son públicos porque el repositorio es público; el flujo solo informa del número de filas y del tipo de error, nunca imprime datos de salud, claves ni URL.

## Datos guardados

- `garmin_records`: JSON original de resúmenes diarios, sueño, pasos, estrés, HRV, Body Battery y actividades.
- `garmin_activity_files`: archivos ZIP de actividades descargados desde Garmin, con los datos FIT.

La clave compuesta hace que repetir un periodo actualice el JSON existente en vez de duplicarlo. Los archivos FIT se descargan una vez por actividad.

El proyecto Neon visible actualmente usa Free. Revisa sus límites de uso y almacenamiento; si se alcanzan, la sincronización puede detenerse mientras se mantenga el plan gratuito. No hay recursos de Render en esta configuración.

La futura lectura del histórico desde ChatGPT no está incluida en esta sincronización.
