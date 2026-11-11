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
    welcome_open: str = "Abrir otro proyecto…"
    recent_title: str = "Sus proyectos"
    recent_empty: str = "Todavía no hay proyectos. Empiece creando uno nuevo."
    recent_item: str = "{name}\n{use} · creado el {date}"
    recent_hint: str = "Doble clic para abrir."
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
        "Revise lo que encontró el sistema y corrija lo necesario. Las salidas en línea "
        "discontinua son propuestas: haga doble clic sobre ellas para confirmarlas. Clic derecho "
        "sobre un elemento para más opciones. En edificios de varios pisos, dibuje cada escalera "
        "en todos los pisos que une."
    )
    detect: str = "Detectar automáticamente"
    detecting: str = "Buscando muros y puertas… esto puede tardar unos segundos."
    detect_done: str = (
        "Se encontraron {walls} muros, {doors} puertas y {exits} salidas propuestas. "
        "Revise y corrija lo necesario."
    )
    no_image: str = "Primero cargue un plano en el paso 1."
    step_not_ready: str = "Este paso todavía no está disponible."


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
    confirm_all: str = "Confirmar todas"
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
    hint_select: str = (
        "Clic: seleccionar. Doble clic en una salida propuesta: confirmarla. Clic derecho: más "
        "opciones. Supr: borrar."
    )
    hint_segment: str = "Arrastre para dibujar. Mantenga Mayús para líneas rectas."
    hint_area: str = "Arrastre para dibujar un rectángulo."
    hint_zoom: str = "Rueda del mouse: acercar o alejar. Botón central: desplazar."
    tip_select: str = "Seleccionar elementos. Clic derecho sobre uno para más opciones."
    tip_wall: str = "Dibujar un muro: arrastre de un extremo al otro."
    tip_door: str = "Marcar una puerta: arrastre sobre el muro; se encaja sola y abre el hueco."
    tip_exit: str = "Marcar una salida al exterior: arrastre sobre un muro exterior."
    tip_stair: str = "Marcar una escalera: arrastre un rectángulo."
    tip_obstacle: str = "Marcar un mueble u obstáculo que no se puede atravesar."
    tip_safe_zone: str = "Marcar una zona segura (patio, explanada) a la que se puede evacuar."
    tip_shortcut: str = "{tip}\nAtajo: {key}"
    legend_title: str = "Leyenda y capas"
    legend_dashed: str = "Línea discontinua: salida propuesta, falta confirmarla."
    legend_low: str = "Naranja: detectado con poca seguridad; revíselo."
    menu_confirm: str = "Confirmar salida"
    menu_rename: str = "Cambiar nombre…"
    menu_delete: str = "Borrar"
    rename_title: str = "Cambiar nombre"
    rename_label: str = "Nombre:"
    name_empty: str = "Escriba un nombre."
    name_in_use: str = "Ya existe otro elemento llamado «{name}» en este piso."
    cmd_rename: str = "Cambiar nombre a «{name}»"
    pending_exits: str = "Hay {count} salida(s) propuesta(s) por confirmar."
    exit_name: str = "Salida {number}"
    proposed_suffix: str = " (por confirmar)"
    stair_name: str = "Escalera {letter}"
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
    card_total: str = "Tiempo total"
    card_ninety: str = "90 % evacuado"
    card_evacuated: str = "Personas evacuadas"
    card_evacuated_value: str = "{done} de {total}"
    note_all_out: str = "Salieron todas las personas."
    note_left: str = "Quedaron {left} persona(s) dentro."
    note_congestion: str = "{count} zona(s) con congestión."
    note_no_congestion: str = "Sin congestión sostenida."
    note_ninety: str = "Momento en que salió el 90 % de las personas."
    per_exit_title: str = "Tiempo por salida"
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
    pending_exits: str = (
        "Hay {count} salida(s) propuesta(s) sin confirmar: se tratarán como cerradas. Si son "
        "salidas reales, confírmelas en el paso 3."
    )


