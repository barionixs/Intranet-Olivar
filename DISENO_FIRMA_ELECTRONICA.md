# Diseño: Firma electrónica simple + jerarquía de funcionarios

> Generado el 2026-07-31 a partir de una conversación de diseño sobre el flujo de firma de `SolicitudPermiso` en la Intranet Municipal de Olivar. Complementa a `CONTEXTO_PROYECTO.md`. Pensado para cargar como contexto en Claude Code (VS Code) y continuar el desarrollo desde acá.
>
> **Estado a 2026-07-31: diseño cerrado, nada de esto está implementado todavía.** Pablo sigue rellenando datos de departamentos/jefaturas antes de dar luz verde a empezar el código.

## Objetivo

Reemplazar el sistema actual de aprobación (un botón de aprobar/rechazar, `SolicitudPermiso.estado` + `aprobado_por`) por un flujo de **firma electrónica simple** con 4 firmantes en orden, bajo Ley 19.799 chilena (firma simple, no avanzada — no requiere certificador acreditado).

Firmantes en orden:
1. Interesado (quien solicita)
2. Jefa de Personal (cargo único, fijo — Carola Alejandra Correa Reyes, RUT 11.757.449-0)
3. Jefatura directa (depende de la jerarquía real del solicitante, no del departamento)
4. Alcaldesa (cargo único, fijo — RUT pendiente de confirmar)

---

## 1. Tipo de firma y cómo se valida

No se necesita firma avanzada ni certificador (eso sería otro trámite vía e-CertChile, no aplica acá). Lo que exige la ley es poder **atribuir razonablemente el acto a una persona en un momento específico**. Se logra con:

- **Re-autenticación en el momento de firmar**: pedir la contraseña de nuevo, no basta con la sesión activa. Sesión activa prueba que entró al sistema; volver a pedir la clave prueba que *esa persona, en ese instante*, decidió firmar *ese* documento.
- **Hash del contenido** (`sha256` de los campos relevantes de la solicitud) tomado en el momento exacto de la firma. Si la solicitud se edita después, la firma queda ligada a esa versión específica — es lo que da trazabilidad real sin cripto de verdad.
- **IP + timestamp** de cada firma.
- **Checkbox de declaración explícita**: *"Declaro que firmo electrónicamente esta solicitud conforme a la Ley 19.799"* — texto que también se guarda.
- **Comprobante final**: al completar las 4 firmas, generar un PDF de respaldo con el detalle de cada una (nombre, RUT, fecha, hash). No es la firma en sí, es el archivo para respaldo/auditoría.

Explícitamente descartado: firma dibujada en canvas (no aporta valor legal, es solo estética).

### Vista de firma (esqueleto)

```python
def firmar(request, solicitud_id, orden):
    firma = get_object_or_404(FirmaSolicitud, solicitud_id=solicitud_id, orden=orden)

    if firma.funcionario_firmante.usuario != request.user:
        raise PermissionDenied

    form = ReautenticacionForm(request.POST)  # solo pide password + checkbox declaración
    if form.is_valid() and request.user.check_password(form.cleaned_data["password"]):
        firma.estado = "firmado"
        firma.fecha_firma = timezone.now()
        firma.ip_firma = get_client_ip(request)
        firma.hash_documento = hash_solicitud(firma.solicitud)
        firma.save()
```

---

## 2. Modelo de datos: `FirmaSolicitud`

Reemplaza el esquema actual de un solo botón por un registro de firma por firmante, con su propio rastro.

```python
class FirmaSolicitud(models.Model):
    ROL_FIRMANTE = [
        ("interesado", "Interesado"),
        ("jefa_personal", "Jefa de Personal"),
        ("jefatura_directa", "Jefatura directa"),
        ("alcaldesa", "Alcaldesa"),
    ]
    ESTADO = [("pendiente", "Pendiente"), ("firmado", "Firmado"), ("rechazado", "Rechazado")]

    solicitud = models.ForeignKey(SolicitudPermiso, related_name="firmas", on_delete=models.CASCADE)
    orden = models.PositiveSmallIntegerField()  # 1-4
    rol_firmante = models.CharField(max_length=20, choices=ROL_FIRMANTE)
    funcionario_firmante = models.ForeignKey(Funcionario, null=True, on_delete=models.SET_NULL)
    estado = models.CharField(max_length=10, choices=ESTADO, default="pendiente")
    fecha_firma = models.DateTimeField(null=True)
    ip_firma = models.GenericIPAddressField(null=True)
    hash_documento = models.CharField(max_length=64, blank=True)
    comentario = models.TextField(blank=True)
```

`SolicitudPermiso.estado` pasa a ser derivado: todas firmadas → aprobada; alguna rechazada → rechazada; si no, pendiente en el paso N.

---

## 3. Cargos únicos como configuración, no como código

En vez de hardcodear los RUT de Jefa de Personal y Alcaldesa:

```python
class CargoUnico(models.Model):
    nombre = models.CharField(max_length=50, unique=True)  # "jefa_personal", "alcaldesa"
    funcionario = models.ForeignKey(Funcionario, null=True, on_delete=models.SET_NULL)
```

