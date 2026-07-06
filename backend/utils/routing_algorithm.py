from datetime import datetime, timezone
from typing import List, Dict, Optional

def calculate_technician_workload(active_tickets: List[Dict]) -> int:
    """
    Calcula la carga multiplicando sus tickets activos por prioridad:
    - Baja = 1 punto
    - Media = 2 puntos
    - Alta = 3 puntos
    - Crítica = 3 puntos (Mapeado a 3 según el requerimiento de 3 niveles)
    """
    score = 0
    for t in active_tickets:
        prio = t.get("prioridad", "Baja")
        if prio == "Baja":
            score += 1
        elif prio == "Media":
            score += 2
        elif prio in ["Alta", "Crítica"]:
            score += 3
        else:
            score += 1
    return score

def select_best_technician(technicians: List[Dict], active_tickets: List[Dict]) -> Optional[Dict]:
    """
    Selecciona al técnico activo con menor carga ponderada de trabajo.
    Ante un empate, usa la estampa de tiempo más lejana desde su última asignación.
    """
    if not technicians:
        return None
        
    tech_scores = []
    for tech in technicians:
        tech_id_str = str(tech["_id"])
        # Filtrar tickets activos para este técnico específico (Asignado / En Proceso)
        tech_tickets = [
            t for t in active_tickets 
            if t.get("assigned_tech_id") == tech_id_str and t.get("status") in ["Asignado", "En Proceso"]
        ]
        score = calculate_technician_workload(tech_tickets)
        
        last_assign_date = tech.get("ultima_asignacion_at")
        if last_assign_date is None:
            # retroceso al inicio de la época (tiempo más antiguo posible)
            last_assign_date = datetime.fromtimestamp(0, tz=timezone.utc)
            
        # Garantía comparaciones que tengan en cuenta la zona horaria (trabaje siempre con UTC)
        if last_assign_date.tzinfo is None:
            last_assign_date = last_assign_date.replace(tzinfo=timezone.utc)
            
        tech_scores.append((score, last_assign_date, tech))
        
    # Ordenar: puntuación más baja primero (primaria), fecha de asignación más antigua primero (secundaria)
    tech_scores.sort(key=lambda x: (x[0], x[1]))
    return tech_scores[0][2]