import pytest
from datetime import datetime, timezone, timedelta
from backend.utils.routing_algorithm import calculate_technician_workload, select_best_technician

def test_calculate_technician_workload():
    # Entradas: Baja=1, Media=2, Alta=3, Crítica=3
    tickets = [
        {"prioridad": "Baja"},
        {"prioridad": "Media"},
        {"prioridad": "Alta"},
        {"prioridad": "Crítica"},
        {"prioridad": "Inexistente"} # Por defecto a Baja (1)
    ]
    # Suma: 1 + 2 + 3 + 3 + 1 = 10
    score = calculate_technician_workload(tickets)
    assert score == 10

def test_select_best_technician_simple():
    techs = [
        {"_id": "tech1", "ultima_asignacion_at": datetime.now(timezone.utc) - timedelta(minutes=10)},
        {"_id": "tech2", "ultima_asignacion_at": datetime.now(timezone.utc) - timedelta(minutes=20)},
    ]
    
    # tech1 tiene 1 boleto de Alta (puntuación = 3)
    # tech2 tiene 2 entradas para la Baja (puntuación = 2)
    tickets = [
        {"assigned_tech_id": "tech1", "status": "Asignado", "prioridad": "Alta"},
        {"assigned_tech_id": "tech2", "status": "Asignado", "prioridad": "Baja"},
        {"assigned_tech_id": "tech2", "status": "En Proceso", "prioridad": "Baja"},
    ]
    
    best = select_best_technician(techs, tickets)
    assert best["_id"] == "tech2" # Menor carga de trabajo (2 vs 3)

def test_select_best_technician_tie_breaker():
    now = datetime.now(timezone.utc)
    techs = [
        {"_id": "tech1", "ultima_asignacion_at": now - timedelta(minutes=10)},
        {"_id": "tech2", "ultima_asignacion_at": now - timedelta(minutes=30)},
        {"_id": "tech3", "ultima_asignacion_at": None}, # respaldo más antiguo
    ]
    
    # Todos tienen la misma carga de trabajo (0)
    best = select_best_technician(techs, [])
    assert best["_id"] == "tech3"