class AbilityMicrokernel:
    """Microkernel encargado de gestionar y validar las reglas y habilidades del juego."""
    
    def __init__(self):
        # Registro centralizado de habilidades (actúa como el motor de reglas / plugins)
        self._registry = {
            "HAB-000": {"nombre": "Habilidad Base", "tipo": "Neutral", "efecto": "Estándar"},
            "HAB-001": {"nombre": "Llamarada", "tipo": "Fuego", "efecto": "Daño de área"},
            "HAB-002": {"nombre": "Impactrueno", "tipo": "Rayo", "efecto": "Probabilidad de parálisis"}
        }

    def validar_habilidad(self, codigo: str) -> bool:
        """Verifica si el código de habilidad existe en el registro del Microkernel."""
        return codigo in self._registry

    def registrar_plugin_habilidad(self, codigo: str, metadata: dict):
        """Permite extender el Microkernel cargando dinámicamente nuevas habilidades."""
        self._registry[codigo] = metadata

# Instancia global del motor (Microkernel Core)
ability_engine = AbilityMicrokernel()