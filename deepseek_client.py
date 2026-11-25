import os
import json
import logging
import requests

logger = logging.getLogger("deepseek_client")

class JarvisDeepSeekAI:
    def __init__(self, api_key, model_name="deepseek-v4-pro", system_instruction=None, open_app_callback=None, base_url="https://api.deepseek.com"):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.system_instruction = system_instruction or (
            "Eres J.A.R.V.I.S., la inteligencia artificial creada por Tony Stark. "
            "Respondes al usuario como 'Señor' o 'Creador' de manera sofisticada, servicial, "
            "un poco sarcástica pero siempre leal y eficiente. "
            "Usa un tono tecnológico y de asistente personal de alta tecnología."
        )
        self.open_app_callback = open_app_callback
        
        self.messages = [
            {"role": "system", "content": self.system_instruction}
        ]
        
        # Tools definition (OpenAI-compatible)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "open_external_app",
                    "description": "Abre una aplicación o programa del sistema operativo instalada localmente (ej. 'Chrome', 'Blender', 'Domotica', 'Iron Man', 'Satelites', 'Image-to-model', etc.) por su nombre.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "app_name": {
                                "type": "string",
                                "description": "El nombre de la aplicación o programa a abrir."
                            }
                        },
                        "required": ["app_name"]
                    }
                }
            }
        ]

    def reset_chat(self):
        """Resets the conversation history keeping the system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_instruction}
        ]

    def _trim_history(self):
        """Keeps system prompt and the most recent 20 messages to manage context length."""
        if len(self.messages) > 22:
            self.messages = [self.messages[0]] + self.messages[-20:]

    def send_message(self, text):
        """Sends a text message to DeepSeek and returns the assistant's text response."""
        try:
            logger.info(f"Sending message to DeepSeek ({self.model_name}): {text}")
            self.messages.append({"role": "user", "content": text})
            self._trim_history()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            url = f"{self.base_url}/chat/completions"
            
            payload = {
                "model": self.model_name,
                "messages": self.messages,
                "tools": self.tools,
                "tool_choice": "auto"
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            
            # If model doesn't support tools, retry without tools
            if resp.status_code == 400 and "tools" in resp.text.lower():
                logger.warning(f"Model {self.model_name} may not support tools. Retrying without tools.")
                payload_no_tools = {
                    "model": self.model_name,
                    "messages": self.messages
                }
                resp = requests.post(url, headers=headers, json=payload_no_tools, timeout=60)

            if resp.status_code != 200:
                err_msg = f"DeepSeek API Error [{resp.status_code}]: {resp.text}"
                logger.error(err_msg)
                raise Exception(err_msg)

            data = resp.json()
            choice = data["choices"][0]
            message_obj = choice.get("message", {})
            tool_calls = message_obj.get("tool_calls")

            if tool_calls:
                # Add assistant message with tool calls to history
                self.messages.append(message_obj)

                for tool_call in tool_calls:
                    func = tool_call.get("function", {})
                    func_name = func.get("name")
                    call_id = tool_call.get("id")
                    raw_args = func.get("arguments", "{}")
                    
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        args = {}

                    logger.info(f"DeepSeek tool call: {func_name}({args})")
                    
                    if func_name == "open_external_app":
                        app_name = args.get("app_name", "")
                        if self.open_app_callback:
                            tool_result = self.open_app_callback(app_name)
                        else:
                            tool_result = "Error: Callback de apertura no configurado."
                    else:
                        tool_result = f"Error: Herramienta desconocida '{func_name}'."

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": str(tool_result)
                    })

                # Follow-up request to get final assistant response after tool execution
                followup_payload = {
                    "model": self.model_name,
                    "messages": self.messages
                }
                followup_resp = requests.post(url, headers=headers, json=followup_payload, timeout=60)
                if followup_resp.status_code != 200:
                    err_msg = f"DeepSeek Follow-up Error [{followup_resp.status_code}]: {followup_resp.text}"
                    logger.error(err_msg)
                    raise Exception(err_msg)
                
                followup_data = followup_resp.json()
                final_content = followup_data["choices"][0]["message"].get("content", "")
                self.messages.append({"role": "assistant", "content": final_content})
                return final_content
            else:
                content = message_obj.get("content", "")
                self.messages.append({"role": "assistant", "content": content})
                return content

        except Exception as e:
            logger.error(f"Error in DeepSeek send_message: {e}")
            raise e
