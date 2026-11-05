"""Marcadores locales para no modificar la configuración global de pytest."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "comportamiento_preservado: conducta vigente que debe sobrevivir la migración.",
    )
    config.addinivalue_line(
        "markers",
        "defecto_caracterizado: defecto vigente reproducido, sin aprobarlo como contrato futuro.",
    )
