"""Registry for storing loaded models in memory"""

_models = {}

def set_model(name, model):
    """Store a model in the registry"""
    _models[name] = model

def get_model(name):
    """Retrieve a model from the registry"""
    model = _models.get(name)
    if name == 'layoutlm':
        print(f"[DEBUG] get_model('{name}'): {type(model).__name__ if model else 'None'}, registry keys: {list(_models.keys())}")
    return model

def get_all_models():
    """Get all registered models"""
    return _models

def clear_models():
    """Clear all registered models"""
    _models.clear()
