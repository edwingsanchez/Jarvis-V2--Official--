import os
import logging
import warnings

# Suppress google.generativeai deprecation warning
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai

logger = logging.getLogger("gemini_client")

class JarvisAI:
    def __init__(self, api_key, model_name="gemini-3.5-flash", system_instruction=None, open_app_callback=None):
        self.api_key = api_key
        self.model_name = model_name
        self.system_instruction = system_instruction or (
            "Eres J.A.R.V.I.S., la inteligencia artificial creada por Tony Stark. "
            "Respondes al usuario como 'Señor' o 'Creador' de manera sofisticada, servicial, "
            "un poco sarcástica pero siempre leal y eficiente. "
            "Usa un tono tecnológico y de asistente personal de alta tecnología."
        )
        self.open_app_callback = open_app_callback
        
        # Configure API key
        genai.configure(api_key=self.api_key)
        
        # Define tool function inside the class to capture self context
        def open_external_app(app_name: str) -> str:
            """Abre una aplicación o programa del sistema operativo instalada localmente (ej. 'Chrome', 'Blender', etc.) por su nombre.
            
            Args:
                app_name: El nombre de la aplicación o programa a abrir.
            """
            logger.info(f"Jarvis AI tool call: open_external_app('{app_name}')")
            if self.open_app_callback:
                return self.open_app_callback(app_name)
            return "Error: Callback de apertura de aplicación no configurado en el sistema."

        self.tools = [open_external_app]
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction,
            tools=self.tools
        )
        
        # Start chat with automatic tool call execution
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def send_message(self, text):
        """Sends a text message and returns the text response."""
        try:
            logger.info(f"Sending message to Gemini: {text}")
            response = self.chat.send_message(text)
            return response.text
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            raise e