Ventaja: se puede construir y dejar funcionando todo el flujo de firmas ya, con el registro de `alcaldesa` simplemente sin `funcionario` asignado (bloquea solo esa firma puntual, no todo el sistema). El día que cambie la persona en el cargo, se actualiza una fila, no el código.

---

## 4. Jerarquía: de "jefe por departamento" a "jefe directo por persona"

### El problema

Hoy `Departamento.jefe` asigna un jefe por departamento, con fallback a `departamento_padre`. Esto no representa bien casos como el de Norma Vidal (encargada de patentes comerciales, pero depende funcionalmente de DAF/Pedro Llanos, no necesariamente del jefe de su departamento asignado). El requisito real es una cadena director → jefe → encargado que puede tener distinto largo según la dirección, y no siempre coincide con la estructura de departamentos.

### La solución: jerarquía por persona

```python
class Funcionario(models.Model):
    # ... campos existentes ...
    jefe_directo = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="subordinados",
    )
```

Cada `Funcionario` apunta a su jefe inmediato. La cadena queda representada exactamente como es en la realidad, sin importar cuántos niveles tenga ni si coincide con departamentos.

### Resolución de "jefatura directa" respetando niveles de cargo

```python
NIVEL_CARGO = {"funcionario": 0, "encargado": 1, "jefe": 2, "director": 3}

def resolver_jefatura_directa(funcionario, nivel_minimo="jefe"):
    actual = funcionario
    visitados = {actual.id}
    while actual.jefe_directo:
        actual = actual.jefe_directo
        if actual.id in visitados:
            raise ValueError(f"Ciclo detectado en jerarquía de {funcionario}")
        visitados.add(actual.id)
        if NIVEL_CARGO.get(actual.cargo, 0) >= NIVEL_CARGO.get(nivel_minimo, 2):
            return actual
    return None  # no se encontró jefatura -> bloquear envío de la solicitud
```

Sube la cadena hasta encontrar el primer `jefe` o `director` (nivel configurable), sin que el código necesite saber de antemano cuántos escalones tiene esa dirección en particular. Si devuelve `None`, la solicitud no se puede enviar todavía — es una validación natural, no un error.

### Migración de datos existentes

`Departamento.jefe` se usa como semilla, no se pierde lo ya cargado:

```python
def poblar_jefe_directo_desde_departamentos():
    for f in Funcionario.objects.filter(jefe_directo__isnull=True):
        depto = f.departamento
        while depto:
            if depto.jefe and depto.jefe != f:
                f.jefe_directo = depto.jefe
                f.save()
                break
            depto = depto.departamento_padre
```

Correr una vez completado `Departamento.jefe` en los 21 departamentos, luego ajustar a mano casos especiales (Norma Vidal puede quedar apuntando directo a Pedro Llanos, sin pasar por el departamento).

### Validación de integridad

```python
def validar_sin_ciclos(funcionario):
    actual = funcionario.jefe_directo
    visitados = {funcionario.id}
    while actual:
        if actual.id in visitados:
            raise ValidationError(f"Ciclo jerárquico detectado involucrando a {funcionario}")
        visitados.add(actual.id)
        actual = actual.jefe_directo
```

Dos chequeos recomendados antes de confiar en la cadena:
1. **Sin ciclos** — nadie puede ser jefe de su propio jefe, directa o indirectamente.
2. **Todo funcionario no-director llega a alguien con cargo `jefe` o superior** — si `resolver_jefatura_directa` devuelve `None` para un funcionario normal, es dato incompleto, no caso legítimo.

---

## 5. Plan de desbloqueo en paralelo

Hay tres bloqueos de datos pendientes (jefe en 21 departamentos, jerarquía `departamento_padre` incompleta, RUT de la Alcaldesa). No es necesario esperar a que se resuelvan para avanzar en código:

1. Migraciones de `FirmaSolicitud`, `CargoUnico`, y `Funcionario.jefe_directo`.
2. `resolver_jefatura_directa()` con tests usando 2-3 funcionarios de prueba con cadenas de distinto largo.
3. Vista de firma (re-autenticación + checkbox + hash + registro) — testeable con cualquier funcionario, sin depender de datos reales de jerarquía.
4. Al final: correr `poblar_jefe_directo_desde_departamentos()`, ajustar casos especiales, confirmar RUT de la Alcaldesa, y sacar el feature flag para activar el flujo real sobre `SolicitudPermiso`.

---

## Pendiente para la próxima conversación

- Formulario/vista completa del paso de firma (incluyendo checkbox de declaración y generación del PDF de respaldo al completar las 4 firmas).
- Cerrar el modelo `jefe_directo` y correr las migraciones sobre datos reales.
- Definir generación y guardado del PDF de respaldo (qué librería, dónde se almacena — ¿junto a `respaldos_bd/`? ¿aparte?).
- Definir exactamente qué campos de `SolicitudPermiso` entran en `hash_documento` (¿incluye `estado`? cambia después de firmar, así que probablemente no).
