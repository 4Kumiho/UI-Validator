"""Models package - AI model loading and registry."""

from Models.model_registry import set_model, get_model, get_all_models, clear_registry

__all__ = ["set_model", "get_model", "get_all_models", "clear_registry"]
