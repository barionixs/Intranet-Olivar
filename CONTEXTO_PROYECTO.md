# Intranet Municipal de Olivar — contexto del proyecto

> Generado el 2026-07-31 para dar contexto a otra conversación de Claude sobre este proyecto. Refleja el estado del código y la base de datos a esa fecha — verificar contra el repo antes de asumir que algo sigue igual.

## Qué es

Intranet interna para funcionarios de la Municipalidad de Olivar (Chile), ~100 usuarios. Cubre RRHH, directorio de funcionarios, comunicados internos y (en desarrollo) un flujo de solicitudes de permisos/vacaciones con firma electrónica simple. Es un proyecto de aprendizaje de Pablo Reyes, TI de la municipalidad, construido con ayuda de Claude Code.

## Stack

- **Backend**: Django 6.0.7 (Python), templates de Django (no SPA — la migración a React quedó descartada por ahora).
- **Base de datos**: PostgreSQL 18 local (`intranet_olivar`, rol `intranet_olivar`, `localhost:5432`). Antes era SQLite; la migración fue el 2026-07-28.
- **Secretos**: desde 2026-07-30, `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS`/credenciales de BD se leen desde `.env` (vía `django-environ`), no están hardcodeados. `.env.example` sirve de plantilla.
- **Repo**: GitHub (`barionixs/Intranet-Olivar`), rama `master`. Respaldo de BD aparte, vía `pg_dump` a `respaldos_bd/` (gitignorado, nunca se sube data real a git).
- **Protección de login**: `django-axes` (5 intentos fallidos → bloqueo 30 min).

## Apps Django

- **`usuarios`**: modelo `Usuario` (extiende `AbstractUser` + campo `rol`), login por RUT, panel CRUD de usuarios (solo super admin), middleware que fuerza cambio de clave en el primer login.
- **`directorio`**: modelos `Funcionario` y `Departamento`. Búsqueda, ficha con datos sensibles gateados por permiso, panel CRUD (solo super admin).
- **`rrhh`**: `FichaLaboral`, `SolicitudPermiso`, `LicenciaMedica`, `LiquidacionSueldo`, `DocumentoPersonal` — todo cuelga de `Funcionario`, no de `Usuario`. Incluye "Mi Ficha" (autoservicio de solo lectura) y el flujo de solicitud/aprobación de permisos.
- **`comunicados`**: tablón de anuncios (modelo simple, sin mucho desarrollo adicional aún).

## Modelo de datos: puntos importantes

- **`Funcionario` es la ficha de RRHH/directorio; `Usuario` es la cuenta de acceso.** Antes estaban desacoplados a propósito (`on_delete=SET_NULL`), pero **desde 2026-07-30 son CASCADE**: borrar un `Usuario` borra automáticamente su `Funcionario` (y todo lo que cuelgue de RRHH). Esto fue un pedido explícito para que ambos queden siempre sincronizados.
- **`Departamento.departamento_padre`**: existe desde el inicio pero recién se está poblando (2026-07-31). Varias unidades comparten director con una dirección superior aunque son unidades separadas — ejemplos ya cargados: Licencias de Conducir → DAF, Rentas y Permisos de Circulación → DAF, Informática → Servicios Generales, Organizaciones Comunitarias → DIDECO. Quedan más por vincular; Pablo está terminando de cargar datos antes de seguir.
- **`Departamento.jefe`**: apunta al `Funcionario` que encabeza el departamento. **A la fecha de este documento sigue vacío en los 21 departamentos** — es el siguiente paso, Pablo está "rellenando con datos" antes de asignarlo. Este campo es el que determina en el código quién puede aprobar solicitudes de un departamento (no el campo `Rol` del Usuario, que es solo una etiqueta visual hoy).

## Roles y cargos (dos campos distintos, no confundir)

