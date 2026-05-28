"""Global model registry - stores loaded AI models for reuse across the application."""

_registry = {}


def set_model(name: str, instance):
    """Register a loaded model instance."""
    _registry[name] = instance


def get_model(name: str):
    """Retrieve a registered model instance."""
    return _registry.get(name)


def get_all_models():
    """Get all registered models."""
    return _registry.copy()


def clear_registry():
    """Clear all registered models (for cleanup/testing)."""
    _registry.clear()
