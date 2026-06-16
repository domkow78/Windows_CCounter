"""
Fabryka czujników - wybiera odpowiednią implementację na podstawie konfiguracji
"""

import logging
from typing import Union, Literal

from .inductive_sensor import InductiveSensor
from .automation_hat_sensor import AutomationHATSensor

logger = logging.getLogger(__name__)


def create_sensor(
    backend: Literal["gpio", "automationhat"] = "gpio",
    **kwargs
) -> Union[InductiveSensor, AutomationHATSensor]:
    """
    Fabryka do tworzenia czujnika na podstawie wybranego backendu.
    
    Args:
        backend: Typ backendu sprzętowego ("gpio" lub "automationhat")
        **kwargs: Dodatkowe argumenty przekazane do konstruktora czujnika
        
    Returns:
        Instancja InductiveSensor lub AutomationHATSensor
        
    Raises:
        ValueError: Jeśli backend nie jest rozpoznany
        
    Examples:
        # Czujnik GPIO
        sensor = create_sensor("gpio", gpio_pin=17, debounce_ms=50)
        
        # Czujnik Automation HAT
        sensor = create_sensor("automationhat", automation_hat_input="one", debounce_ms=50)
    """
    if backend == "gpio":
        logger.info("Inicjalizacja czujnika GPIO")
        return InductiveSensor(**kwargs)
    
    elif backend == "automationhat":
        logger.info("Inicjalizacja czujnika Automation HAT Mini")
        return AutomationHATSensor(**kwargs)
    
    else:
        raise ValueError(
            f"Nieznany backend: {backend}. "
            f"Dostępne opcje: 'gpio', 'automationhat'"
        )


def create_sensor_from_config(config: dict) -> Union[InductiveSensor, AutomationHATSensor]:
    """
    Fabryka do tworzenia czujnika na podstawie słownika konfiguracji.
    
    Args:
        config: Słownik zawierający konfigurację (z pliku config.yaml)
               Oczekuje kluczy: sensor.hardware_backend, sensor.gpio_pin, etc.
        
    Returns:
        Instancja InductiveSensor lub AutomationHATSensor
        
    Example:
        config = yaml.safe_load(open("config.yaml"))
        sensor = create_sensor_from_config(config["sensor"])
    """
    sensor_config = config or {}
    backend = sensor_config.get("hardware_backend", "gpio")
    
    # Przygotuj argumenty na podstawie backendu
    if backend == "gpio":
        kwargs = {
            "gpio_pin": sensor_config.get("gpio_pin", 17),
            "debounce_ms": sensor_config.get("debounce_ms", 50),
            "pull_up": sensor_config.get("pull_up", True),
            "active_low": sensor_config.get("active_low", True),
            "simulation_mode": sensor_config.get("simulation_mode", False),
        }
    
    elif backend == "automationhat":
        kwargs = {
            "input_name": sensor_config.get("automation_hat_input", "one"),
            "debounce_ms": sensor_config.get("debounce_ms", 50),
            "active_low": sensor_config.get("active_low", True),
            "simulation_mode": sensor_config.get("simulation_mode", False),
        }
    
    else:
        raise ValueError(
            f"Nieznany backend: {backend}. "
            f"Dostępne opcje: 'gpio', 'automationhat'"
        )
    
    return create_sensor(backend, **kwargs)