- **`Usuario.rol`** (permisos/etiqueta): `funcionario`, `jefatura`, `directivo`, `encargado`. Se sacaron `rrhh` y `admin` del desplegable a pedido de Pablo — pero el código sigue comparando contra esos strings literales en varios lados (`directorio/models.py`, `rrhh/utils.py`, `comunicados/views.py`), y la cuenta de Pablo (super admin) sigue teniendo `rol="admin"` guardado, solo que ya no es seleccionable desde el formulario.
- **`Funcionario.cargo`** (cargo real de RRHH): `funcionario`, `jefe`, `encargado`, `director`.
- **Importante**: el `Rol` de Usuario **no otorga permisos de aprobación por sí solo**. Lo que determina quién puede aprobar/ver solicitudes de un departamento es exclusivamente `Departamento.jefe` (ver `rrhh/utils.py::es_jefatura`).

## El flujo de firma electrónica simple (en diseño, no construido aún)

Decisión confirmada por Pablo el 2026-07-30, bajo el marco de la Ley 19.799 chilena (firma electrónica *simple*, no avanzada — no requiere certificador acreditado):

**Toda `SolicitudPermiso`** (los 4 tipos: Vacaciones, Día administrativo, Permiso sin goce de sueldo, Otro) necesita **4 firmas en orden**:

1. **Firma del interesado** — quien solicita, al momento de enviar la solicitud (prueba de que la pidió realmente).
2. **Jefa de Personal** — cargo único, fijo, no depende de departamento. Identificada: **Carola Alejandra Correa Reyes, RUT 11.757.449-0**.
3. **Jefatura directa** — depende del departamento del solicitante (`Departamento.jefe`, con fallback al `departamento_padre` si la unidad no tiene jefe propio). Aplica igual en los 21 departamentos, no es un caso especial.
4. **Alcaldesa** — cargo único, fijo. **Su RUT todavía no ha sido confirmado por Pablo** (quedó pendiente).

Esto reemplaza el sistema actual, que es solo un botón de aprobar/rechazar de una persona (`SolicitudPermiso.estado` + `aprobado_por` + `fecha_resolucion`, sin firma real). **No construido todavía** — bloqueado hasta que Pablo termine de: (a) rellenar los datos pendientes, (b) asignar `Departamento.jefe` en los 21 departamentos, (c) confirmar el RUT de la Alcaldesa.

### Caso especial ya resuelto: Norma Vidal
Es "encargada de patentes comerciales" pero esa función depende de DAF, cuyo director es Pedro Llanos — su jefatura directa no es necesariamente quien figura como jefe de su departamento asignado. Este tipo de caso es justo lo que la jerarquía `departamento_padre` (recién empezada a poblar) debería resolver sin necesitar un campo aparte de "jefe directo".

## Cuentas con particularidades (no tocar sin preguntar)

- **Super admin**: Pablo, RUT `20026280-8`, `is_superuser=True`, `rol="admin"`.
- **Raimundo Arenas (RUT 19261027-3) y Felipe Bahamondes (RUT 14491523-2)**: eliminados a propósito de la intranet — si reaparecen como "sin usuario", **no reprovisionar** sin que Pablo lo pida explícitamente.
- **Juan Pablo Moya Miranda y Johnny Ceballos Cid**: cuentas con correo de cargo (`dideco@muniolivar.cl`, `jefedaem@eduolivar.cl`) sin ficha de `Funcionario` vinculada — parecen ser cuentas genéricas por cargo, no por persona. Confirmar con Pablo antes de asumir que es un error.

## Convenciones de trabajo con Claude Code en este proyecto

- Todo el código y mensajes en español, mismo estilo que el resto del repo.
- Nunca commitear `.env`, `data_privada/` (datos reales de nómina/RUT) ni `respaldos_bd/` — todos gitignorados.
- Los respaldos de base de datos se hacen con `pg_dump` (formato custom) a `respaldos_bd/`, separado del respaldo de código en GitHub.
- Antes de cada commit/push a GitHub, se confirma con Pablo qué se va a subir.
- El servidor de desarrollo se corre con `venv/Scripts/python.exe manage.py runserver`, verificado en el navegador vía Playwright (no hay `chromium-cli` en este entorno).
