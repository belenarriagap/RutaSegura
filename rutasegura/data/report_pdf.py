"""Generador del informe PDF (RF09) con ReportLab y gráficos de Matplotlib (backend Agg).

Las fuentes (DejaVu Sans) se toman de la instalación local de Matplotlib y se incrustan en el
PDF: no se descarga nada.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np
import numpy.typing as npt
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from rutasegura.domain.norms import NormEvaluation
from rutasegura.domain.people import PersonProfile
from rutasegura.domain.plan import FloorPlan
from rutasegura.domain.project import Project
from rutasegura.domain.results import Observation, SimulationResult
from rutasegura.domain.scenario import Scenario

FONT = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
ACCENT = colors.HexColor("#1f3a93")
WARNING_BG = colors.HexColor("#fdebd0")
USE_LABELS = {"educacion": "Educación", "oficinas": "Oficinas", "comercio": "Comercio"}


@dataclass(frozen=True)
class ScenarioRow:
    """Fila de la comparación de escenarios."""

    name: str
    occupants: int
    blocked_exits: tuple[str, ...]
    total_time_s: float
    time_90_s: float | None
    evacuated: int
    agents: int
    completed: bool
    bottlenecks: int


@dataclass(frozen=True, eq=False)
class ReportContent:
    """Todo lo que va en el informe."""

    project: Project
    plan: FloorPlan
    plan_image: npt.NDArray[np.uint8] | None
    scenario: Scenario
    norms: NormEvaluation
    result: SimulationResult | None
    congestion: tuple[Observation, ...]
    profiles: tuple[PersonProfile, ...]
    provisional_profiles: tuple[str, ...]
    parameters: tuple[tuple[str, str], ...]
    legal_disclaimer: str
    app_version: str
    comparison: tuple[ScenarioRow, ...] = ()
    # Varios pisos: (plano, imagen) de cada piso, del más bajo al más alto.
    floors: tuple[tuple[FloorPlan, npt.NDArray[np.uint8] | None], ...] = ()
    generated_at: datetime = field(default_factory=datetime.now)


def _register_fonts() -> None:
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    folder = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont(FONT, str(folder / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(folder / "DejaVuSans-Bold.ttf")))


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName=FONT, fontSize=9.5, leading=13)
    return {
        "body": body,
        "small": ParagraphStyle("small", parent=body, fontSize=8, leading=10),
        "title": ParagraphStyle(
            "title", parent=body, fontName=FONT_BOLD, fontSize=24, leading=30, alignment=TA_CENTER
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=body, fontSize=13, leading=18, alignment=TA_CENTER
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=body,
            fontName=FONT_BOLD,
            fontSize=15,
            leading=20,
            textColor=ACCENT,
            spaceBefore=6,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=body,
            fontName=FONT_BOLD,
            fontSize=11.5,
            leading=15,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "warning": ParagraphStyle(
            "warning",
            parent=body,
            backColor=WARNING_BG,
            borderColor=colors.HexColor("#e67e22"),
            borderWidth=1,
            borderPadding=6,
            spaceBefore=6,
            spaceAfter=10,
        ),
    }


def format_duration(seconds: float) -> str:
    """Segundos → «2 min 35 s»."""
    minutes, secs = divmod(round(max(0.0, seconds)), 60)
    return f"{minutes} min {secs:02d} s" if minutes else f"{secs} s"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _table(
    rows: Sequence[Sequence[str]], widths: Sequence[float], styles: dict[str, ParagraphStyle]
) -> Table:
    cells = [[Paragraph(_escape(c), styles["small"]) for c in row] for row in rows]
    table = Table(cells, colWidths=list(widths), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d6dbf0")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9aa4c8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fb")]),
            ]
        )
    )
    return table


def _figure_image(fig: Figure, width_cm: float) -> Image:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")  # Figure sin pyplot: usa el lienzo Agg
    buffer.seek(0)
    w, h = fig.get_size_inches()
    return Image(buffer, width=width_cm * cm, height=width_cm * cm * h / w)


# ---------------------------------------------------------------------------- gráficos


def heatmap_figure(content: ReportContent, level: int | None = None) -> Figure | None:
    """Plano en gris + mapa de calor de densidad + numeración de cuellos de botella.

    ``level`` elige el piso (por defecto, el más bajo).
    """
    result = content.result
    if result is None:
        return None
    floors = dict((p.level, (p, img)) for p, img in content.floors) or {
        content.plan.level: (content.plan, content.plan_image)
    }
    maps = {m.level: m for m in result.maps()}
    if level is None:
        level = min(floors)
    plan, plan_image = floors.get(level, (content.plan, content.plan_image))
    floor_map = maps.get(level) if result.floor_maps else result.maps()[0]
    scale = plan.scale_m_per_px
    if scale is None or floor_map is None:
        return None
    fig = Figure(figsize=(7.5, 5.2), dpi=150)
    ax = fig.add_subplot()
    if plan_image is not None:
        h, w = plan_image.shape[:2]
        gray = plan_image.mean(axis=2) if plan_image.ndim == 3 else plan_image
        ax.imshow(gray, cmap="gray", extent=(0, w * scale, h * scale, 0), alpha=0.55)
    density = np.ma.masked_less_equal(floor_map.density_map, 0.0)
    rows, cols = floor_map.density_map.shape
    x0, y0 = floor_map.grid_origin_m
    size = floor_map.cell_size_m
    image = ax.imshow(
        density,
        cmap="YlOrRd",
        extent=(x0, x0 + cols * size, y0 + rows * size, y0),
        alpha=0.75,
        interpolation="nearest",
    )
    for rank, bottleneck in enumerate(result.bottlenecks[:5], start=1):
        if result.floor_maps and bottleneck.level != level:
            continue
        ax.annotate(
            str(rank),
            (bottleneck.location.x, bottleneck.location.y),
            ha="center",
            va="center",
            fontsize=9,
            fontweight="bold",
            color="white",
            bbox={"boxstyle": "circle,pad=0.25", "fc": "#1f3a93", "ec": "white"},
        )
    ax.set_xlabel("metros")
    ax.set_ylabel("metros")
    ax.set_aspect("equal")
    cbar = fig.colorbar(image, ax=ax, shrink=0.8)
    cbar.set_label("Densidad acumulada (personas·s/m²)")
    fig.tight_layout()
    return fig


def curve_figure(result: SimulationResult) -> Figure:
    """Curva de personas evacuadas vs. tiempo."""
    fig = Figure(figsize=(7.5, 3.4), dpi=150)
    ax = fig.add_subplot()
    ax.step(result.curve_times_s, result.curve_evacuated, where="post", color="#1f3a93")
    ax.axhline(result.agents_total, color="#7f8c8d", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Personas evacuadas")
    ax.set_ylim(0, max(1, result.agents_total) * 1.05)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------- informe


def write_report(path: Path, content: ReportContent) -> None:
    """Genera el PDF en ``path``."""
    _register_fonts()
    s = _styles()
    story: list[Flowable] = []
    project = content.project
    result = content.result
    norms = content.norms
    unverified = norms.unverified_rules

    # ------------------------------------------------------------------ portada
    story += [
        Spacer(1, 4 * cm),
        Paragraph("Informe de evacuación ante sismo", s["title"]),
        Spacer(1, 0.6 * cm),
        Paragraph(_escape(project.name), s["subtitle"]),
        Paragraph(_escape(project.address or "Dirección no registrada"), s["subtitle"]),
        Paragraph(f"Uso: {USE_LABELS.get(project.use.value, project.use.value)}", s["subtitle"]),
        Spacer(1, 1.5 * cm),
        Paragraph(
            f"Fecha del informe: {content.generated_at.strftime('%d/%m/%Y %H:%M')}<br/>"
            f"Generado con RutaSegura {content.app_version}, sin conexión a internet.",
            s["body"],
        ),
        Spacer(1, 1 * cm),
        Paragraph(f"<b>Aclaración legal.</b> {_escape(content.legal_disclaimer)}", s["warning"]),
        PageBreak(),
    ]

    # ------------------------------------------------------------------ resumen
    story.append(Paragraph("1. Resumen", s["h1"]))
    lines: list[str] = []
    if result is None:
        lines.append("Todavía no se ha simulado la evacuación de este local.")
    else:
        lines.append(
            f"<b>Tiempo total estimado de evacuación: {format_duration(result.total_time_s)}</b>"
        )
        lines.append(f"Personas evacuadas: {result.agents_evacuated} de {result.agents_total}.")
        if not result.completed:
            lines.append(
                "<b>Atención:</b> al terminar la simulación todavía quedaban personas dentro."
            )
        lines.append(f"Cuellos de botella detectados: {len(result.bottlenecks)}.")
    lines.append(
        f"Aforo calculado: {norms.total_capacity} personas. "
        f"Ocupantes asignados: {norms.total_occupants}."
    )
    lines.append(f"Observaciones normativas: {len(norms.observations)}.")
    story += [Paragraph(line, s["body"]) for line in lines]
    if unverified:
        story.append(
            Paragraph(
                f"<b>Advertencia:</b> este informe usó {len(unverified)} regla(s) normativa(s) "
                "que todavía no fueron contrastadas con el texto oficial del RNE (marcadas como "
                "«no verificada»). Sus valores y artículos deben confirmarse antes de usar estos "
                "resultados con fines formales. La lista está al final del informe.",
                s["warning"],
            )
        )

    # ------------------------------------------------------------------ aforo y normas
    story.append(Paragraph("2. Aforo y verificación normativa", s["h1"]))
    rows = [["Ambiente", "Categoría", "Área (m²)", "Aforo", "Ocupantes", "Estado"]]
    for cap in norms.capacities:
        status = "Excede el aforo" if cap.exceeded else "Correcto"
        rows.append(
            [
                cap.room_name,
                cap.category_label or cap.category,
                f"{cap.area_m2:.1f}",
                "—" if cap.capacity is None else str(cap.capacity),
                str(cap.occupants),
                "Sin aforo propio" if cap.capacity is None else status,
            ]
        )
    if len(rows) == 1:
        rows.append(["Sin ambientes marcados", "", "", "", "", ""])
    story.append(_table(rows, [4.2 * cm, 3.6 * cm, 2 * cm, 1.6 * cm, 2 * cm, 3 * cm], s))
    story.append(Paragraph("Observaciones normativas", s["h2"]))
    if not norms.observations:
        story.append(
            Paragraph("No se encontraron incumplimientos con las reglas usadas.", s["body"])
        )
    for i, obs in enumerate(norms.observations, start=1):
        tag = "" if obs.verified else " — <b>regla no verificada</b>"
        story.append(
            KeepTogether(
                [
                    Paragraph(f"<b>{i}.</b> {_escape(obs.description)}", s["body"]),
                    Paragraph(
                        f"Norma: {_escape(obs.norm or '')}, {_escape(obs.article or '')}{tag}",
                        s["small"],
                    ),
                    Paragraph(f"Recomendación: {_escape(obs.recommendation)}", s["small"]),
                    Spacer(1, 4),
                ]
            )
        )

    # ------------------------------------------------------------------ simulación
    story.append(Paragraph("3. Simulación de la evacuación", s["h1"]))
    if result is None:
        story.append(
            Paragraph("Simule la evacuación (paso 6) para completar esta sección.", s["body"])
        )
    else:
        levels = [p.level for p, _ in content.floors] or [content.plan.level]
        for level in levels:
            heat = heatmap_figure(content, level)
            if heat is None:
                continue
            title = "Mapa de calor de congestión"
            if len(levels) > 1:
                title += f" — Piso {level + 1}"
            story.append(
                KeepTogether(
                    [
                        Paragraph(title, s["h2"]),
                        _figure_image(heat, 16),
                        Paragraph(
                            "Las zonas rojas concentraron más personas en movimiento durante más "
                            "tiempo. Los números indican los cuellos de botella del ranking.",
                            s["small"],
                        ),
                    ]
                )
            )
        story.append(
            KeepTogether(
                [
                    Paragraph("Personas evacuadas a lo largo del tiempo", s["h2"]),
                    _figure_image(curve_figure(result), 16),
                ]
            )
        )
        if result.time_per_exit_s:
            exit_rows = [["Salida o zona segura", "Última persona en salir"]]
            exit_rows += [[name, format_duration(t)] for name, t in result.time_per_exit_s]
            story += [
                Paragraph("Tiempo por salida", s["h2"]),
                _table(exit_rows, [9 * cm, 5 * cm], s),
            ]
        story.append(Paragraph("Ranking de cuellos de botella", s["h2"]))
        if not content.congestion:
            story.append(Paragraph("No se detectaron zonas de congestión sostenida.", s["body"]))
        for i, obs in enumerate(content.congestion, start=1):
            story += [
                Paragraph(f"<b>{i}.</b> {_escape(obs.description)}", s["body"]),
                Paragraph(f"Recomendación: {_escape(obs.recommendation)}", s["small"]),
                Spacer(1, 4),
            ]

    # ------------------------------------------------------------------ comparación
    section = 4
    if len(content.comparison) >= 2:
        story.append(Paragraph(f"{section}. Comparación de escenarios", s["h1"]))
        story.append(
            Paragraph(
                "Última simulación de cada escenario «qué pasa si» del local. El tiempo total "
                "suele depender de la persona que reacciona más tarde; el tiempo para evacuar al "
                "90 % muestra mejor el efecto de bloquear salidas o cambiar el aforo.",
                s["body"],
            )
        )
        rows = [
            [
                "Escenario",
                "Personas",
                "Salidas bloqueadas",
                "Tiempo total",
                "Al 90 %",
                "Evacuados",
                "Cuellos",
            ]
        ]
        for row in content.comparison:
            evacuated = f"{row.evacuated} de {row.agents}" + (
                "" if row.completed else " (incompleto)"
            )
            rows.append(
                [
                    row.name,
                    str(row.occupants),
                    ", ".join(row.blocked_exits) or "Ninguna",
                    format_duration(row.total_time_s),
                    "—" if row.time_90_s is None else format_duration(row.time_90_s),
                    evacuated,
                    str(row.bottlenecks),
                ]
            )
        widths = [3.4 * cm, 1.7 * cm, 3 * cm, 2.2 * cm, 2 * cm, 2.6 * cm, 1.6 * cm]
        story.append(_table(rows, widths, s))
        section += 1

    # ------------------------------------------------------------------ parámetros
    story.append(Paragraph(f"{section}. Parámetros y semilla", s["h1"]))
    story.append(
        Paragraph(
            f"Escenario: {_escape(content.scenario.name)}. Semilla: {content.scenario.seed} "
            "(con la misma semilla y los mismos datos, la simulación da el mismo resultado).",
            s["body"],
        )
    )
    profile_rows = [
        ["Perfil", "Velocidad máx. (m/s)", "Reacción media (s)", "Desv. (s)", "Radio (m)"]
    ]
    for p in content.profiles:
        mark = " (provisional)" if p.name in content.provisional_profiles else ""
        profile_rows.append(
            [
                p.name + mark,
                f"{p.max_speed_mps:.2f}",
                f"{p.reaction_mean_s:.1f}",
                f"{p.reaction_std_s:.1f}",
                f"{p.radius_m:.2f}",
            ]
        )
    story += [
        Paragraph("Perfiles de personas", s["h2"]),
        _table(profile_rows, [4.6 * cm, 3.2 * cm, 3.2 * cm, 2.2 * cm, 2.2 * cm], s),
    ]
    param_rows = [["Parámetro del modelo", "Valor"], *[[k, v] for k, v in content.parameters]]
    story += [Paragraph("Modelo de movimiento", s["h2"]), _table(param_rows, [10 * cm, 5 * cm], s)]
    if content.provisional_profiles:
        story.append(
            Paragraph(
                "Los valores marcados como provisionales deben calibrarse con un simulacro real.",
                s["small"],
            )
        )

    # ------------------------------------------------------------------ reglas usadas
    story.append(Paragraph(f"{section + 1}. Reglas normativas usadas", s["h1"]))
    rule_rows = [["Regla", "Descripción", "Cita", "Estado"]]
    for rule in norms.rules_used:
        rule_rows.append(
            [
                rule.id,
                rule.description,
                rule.citation,
                "Verificada" if rule.verified else "No verificada",
            ]
        )
    story.append(_table(rule_rows, [4 * cm, 6.4 * cm, 3.6 * cm, 2.4 * cm], s))

    # ------------------------------------------------------------------ aclaración
    story += [
        Paragraph(f"{section + 2}. Aclaración legal", s["h1"]),
        Paragraph(_escape(content.legal_disclaimer), s["warning"]),
    ]

    footer = content.legal_disclaimer

    def decorate(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont(FONT, 6.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawCentredString(A4[0] / 2, 1.25 * cm, footer)
        canvas.drawRightString(A4[0] - 1.8 * cm, 0.8 * cm, f"Página {doc.page}")
        canvas.restoreState()

    path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=2 * cm,
        title=f"Informe de evacuación — {project.name}",
        author="RutaSegura",
    )
    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