@dataclass(frozen=True, slots=True)
class GuideTexts:
    """Guía del asistente: navegación, «Qué falta» y mensajes."""

    app_subtitle: str = "Evacuación ante sismos"
    previous: str = "‹ Anterior"
    next: str = "Siguiente ›"
    step_of: str = "Paso {number} de {total}: {name}"
    go_to: str = "Ir al paso {number}"
    before_step: str = "Antes de este paso (paso {number}): {issue}"
    missing: str = "Qué falta: {issue}"
    review: str = "Para revisar: {issue}"
    step_done: str = "Este paso está completo. Puede seguir con «{next}»."
    step_done_last: str = "Este paso está completo."
    norms_observations: str = (
        "Para revisar: hay {count} observación(es) normativa(s) abajo, cada una con su "
        "recomendación. Puede simular igual y corregir después."
    )
    issues: tuple[tuple[str, str], ...] = (
        ("sin_imagen", "cargue la foto o el PDF del plano del local."),
        ("sin_escala", "defina la escala: dibuje una línea sobre una medida que conozca."),
        ("sin_muros", "dibuje los muros del plano o use «Detectar automáticamente»."),
        (
            "sin_salidas",
            "marque al menos una salida (confirmada) o una zona segura. Dibuje la salida sobre "
            "un muro exterior con la herramienta Salida.",
        ),
        (
            "salidas_por_confirmar",
            "hay salidas propuestas sin confirmar; se tratarán como cerradas. Confírmelas con "
            "doble clic o con «Confirmar todas».",
        ),
        ("sin_ambientes", "marque los ambientes del local (detectarlos o dibujarlos)."),
        ("sin_ocupantes", "indique cuántas personas hay en cada ambiente."),
        ("sin_simulacion", "pulse «Simular» para ver cómo se evacúa el local."),
        (
            "simulacion_incompleta",
            "en la última simulación no salieron todas las personas. Revise las salidas y "
            "puertas en el paso 3.",
        ),
    )

    def issue_text(self, code: str) -> str:
        """Texto de un faltante (por su código)."""
        return dict(self.issues).get(code, code)


@dataclass(frozen=True, slots=True)
class FloorTexts:
    """Selector de pisos (RF12)."""

    label: str = "Piso:"
    name: str = "Piso {number}"
    add: str = "+ Agregar piso"
    delete: str = "Eliminar este piso"
    confirm_delete: str = "¿Eliminar el {name} con su plano, ambientes y ocupantes?"
    max_floors: str = "RutaSegura trabaja con edificios de hasta 4 pisos."
    cannot_delete: str = "Solo se puede eliminar el piso más alto, y nunca el piso 1."
    added: str = (
        "Se agregó el {name}. Cargue su plano (paso 1) y dibuje la escalera en el mismo lugar "
        "que en el piso de abajo, con el mismo nombre."
    )


@dataclass(frozen=True, slots=True)
class ScenarioTexts:
    """Escenarios «qué pasa si» y comparador (RF10)."""

    label: str = "Escenario:"
    new: str = "Nuevo escenario…"
    edit: str = "Editar…"
    delete: str = "Eliminar"
    compare: str = "Comparar escenarios…"
    dialog_new_title: str = "Nuevo escenario «qué pasa si»"
    dialog_edit_title: str = "Editar escenario"
    name: str = "Nombre:"
    occupancy: str = "Ocupación respecto del escenario base:"
    occupancy_result: str = "= {count} personas (el escenario base tiene {base})."
    blocked: str = "Salidas bloqueadas en este escenario:"
    no_exits: str = "El plano no tiene salidas confirmadas."
    base_hint: str = (
        "Las personas del escenario base se indican en el paso 4. Los demás escenarios copian "
        "esa ocupación con el porcentaje elegido."
    )
    confirm_delete: str = "¿Eliminar el escenario «{name}» y sus simulaciones?"
    compare_title: str = "Comparar escenarios"
    compare_need_two: str = "Simule al menos dos escenarios para poder compararlos."
    play_both: str = "▶ Reproducir ambos"
    metric: str = "Indicador"
    difference: str = "Diferencia (B − A)"
    row_people: str = "Personas"
    row_blocked: str = "Salidas bloqueadas"
    row_total: str = "Tiempo total de evacuación"
    row_half: str = "Tiempo para evacuar al 50 %"
    row_ninety: str = "Tiempo para evacuar al 90 %"
    row_evacuated: str = "Evacuados"
    row_bottlenecks: str = "Cuellos de botella"
    row_exit: str = "Tiempo por «{name}»"
    none: str = "Ninguna"
    not_used: str = "sin uso"


