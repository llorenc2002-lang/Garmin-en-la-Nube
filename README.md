# Garmin en la Nube

Sincronización diaria de solo lectura desde Garmin Connect Personal API a PostgreSQL en Neon. El repositorio contiene código y configuración; los datos de salud se envían directamente a Neon y no se guardan como archivos en GitHub.

## Preparación

1. Usa el proyecto Neon **my-first-project**, que está en el plan Free. En Neon, abre **Connect** y copia la cadena de conexión de PostgreSQL, manteniendo SSL activado.
2. En GitHub, abre **Settings → Secrets and variables → Actions → New repository secret**.
3. Crea estos dos secretos y pega cada valor directamente en su campo:
   - `GARMIN_PERSONAL_API_KEY`: la Personal API Key de Garmin.
   - `DATABASE_URL`: la cadena de conexión de Neon.
4. Abre **Actions → Garmin to Neon sync → Run workflow**. La ejecución manual importa hasta 90 días por defecto. Después, la tarea programada refresca los últimos 7 días cada día a las 04:37 UTC.

No pegues ninguna clave en una incidencia, archivo del repositorio o chat. Los registros de ejecución solo informan del número de filas y del tipo de error, nunca imprimen los datos de salud, claves ni URL.

## Datos guardados

La tabla `garmin_records` almacena JSON original por conjunto, fecha e identificador. Se sincronizan resúmenes diarios, sueño, pasos, estrés, HRV, Body Battery y actividades. La clave compuesta hace que repetir un periodo actualice datos existentes en vez de duplicarlos.

El proyecto Neon visible actualmente usa Free. Los límites del plan pueden cambiar; configura en Neon/GitHub controles para que no se aplique un plan de pago automáticamente. Si se alcanzan los límites gratuitos, la sincronización puede detenerse hasta que se reduzca el consumo o se elija conscientemente otro plan.

La futura lectura del histórico desde ChatGPT no está incluida en esta sincronización.
