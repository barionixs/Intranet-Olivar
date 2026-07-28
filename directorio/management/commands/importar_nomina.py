import re
import unicodedata

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from directorio.models import Departamento, Funcionario


def normalizar_texto(valor):
    """Mayúsculas, sin tildes y sin puntuación, para poder comparar
    'DIRECCION DE...' (Excel, sin tildes) con 'Dirección de...' (BD, con
    tildes) o 'O.I.R.S' con 'OIRS'."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", valor) if not unicodedata.combining(c)
    )
    sin_puntuacion = re.sub(r"[^A-Z0-9 ]", "", sin_tildes.upper())
    return re.sub(r"\s+", " ", sin_puntuacion).strip()


RUT_VALIDO = re.compile(r"^\d{6,9}-[0-9K]$")


def normalizar_rut(valor):
    """Deja el RUT como NNNNNNNN-K: sin puntos, con guión, dígito
    verificador en mayúscula. Tolera puntos mal puestos en el origen
    (ej. '15.97.1243-5'), porque solo importan los dígitos y el guión."""
    limpio = re.sub(r"[.\s]", "", str(valor)).upper()
    if "-" not in limpio and len(limpio) > 1:
        limpio = f"{limpio[:-1]}-{limpio[-1]}"
    return limpio


def encontrar_columna_fecha(columnas):
    for c in columnas:
        if c.startswith("FECHA NACIMIENTO"):
            return c
    return None


# Cargos/programas de la nómina real que no calzan textualmente con ningún
# departamento pero que, en la estructura típica de un municipio chileno,
# corresponden a programas o roles de estas áreas. Revisado con RRHH/usuario
# el 2026-07-28; ajustar aquí si el organigrama oficial dice otra cosa.
SINONIMOS = {
    "EJECUTIVO ATENCION DE USUARIO OMIL": "DIDECO",
    "ELABORACION CATASTRO DE EMPRENDEDORES COMUNA DE OLIVAR": "DIDECO",
    "APOYO FAMILIAR INTEGRAL DEL PROGRAMA FAMILIA": "DIDECO",
    "ENCARGADO DE RECINTO DEPORTIVO OLIVAR ALTO": "DIDECO",
    "ENCARGADO DE RECINTO DEPORTIVO OLIVAR BAJO": "DIDECO",
    "PROGRAMA DIAGNOSTICO": "DIDECO",
    "PROFESORA DE AEROBICA SECTOR OLIVAR ALTO Y OLIVAR BAJO": "DIDECO",
    "INSTRUCTORA DE ZUMBA": "DIDECO",
    "PROFESORA DE VOLEIBOL SECTOR OLIVAR ALTO": "DIDECO",
    "PROFESOR DE FUTBOL EN OLIVAR ALTO": "DIDECO",
    "INSTRUCTORA DE YOGA": "DIDECO",
    "APOYO DE ENTREGA DE AYUDA ASISTENCIALES": "DIDECO",
    "COORDINADORA DE EQUIPO TECNICO NPRODESAL A HONORARIOS": "DIDECO",
    "TECNICO ASESOR DEL PROGRMA DE PRODESAL": "DIDECO",
    "APOYO OFICINA RE3GISTRO SOCIAL DE HOGARES": "DIDECO",
    "CORDINADOR PROGRAMA CHILE CRECE CONTIGO": "DIDECO",
    "ALCALDESA": "ALCALDIA",
}


def emparejar_departamento(area_original, departamentos_cache):
    """Busca coincidencia exacta primero (ignorando tildes/puntuación); luego
    la tabla de SINONIMOS para cargos/programas conocidos; y por último que el
    nombre del departamento esté contenido en el texto del área (o viceversa).
    Si hay más de un departamento candidato por substring, se considera
    ambiguo y se deja para revisión manual en vez de adivinar."""
    area = normalizar_texto(area_original)

    if area in departamentos_cache:
        return departamentos_cache[area], False

    if area in SINONIMOS:
        return departamentos_cache.get(SINONIMOS[area]), False

    candidatos = [
        dep
        for nombre, dep in departamentos_cache.items()
        if nombre in area or area in nombre
    ]
    candidatos_unicos = {dep.pk: dep for dep in candidatos}
    if len(candidatos_unicos) == 1:
        return next(iter(candidatos_unicos.values())), False

    return None, len(candidatos_unicos) > 1  # (None, es_ambiguo)


class Command(BaseCommand):
    help = (
        "Importa funcionarios desde el Excel de nómina/cumpleaños. "
        "No incluye CARGO: queda vacío para completarse manualmente en el admin."
    )

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str, help="Ruta al archivo .xlsx de nómina")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué se importaría, sin guardar nada en la base de datos.",
        )

    def handle(self, *args, **options):
        ruta = options["archivo"]
        dry_run = options["dry_run"]

        try:
            df = pd.read_excel(ruta)
        except FileNotFoundError:
            raise CommandError(f"No se encontró el archivo: {ruta}")

        df.columns = [str(c).strip().upper() for c in df.columns]
        col_fecha = encontrar_columna_fecha(df.columns)

        requeridas_fijas = {"NOMBRE", "RUT", "ÁREA"}
        faltantes = requeridas_fijas - set(df.columns)
        if faltantes or col_fecha is None:
            faltantes_msg = sorted(faltantes | ({"FECHA NACIMIENTO..."} if col_fecha is None else set()))
            raise CommandError(
                f"Faltan columnas en el Excel: {', '.join(faltantes_msg)}. "
                f"Columnas encontradas: {', '.join(df.columns)}"
            )

        departamentos_cache = {normalizar_texto(d.nombre): d for d in Departamento.objects.all()}

        creados, actualizados = 0, 0
        sin_area, ambiguos, rut_invalido, filas_vacias = [], [], [], 0
        vistos_en_archivo = {}  # rut normalizado -> primera fila donde apareció

        for i, fila in df.iterrows():
            nombre = fila.get("NOMBRE")
            rut_crudo = fila.get("RUT")
            if pd.isna(nombre) or pd.isna(rut_crudo):
                filas_vacias += 1
                continue

            nombre = str(nombre).strip()
            rut = normalizar_rut(rut_crudo)
            fila_num = i + 2  # +2 = fila real en Excel (encabezado + índice 0-based)

            if not RUT_VALIDO.match(rut):
                rut_invalido.append((fila_num, nombre, rut_crudo))
                continue

            if rut in vistos_en_archivo:
                rut_invalido.append(
                    (fila_num, nombre, f"RUT duplicado en el archivo (misma fila que {vistos_en_archivo[rut]}: {rut})")
                )
                continue
            vistos_en_archivo[rut] = fila_num

            area_original = str(fila["ÁREA"]).strip()
            fecha_nacimiento = pd.to_datetime(fila[col_fecha]).date()

            departamento, es_ambiguo = emparejar_departamento(area_original, departamentos_cache)
            if departamento is None:
                (ambiguos if es_ambiguo else sin_area).append((fila_num, nombre, area_original))
                continue

            if dry_run:
                self.stdout.write(f"[dry-run] {nombre} | {rut} | {departamento} | {fecha_nacimiento}")
                continue

            _, fue_creado = Funcionario.objects.update_or_create(
                rut=rut,
                defaults={
                    "nombre_completo": nombre,
                    "departamento": departamento,
                    "fecha_nacimiento": fecha_nacimiento,
                },
            )
            creados += int(fue_creado)
            actualizados += int(not fue_creado)

        for etiqueta, lista in (
            ("SIN COINCIDENCIA DE ÁREA", sin_area),
            ("ÁREA AMBIGUA (varios departamentos posibles)", ambiguos),
            ("RUT INVÁLIDO O DUPLICADO EN EL ARCHIVO", rut_invalido),
        ):
            if lista:
                self.stdout.write(self.style.WARNING(f"\n{etiqueta} — no importados ({len(lista)}):"))
                for fila_num, nombre, detalle in lista:
                    self.stdout.write(f"  Fila {fila_num}: {nombre} -> '{detalle}'")

        if filas_vacias:
            self.stdout.write(self.style.WARNING(f"\nFilas vacías/sin nombre-RUT saltadas: {filas_vacias}"))

        total_pendientes = len(sin_area) + len(ambiguos) + len(rut_invalido)
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nSimulación: {len(df) - filas_vacias - total_pendientes} filas listas para importar."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nListo: {creados} funcionarios creados, {actualizados} actualizados.")
            )
