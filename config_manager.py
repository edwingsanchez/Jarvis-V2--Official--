import os
import json
import logging

logger = logging.getLogger("config_manager")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "gemini_model": "gemini-3.5-flash",
    "tripo_api_key": "",
    "homeassistant_url": "http://localhost:8123",
    "homeassistant_token": "",
    "system_prompt": (
        "Eres J.A.R.V.I.S., la inteligencia artificial creada por Tony Stark. "
        "Respondes al usuario como 'Señor' o 'Creador' de manera sofisticada, servicial, "
        "un poco sarcástica pero siempre leal y eficiente. "
        "Usa un tono tecnológico y de asistente personal de alta tecnología."
    ),
    "apps": [
        {"name": "Image-to-model", "path": "[Integrada Nativamente]", "id": "image-to-model"},
        {"name": "Domotica", "path": "[Integrada Nativamente]", "id": "domotica"},
        {"name": "Iron Man", "path": "[Integrada Nativamente]", "id": "iron man"},
        {"name": "Satelites", "path": "[Integrada Nativamente]", "id": "satelites"},
        {"name": "Chrome", "path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"},
        {"name": "Blender", "path": ""}
    ]
}

def load_config():
    """Loads config from config.json. If it does not exist, creates it with default values."""
    if not os.path.exists(CONFIG_FILE):
        logger.info("Config file not found. Creating default configuration.")
        config = DEFAULT_CONFIG.copy()
        save_config(config)
        return config
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Merge default values if keys are missing (for backward compatibility)
        updated = False
        for k, v in DEFAULT_CONFIG.items():
            if k not in config:
                config[k] = v
                updated = True
                
        # Ensure native apps are in apps list and have IDs
        apps = config.get("apps", [])
        
        native_apps = [
            {"name": "Image-to-model", "id": "image-to-model"},
            {"name": "Domotica", "id": "domotica"},
            {"name": "Iron Man", "id": "iron man"},
            {"name": "Satelites", "id": "satelites"}
        ]
        
        for na in native_apps:
            # Try to match by ID first, then by name
            app_idx = -1
            for i, app in enumerate(apps):
                if app.get("id") == na["id"] or (not app.get("id") and app.get("name", "").lower() == na["name"].lower()):
                    app_idx = i
                    break
                    
            if app_idx == -1:
                # App is missing completely, insert it at the top
                idx = 0
                for i, app in enumerate(apps):
                    if app.get("id") in [n["id"] for n in native_apps]:
                        idx = i + 1
                apps.insert(idx, {"name": na["name"], "path": "[Integrada Nativamente]", "id": na["id"]})
                updated = True
            else:
                # Ensure the app has the ID set
                if "id" not in apps[app_idx]:
                    apps[app_idx]["id"] = na["id"]
                    updated = True
                # Ensure path is set to native if it was empty or different
                if not apps[app_idx].get("path"):
                    apps[app_idx]["path"] = "[Integrada Nativamente]"
                    updated = True
                
        config["apps"] = apps
        if updated:
            save_config(config)
            
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}. Returning defaults.")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    """Saves the config dictionary to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        logger.info("Configuration saved successfully.")
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False
