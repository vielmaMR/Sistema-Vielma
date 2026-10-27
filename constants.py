"""Constantes centrales: roles, estados, tipos de trabajo y vehículo.

Centralizar aquí permite que el catálogo sea administrable y que las
validaciones de transición sean coherentes en todo el backend.
"""

# --- Roles ---
ROLE_JEFE = "jefe"
ROLE_EMPLEADO = "empleado"
ROLES = (ROLE_JEFE, ROLE_EMPLEADO)

# --- Estados de la orden ---
ST_SOLICITADO = "solicitado"
ST_ESPERA_APROBACION = "espera_aprobacion"
ST_APROBADO_CLIENTE = "aprobado_cliente"
ST_RECHAZADO_CLIENTE = "rechazado_cliente"
ST_CONFIRMADO = "confirmado"            # Confirmado por el jefe / pendiente de inicio
ST_EN_TRABAJO = "en_trabajo"
ST_PAUSADO = "pausado"
ST_FINALIZADO = "finalizado"
ST_ENTREGADO = "entregado"              # Entregado / cerrado
ST_CANCELADO = "cancelado"

# Etiquetas legibles para la interfaz.
STATUS_LABELS = {
    ST_SOLICITADO: "Solicitado",
    ST_ESPERA_APROBACION: "En espera de aprobación",
    ST_APROBADO_CLIENTE: "Aprobado por cliente",
    ST_RECHAZADO_CLIENTE: "Rechazado por cliente",
    ST_CONFIRMADO: "Confirmado / Pendiente de inicio",
    ST_EN_TRABAJO: "En trabajo",
    ST_PAUSADO: "Pausado",
    ST_FINALIZADO: "Finalizado",
    ST_ENTREGADO: "Entregado / Cerrado",
    ST_CANCELADO: "Cancelado",
}

# Clase CSS (color de etiqueta) por estado.
STATUS_CSS = {
    ST_SOLICITADO: "st-solicitado",
    ST_ESPERA_APROBACION: "st-espera",
    ST_APROBADO_CLIENTE: "st-aprobado",
    ST_RECHAZADO_CLIENTE: "st-rechazado",
    ST_CONFIRMADO: "st-confirmado",
    ST_EN_TRABAJO: "st-trabajo",
    ST_PAUSADO: "st-pausado",
    ST_FINALIZADO: "st-finalizado",
    ST_ENTREGADO: "st-entregado",
    ST_CANCELADO: "st-cancelado",
}

# Estados que se consideran "cerrados" (no acumulan tiempo de trabajo).
CLOSED_STATES = {ST_ENTREGADO, ST_CANCELADO, ST_RECHAZADO_CLIENTE}
# Estados que cuentan como trabajo efectivamente completado.
COMPLETED_STATES = {ST_FINALIZADO, ST_ENTREGADO}

# Transiciones permitidas: estado_actual -> {estados_destino}
ALLOWED_TRANSITIONS = {
    ST_SOLICITADO: {ST_ESPERA_APROBACION, ST_CONFIRMADO, ST_CANCELADO},
    ST_ESPERA_APROBACION: {ST_APROBADO_CLIENTE, ST_RECHAZADO_CLIENTE, ST_CANCELADO},
    ST_APROBADO_CLIENTE: {ST_CONFIRMADO, ST_ESPERA_APROBACION, ST_CANCELADO},
    ST_RECHAZADO_CLIENTE: {ST_ESPERA_APROBACION, ST_CANCELADO},
    ST_CONFIRMADO: {ST_EN_TRABAJO, ST_CANCELADO},
    ST_EN_TRABAJO: {ST_PAUSADO, ST_FINALIZADO, ST_CANCELADO},
    ST_PAUSADO: {ST_EN_TRABAJO, ST_FINALIZADO, ST_CANCELADO},
    ST_FINALIZADO: {ST_ENTREGADO, ST_EN_TRABAJO},  # reapertura auditada a En trabajo
    ST_ENTREGADO: {ST_FINALIZADO},                 # reapertura auditada
    ST_CANCELADO: set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


# --- Tipos de vehículo ---
VH_MOTO = "moto"
VH_AUTO = "auto"
VH_MOTOCARRO = "motocarro"
VEHICLE_TYPES = {
    VH_MOTO: "Moto",
    VH_AUTO: "Auto",
    VH_MOTOCARRO: "Motocarro",
}

# --- Tipos de trabajo ---
WORK_TYPES = [
    ("mantenimiento", "Mantenimiento"),
    ("transmision", "Transmisión"),
    ("parte_electrica", "Parte eléctrica"),
    ("cambio_rulemanes", "Cambio de rulemanes"),
    ("gomeria", "Gomería"),
    ("freno", "Cambio/mantenimiento de freno"),
    ("cambio_aceite", "Cambio de aceite"),
    ("estirado_cadena", "Estirado de cadena"),
    ("otro", "Otro"),
]
WORK_TYPE_LABELS = dict(WORK_TYPES)
DEFAULT_WORK_TYPE = "mantenimiento"

# Motivos frecuentes de pausa (campo libre también permitido).
PAUSE_REASONS = [
    "Espera de repuesto",
    "Consulta al cliente",
    "Fin de jornada",
    "Otra tarea prioritaria",
    "Almuerzo / descanso",
    "Otro",
]
