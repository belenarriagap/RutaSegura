"""Textos de la interfaz, centralizados (preparado para traducción; por ahora solo español).

Para traducir: crear otra instancia de ``UiTexts`` y elegirla al iniciar la aplicación.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UiTexts:
    """Catálogo de textos visibles para el usuario."""

    app_name: str
    window_title: str
    welcome_title: str
    welcome_body: str
    wizard_steps: tuple[str, ...]
    menu_file: str
    menu_help: str
    action_quit: str
    action_about: str
    about_title: str
    about_body: str
    status_ready: str
    legal_disclaimer: str


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