@dataclass(frozen=True, slots=True)
class CalibrationTexts:
    """Registro de simulacro real y calibración (RF11)."""

    menu_tools: str = "&Herramientas"
    menu_calibrate: str = "&Calibrar con un simulacro real…"
    title: str = "Calibrar con un simulacro real"
    help: str = (
        "Registre los datos de un simulacro de su local. El sistema prueba distintos tiempos de "
        "reacción y velocidades hasta que la simulación se parezca a lo que ocurrió."
    )
    date: str = "Fecha del simulacro:"
    participants: str = "Personas que participaron:"
    total_time: str = "Tiempo total (hasta que salió la última persona):"
    per_exit: str = "Tiempo de la última persona por cada salida (opcional, 0 = no medido):"
    minutes: str = " min"
    seconds: str = " s"
    run: str = "Calibrar"
    missing_time: str = "Indique el tiempo total que duró el simulacro."
    cancel: str = "Cancelar"
    running: str = "Probando combinaciones… {percent:.0f} %"
    cancelled: str = "Calibración cancelada."
    result: str = (
        "Error en el tiempo total: antes {before:.0%}, después {after:.0%} (meta: menos de 20 %).\n"
        "Tiempos de reacción × {reaction:g} · Velocidades × {speed:g}\n"
        "Tiempo simulado: {simulated} · Tiempo real: {observed}"
    )
    target_met: str = "Se cumple la meta de validación."
    target_missed: str = (
        "No se alcanzó la meta: revise los datos del simulacro, la ocupación del paso 4 o el plano."
    )
    apply: str = "Aplicar a los perfiles"
    applied: str = (
        "Listo: los perfiles se ajustaron. Vuelva a simular para ver los tiempos calibrados."
    )
    close: str = "Cerrar"
    no_project: str = "Primero abra un proyecto con plano, escala y ocupantes."


@dataclass(frozen=True, slots=True)
class NormsTexts:
    """Paso 5: revisar norma."""

    title: str = "Paso 5. Revisar norma"
    help: str = (
        "Para cada ambiente se calcula el aforo (cuántas personas puede recibir) según su "
        "categoría, y se revisan los anchos de puertas, salidas y pasillos. Elija la categoría "
        "que mejor describa el uso de cada ambiente."
    )
    column_name: str = "Ambiente"
    column_category: str = "Categoría"
    column_area: str = "Área (m²)"
    column_capacity: str = "Aforo"
    column_occupants: str = "Ocupantes"
    column_status: str = "Estado"
    status_ok: str = "Correcto"
    status_exceeded: str = "Excede el aforo"
    status_no_capacity: str = "Sin aforo propio"
    total: str = "Aforo total: {capacity} personas · Ocupantes asignados: {occupants}"
    observations_title: str = "Observaciones normativas"
    no_observations: str = "No se encontraron incumplimientos con las reglas usadas."
    observation: str = "{description}\n{citation}"
    unverified_tag: str = " · regla no verificada"
    unverified_warning: str = (
        "Atención: {count} regla(s) usada(s) todavía no fueron verificadas con el texto oficial "
        "del RNE. Los resultados son orientativos hasta confirmarlas."
    )
    no_scale: str = "Primero defina la escala del plano (paso 2)."


@dataclass(frozen=True, slots=True)
class ReportTexts:
    """Paso 7: informe PDF."""

    title: str = "Paso 7. Informe"
    help: str = (
        "Genere un informe PDF con el tiempo estimado de evacuación, el mapa de calor, los "
        "cuellos de botella, el aforo y las observaciones normativas, para compartirlo con su "
        "comité o brigada."
    )
    generate: str = "Generar informe PDF…"
    generating: str = "Generando el informe…"
    open: str = "Abrir informe"
    save_title: str = "Guardar informe"
    save_filter: str = "Documento PDF (*.pdf)"
    default_name: str = "Informe de evacuación - {name}.pdf"
    saved: str = "Informe guardado en:\n{path}"
    no_run: str = (
        "Todavía no simuló la evacuación: el informe no incluirá tiempos ni mapa de calor. "
        "Puede simular en el paso 6."
    )
    ready: str = "El informe incluirá la última simulación guardada."


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
    norms: NormsTexts = field(default_factory=NormsTexts)
    scenarios: ScenarioTexts = field(default_factory=ScenarioTexts)
    floors: FloorTexts = field(default_factory=FloorTexts)
    guide: GuideTexts = field(default_factory=GuideTexts)
    calibration: CalibrationTexts = field(default_factory=CalibrationTexts)
    report: ReportTexts = field(default_factory=ReportTexts)


SPANISH = UiTexts(
    app_name="RutaSegura",
    window_title="RutaSegura — Simulación de evacuación",
    welcome_title="Bienvenido a RutaSegura",
    welcome_body=(
        "Con RutaSegura puede revisar si las personas de su local pueden salir a tiempo "
        "durante un sismo. Le guiaremos paso a paso, desde la foto del plano hasta el informe."
    ),
    wizard_steps=(
        "Cargar plano",
        "Escala",
        "Corregir plano",
        "Ambientes y ocupantes",
        "Revisar norma",
        "Simular",
        "Informe",
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
