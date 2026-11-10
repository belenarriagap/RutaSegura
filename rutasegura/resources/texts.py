"""Textos de la interfaz, centralizados (preparado para traducción; por ahora solo español).

Para traducir: crear otra instancia de ``UiTexts`` y elegirla al iniciar la aplicación.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProjectTexts:
    """Crear, abrir y guardar proyectos."""

    menu_new: str = "&Nuevo proyecto…"
    menu_open: str = "&Abrir proyecto…"
    menu_save: str = "&Guardar"
    new_title: str = "Nuevo proyecto"
    open_title: str = "Abrir proyecto"
    name: str = "Nombre del local:"
    use: str = "Tipo de local:"
    address: str = "Dirección (opcional):"
    use_labels: tuple[tuple[str, str], ...] = (
        ("educacion", "Educación (colegio, instituto)"),
        ("oficinas", "Oficinas"),
        ("comercio", "Comercio (tienda)"),
    )
    name_required: str = "Escriba el nombre del local."
    no_projects: str = "Todavía no hay proyectos. Cree uno nuevo."
    saved: str = "Cambios guardados."
    opened: str = "Proyecto abierto: {name}"
    welcome_new: str = "Crear un proyecto nuevo"
    welcome_open: str = "Abrir un proyecto existente"
    error_title: str = "No se pudo completar la acción"


@dataclass(frozen=True, slots=True)
class WizardTexts:
    """Pasos 1 a 3 del asistente."""

    load_title: str = "Paso 1. Cargar plano"
    load_help: str = (
        "Elija una foto o un PDF del plano de su local. Si la foto está torcida, puede "
        "enderezarla marcando las 4 esquinas del plano."
    )
    choose_file: str = "Elegir archivo…"
    file_dialog_title: str = "Elegir plano"
    file_filter: str = "Planos ({patterns})"
    no_file: str = "Todavía no eligió un plano."
    page_label: str = "Página del PDF:"
    straighten: str = "Enderezar foto"
    straighten_help: str = (
        "Haga clic en las 4 esquinas del plano, en cualquier orden. Marcadas: {count} de 4."
    )
    straighten_undo: str = "Quitar enderezado"
    next: str = "Siguiente ›"
    scale_title: str = "Paso 2. Escala"
    scale_help: str = (
        "Dibuje una línea sobre una medida que conozca (por ejemplo, una cota del plano o el "
        "ancho de una puerta) y escriba cuántos metros mide."
    )
    scale_meters: str = "La línea mide (metros):"
    scale_apply: str = "Aplicar escala"
    scale_draw_first: str = "Primero dibuje la línea sobre el plano."
    scale_result: str = "Escala definida: 1 metro = {px_per_m:.1f} píxeles."
    scale_missing: str = (
        "Todavía no hay escala. Sin escala no se pueden calcular metros, aforo ni anchos."
    )
    editor_title: str = "Paso 3. Corregir plano"
    editor_help: str = (
        "Revise lo que encontró el sistema. Los elementos en naranja tienen baja confianza y las "
        "salidas en línea discontinua son propuestas: selecciónelas y pulse «Confirmar salida»."
    )
    detect: str = "Detectar automáticamente"
    detecting: str = "Buscando muros y puertas… esto puede tardar unos segundos."
    detect_done: str = (
        "Se encontraron {walls} muros, {doors} puertas y {exits} salidas propuestas. "
        "Revise y corrija lo necesario."
    )
    no_image: str = "Primero cargue un plano en el paso 1."
    step_not_ready: str = "Este paso estará disponible en el próximo hito."


@dataclass(frozen=True, slots=True)
class EditorTexts:
    """Editor de planos."""

    tool_select: str = "Seleccionar"
    tool_wall: str = "Muro"
    tool_door: str = "Puerta"
    tool_exit: str = "Salida"
    tool_stair: str = "Escalera"
    tool_obstacle: str = "Obstáculo"
    tool_safe_zone: str = "Zona segura"
    delete: str = "Borrar"
    confirm_exit: str = "Confirmar salida"
    undo: str = "Deshacer"
    redo: str = "Rehacer"
    fit: str = "Ver todo"
    layers: str = "Capas visibles"
    layer_background: str = "Plano de fondo"
    layer_walls: str = "Muros"
    layer_doors: str = "Puertas"
    layer_exits: str = "Salidas"
    layer_stairs: str = "Escaleras"
    layer_obstacles: str = "Obstáculos"
    layer_safe_zones: str = "Zonas seguras"
    hint_select: str = "Haga clic en un elemento para seleccionarlo; Supr lo borra."
    hint_segment: str = "Arrastre para dibujar. Mantenga Mayús para líneas rectas."
    hint_area: str = "Arrastre para dibujar un rectángulo."
    hint_zoom: str = "Rueda del mouse: acercar o alejar. Botón central: desplazar."
    pending_exits: str = "Hay {count} salida(s) propuesta(s) por confirmar."
    exit_name: str = "Salida {number}"
    cmd_add: str = "Agregar {what}"
    cmd_delete: str = "Borrar {count} elemento(s)"
    cmd_confirm: str = "Confirmar {count} salida(s)"
    cmd_detect: str = "Detección automática"


@dataclass(frozen=True, slots=True)
class RoomsTexts:
    """Paso 4: ambientes y ocupantes."""

    title: str = "Paso 4. Ambientes y ocupantes"
    help: str = (
        "Marque cada ambiente del local e indique cuántas personas de cada tipo hay en él "
        "en el momento más concurrido. Puede detectarlos automáticamente o dibujarlos "
        "haciendo clic en sus esquinas (doble clic para terminar)."
    )
    detect: str = "Detectar ambientes"
    draw: str = "Dibujar ambiente"
    delete: str = "Borrar ambiente"
    name_template: str = "Ambiente {number}"
    column_name: str = "Ambiente"
    column_use: str = "Uso"
    column_area: str = "Área (m²)"
    total: str = "Total: {count} personas"
    no_scale: str = "Primero defina la escala (paso 2): sin ella no se calculan las áreas."
    detected: str = "Se agregaron {count} ambiente(s). Revise sus nombres."
    nothing_detected: str = (
        "No se encontraron ambientes cerrados nuevos. Revise que los muros y puertas estén "
        "completos o dibújelos a mano."
    )


@dataclass(frozen=True, slots=True)
class SimulationTexts:
    """Paso 6: simulación y visor."""

    title: str = "Paso 6. Simular la evacuación"
    help: str = (
        "Simula un sismo: cada persona espera su tiempo de reacción y luego camina hacia la "
        "salida más cercana. Con la misma semilla, el resultado es siempre el mismo."
    )
    seed: str = "Semilla:"
    run: str = "Simular"
    cancel: str = "Cancelar"
    running: str = "Simulando… {percent:.0f} %"
    cancelled: str = "Simulación cancelada."
    play: str = "▶ Reproducir"
    pause: str = "⏸ Pausa"
    speed: str = "Velocidad:"
    heatmap: str = "Mapa de calor"
    time: str = "{now} / {end}"
    evacuated: str = "Evacuados: {done} de {total}"
    results_title: str = "Resultados"
    total_time: str = "Tiempo total de evacuación: {time}"
    incomplete: str = (
        "Atención: después de {time} todavía quedaban {left} personas dentro. "
        "Revise salidas y puertas."
    )
    per_exit: str = "{name}: {time}"
    bottlenecks_title: str = "Cuellos de botella (del más grave al menos grave)"
    no_bottlenecks: str = "No se detectaron zonas de congestión sostenida."
    no_run: str = "Todavía no hay resultados. Pulse «Simular»."
    provisional: str = (
        "Los parámetros del modelo son provisionales hasta calibrarlos con un simulacro real."
    )


@dataclass(frozen=True, slots=True)
class UiTexts:
    """Catálogo de textos visibles para el usuario."""

    app_name: str
    window_title: str
    welcome_title: str
    welcome_body: str
    wizard_steps: tuple[str, ...]
    menu_file: str
    menu_edit: str
    menu_help: str
    action_quit: str
    action_about: str
    about_title: str
    about_body: str
    status_ready: str
    legal_disclaimer: str
    project: ProjectTexts = field(default_factory=ProjectTexts)
    wizard: WizardTexts = field(default_factory=WizardTexts)
    editor: EditorTexts = field(default_factory=EditorTexts)
    rooms: RoomsTexts = field(default_factory=RoomsTexts)
    simulation: SimulationTexts = field(default_factory=SimulationTexts)


SPANISH = UiTexts(
    app_name="RutaSegura",
    window_title="RutaSegura — Simulación de evacuación",
    welcome_title="Bienvenido a RutaSegura",
    welcome_body=(
        "Con RutaSegura puede revisar si las personas de su local pueden salir a tiempo "
        "durante un sismo. Le guiaremos paso a paso, desde la foto del plano hasta el informe."
    ),
    wizard_steps=(
        "1. Cargar plano",
        "2. Escala",
        "3. Corregir plano",
        "4. Ambientes y ocupantes",
        "5. Revisar norma",
        "6. Simular",
        "7. Informe",
    ),
    menu_file="&Archivo",
    menu_edit="&Editar",
    menu_help="A&yuda",
    action_quit="&Salir",
    action_about="&Acerca de RutaSegura",
    about_title="Acerca de RutaSegura",
    about_body=(
        "RutaSegura {version}\n\nFunciona sin internet: sus planos nunca salen de este equipo."
    ),
    status_ready="Listo",
    legal_disclaimer=(
        "Este informe es de apoyo y no reemplaza la Inspección Técnica de Seguridad en "
        "Edificaciones (ITSE) ni el estudio de un profesional colegiado."
    ),
)

TEXTS: UiTexts = SPANISH
