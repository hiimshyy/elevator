"""Domain-specific exceptions."""


class ElevatorNotFoundError(Exception):
    """Raised when an elevator ID does not exist."""
    pass


class SensorUnavailableError(Exception):
    """Raised when a sensor cannot be reached on the Modbus bus."""
    pass


class ModelNotLoadedError(Exception):
    """Raised when an ONNX model file is missing or corrupt."""
    pass


class SensorDataInvalidError(Exception):
    """Raised when sensor readings are outside expected physical range."""
    pass


class AlertRateLimitError(Exception):
    """Raised when an alert is suppressed due to rate limiting."""
    pass
