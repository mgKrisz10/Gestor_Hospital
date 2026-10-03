# Gestor de Citas Medicas - Etapa Funcional

Proyecto de **Paradigmas de Programacion**. La funcionalidad seleccionada para la primera etapa funcional es **busqueda de horarios disponibles de un medico**.

## Lo importante para ejecutar

No requiere Flask, Django, Node, npm ni ninguna otra libreria externa.

### Opcion 1: desde Visual Studio Code

1. Abre esta carpeta completa en VS Code.
2. Abre la terminal.
3. Ejecuta:

```bash
python app.py
```

El navegador se abre en `http://127.0.0.1:8000`.

### Opcion 2: Windows sin usar la terminal

Haz doble clic en **INICIAR.bat**.

### Pruebas

```bash
python -m unittest discover -s tests -v
```

o doble clic en **ejecutar_pruebas.bat**.

## Frontend

La interfaz esta en `frontend/` y se compone de HTML, CSS y JavaScript puro. Permite seleccionar medico, fecha y duracion, consultar la disponibilidad, ver citas ocupadas y seleccionar un horario.

## Backend

`app.py` inicia un servidor local con la biblioteca estandar `http.server`. Tambien puede abrirse `frontend/index.html` directamente o con Live Server de VS Code: en ese caso usa un modo demostracion local con los mismos datos ficticios. Para la integracion completa con Python, usa `python app.py`.

El frontend consume:

- `GET /api/doctores`
- `GET /api/disponibilidad?doctor=MED001&duracion=30`

La logica funcional se mantiene en `src/gestor_citas.py` y no depende de la interfaz.

## Datos ficticios

Los medicos y sus citas estan en `data/citas_ficticias.json`. El horario laboral de esta etapa es de 08:00 a 14:00.

## Programacion funcional aplicada

Se utilizan `@dataclass(frozen=True)`, funciones puras, composicion, `map`, `filter`, `reduce`, lambdas y separacion entre calculo y entrada/salida. Las funciones de negocio reciben datos y retornan nuevos datos sin mutar la entrada.

## Estructura

```text
gestor_citas_project/
├── app.py
├── INICIAR.bat
├── ejecutar_pruebas.bat
├── requirements.txt
├── README.md
├── data/
│   └── citas_ficticias.json
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── src/
│   ├── __init__.py
│   ├── gestor_citas.py
│   └── servidor.py
├── tests/
│   └── test_gestor_citas.py
└── docs/
    ├── Reporte_Etapa_Funcional_Gestor_Citas.docx
    ├── reporte_etapa_funcional.pdf
    └── resultado_pruebas.txt
```
