"""Catálogo institucional de especialidades habilitadas para nuevas altas."""
import unicodedata

ESPECIALIDADES_HOSPITAL = (
    'Medicina general', 'Cardiología', 'Pediatría', 'Dermatología',
    'Anestesiología', 'Neurocirugía', 'Neurología', 'Medicina interna',
    'Ginecología', 'Ortopedia', 'Oftalmología', 'Endocrinología',
)


def clave(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '').strip())
    return ''.join(c for c in texto if not unicodedata.combining(c)).casefold()


def normalizar(valor):
    return {clave(e): e for e in ESPECIALIDADES_HOSPITAL}.get(clave(valor))
