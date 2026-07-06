SLA_MATRIX = {
    "Oro": {
        "Baja": 120,      # 2 horas
        "Media": 60,      # 1 hora
        "Alta": 30,       # 30 minutos (requisito estricto RF-024)
        "Crítica": 30     # 30 minutos
    },
    "Plata": {
        "Baja": 240,      # 4 horas
        "Media": 120,     # 2 horas
        "Alta": 60,       # 1 hora
        "Crítica": 60     # 1 hora
    },
    "Bronce": {
        "Baja": 480,      # 8 horas
        "Media": 240,     # 4 horas
        "Alta": 120,      # 2 horas
        "Crítica": 120     # 2 horas
    }
}

def get_sla_window(nivel_soporte: str, prioridad: str) -> int:
    """
    Retrieves the maximum resolution window in minutes based on
    the client organization's contract tier and ticket priority.
    """
    tier = SLA_MATRIX.get(nivel_soporte, SLA_MATRIX["Bronce"])
    return tier.get(prioridad, tier["Baja"])