import os
import sys
import json
import threading
import logging
import requests
import time
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

# Import local modules
from config_manager import load_config, save_config
from gemini_client import JarvisAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis_app")

# Set customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")  # Default theme, we will customize colors

class ImageToModelWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Image-to-model (Tripo3D API)")
        self.geometry("900x600")
        self.resizable(False, False)
        
        # Ensure it appears on top and holds focus
        self.transient(parent)
        self.grab_set()
        
        # State
        self.image_path = None
        self.generating = False
        
        # Directory configuration
        self.models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Layout splits: 2 columns
        self.grid_columnconfigure(0, weight=1) # Left side (inputs/creation)
        self.grid_columnconfigure(1, weight=1) # Right side (list of models)
        self.grid_rowconfigure(0, weight=1)
        
        # LEFT PANEL
        left_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541")
        left_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_f.grid_columnconfigure(0, weight=1)
        left_f.pack_propagate(False)
        
        # Left Header
        lbl_l_title = ctk.CTkLabel(left_f, text="NÚCLEO TRIPO3D", font=("Segoe UI", 16, "bold"), text_color="#00ffcc")
        lbl_l_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        # Form Container
        form_f = ctk.CTkFrame(left_f, fg_color="transparent")
        form_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Tripo3D API Key Entry
        lbl_key = ctk.CTkLabel(form_f, text="Tripo3D API Key:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_key.pack(anchor="w", pady=(5, 2))
        
        self.ent_tripo_key = ctk.CTkEntry(form_f, placeholder_text="tsk_...", show="*", width=380)
        self.ent_tripo_key.pack(anchor="w", pady=(0, 10))
        self.ent_tripo_key.insert(0, self.parent.config.get("tripo_api_key", ""))
        
        # Model Name Entry
        lbl_name = ctk.CTkLabel(form_f, text="Nombre del Modelo:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_name.pack(anchor="w", pady=(5, 2))
        
        self.ent_name = ctk.CTkEntry(form_f, placeholder_text="ej. reactor_arc", width=380)
        self.ent_name.pack(anchor="w", pady=(0, 10))
        
        # Dotted/solid Attachment box for image
        lbl_att = ctk.CTkLabel(form_f, text="Imagen de Referencia:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_att.pack(anchor="w", pady=(5, 2))
        
        self.preview_frame = ctk.CTkFrame(form_f, fg_color="#03071e", border_width=1, border_color="#3a0ca3", height=150)
        self.preview_frame.pack(fill="x", pady=(0, 15))
        self.preview_frame.pack_propagate(False)
        
        self.lbl_preview = ctk.CTkLabel(self.preview_frame, text="📷 Clic para adjuntar imagen\n(Soporta PNG, JPG, WEBP)", font=("Segoe UI", 11, "italic"), text_color="#718093")
        self.lbl_preview.pack(expand=True)
        
        # Bind preview box to open file picker
        def pick_img(event):
            self.select_image()
        self.preview_frame.bind("<Button-1>", pick_img)
        self.lbl_preview.bind("<Button-1>", pick_img)
        
        # Create Model button
        self.btn_create = ctk.CTkButton(
            form_f, text="Crear Modelo 3D", font=("Segoe UI", 13, "bold"),
            fg_color="#00ffcc", hover_color="#00b894", text_color="#03071e",
            height=36, command=self.start_generation
        )
        self.btn_create.pack(fill="x", pady=(5, 10))
        
        # Progress Bar and Status Label
        self.status_lbl = ctk.CTkLabel(form_f, text="Estado: Listo", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        self.status_lbl.pack(anchor="w", pady=(5, 2))
        
        self.progress_bar = ctk.CTkProgressBar(form_f, progress_color="#00ffcc", fg_color="#1c2541")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        
        # RIGHT PANEL (List of Models)
        right_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541")
        right_f.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right_f.grid_columnconfigure(0, weight=1)
        right_f.grid_rowconfigure(0, weight=0) # Header
        right_f.grid_rowconfigure(1, weight=1) # Scroll list
        right_f.grid_rowconfigure(2, weight=0) # Bottom buttons
        right_f.pack_propagate(False)
        
        # Right Header
        lbl_r_title = ctk.CTkLabel(right_f, text="MODELOS GENERADOS", font=("Segoe UI", 16, "bold"), text_color="#00ffcc")
        lbl_r_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        # Scrollable container for items
        self.scroll_models = ctk.CTkScrollableFrame(right_f, fg_color="#03071e", border_width=1, border_color="#1c2541")
        self.scroll_models.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.scroll_models.grid_columnconfigure(0, weight=1)
        
        # Bottom control to open models folder
        self.btn_open_folder = ctk.CTkButton(
            right_f, text="📁 Abrir Carpeta de Modelos", font=("Segoe UI", 11, "bold"),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            height=30, command=self.open_models_directory
        )
        self.btn_open_folder.grid(row=2, column=0, sticky="ew", padx=15, pady=15)
        
        # Initial render of models
        self.refresh_models_list()
        
    def select_image(self):
        if self.generating:
            return
        path = filedialog.askopenfilename(
            title="Seleccionar Imagen de Referencia",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")]
        )
        if not path:
            return
        self.image_path = path
        try:
            pil_img = Image.open(path)
            pil_img.thumbnail((200, 110))
            self.photo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.lbl_preview.configure(image=self.photo, text="")
        except Exception:
            self.lbl_preview.configure(text=os.path.basename(path))
            
    def open_models_directory(self):
        try:
            os.startfile(self.models_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el directorio: {e}")
            
    def refresh_models_list(self):
        # Clear list
        for w in self.scroll_models.winfo_children():
            w.destroy()
            
        # Get glb files
        import glob, time
        files = glob.glob(os.path.join(self.models_dir, "*.glb"))
        
        # Sort by modification time (newest first)
        files.sort(key=os.path.getmtime, reverse=True)
        
        if not files:
            lbl_empty = ctk.CTkLabel(
                self.scroll_models, 
                text="No hay modelos generados en la carpeta.", 
                font=("Segoe UI", 11, "italic"),
                text_color="#718093"
            )
            lbl_empty.pack(pady=40)
            return
            
        for path in files:
            name = os.path.basename(path)
            size_kb = os.path.getsize(path) / 1024.0
            mtime = os.path.getmtime(path)
            date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            
            card = ctk.CTkFrame(self.scroll_models, fg_color="#0b132b", border_width=1, border_color="#1c2541", height=50)
            card.pack(fill="x", pady=4, padx=5)
            card.pack_propagate(False)
            
            info_f = ctk.CTkFrame(card, fg_color="transparent")
            info_f.pack(side="left", fill="both", expand=True, padx=10, pady=5)
            
            lbl_name = ctk.CTkLabel(info_f, text=name, font=("Segoe UI", 12, "bold"), text_color="#ffffff")
            lbl_name.pack(anchor="w")
            
            lbl_info = ctk.CTkLabel(info_f, text=f"{date_str} | {size_kb:.1f} KB", font=("Consolas", 9), text_color="#718093")
            lbl_info.pack(anchor="w")
            
            # Action button to open GLB (with default viewer)
            btn_play = ctk.CTkButton(
                card, text="Abrir", font=("Segoe UI", 10, "bold"),
                fg_color="#00ffcc", hover_color="#00b894", text_color="#03070e",
                width=60, height=24,
                command=lambda p=path: self.open_model_file(p)
            )
            btn_play.pack(side="right", padx=10, pady=13)
            
    def open_model_file(self, filepath):
        try:
            os.startfile(filepath)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo de modelo: {e}")
            
    def start_generation(self):
        if self.generating:
            return
            
        api_key = self.ent_tripo_key.get().strip()
        proj_name = self.ent_name.get().strip()
        
        if not api_key:
            messagebox.showerror("Error", "Por favor ingrese su API Key de Tripo3D.")
            return
        if not proj_name:
            messagebox.showerror("Error", "Por favor ingrese el nombre del modelo.")
            return
        if not self.image_path:
            messagebox.showerror("Error", "Por favor adjunte una imagen de referencia.")
            return
            
        # Strip extension if written
        if proj_name.lower().endswith(".glb"):
            proj_name = proj_name[:-4]
            
        self.generating = True
        self.btn_create.configure(state="disabled", text="PROCESANDO...")
        
        # Start worker thread
        threading.Thread(
            target=self.generation_worker,
            args=(api_key, proj_name, self.image_path),
            daemon=True
        ).start()
        
    def generation_worker(self, api_key, proj_name, image_path):
        try:
            # 0. Save config
            self.parent.config["tripo_api_key"] = api_key
            save_config(self.parent.config)
            
            # 1. Upload File
            self.update_status("Subiendo imagen al servidor de Tripo3D...", 0.1)
            
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            with open(image_path, "rb") as f:
                files = {
                    "file": (os.path.basename(image_path), f, "image/png")
                }
                response = requests.post("https://openapi.tripo3d.ai/v3/files", headers=headers, files=files, timeout=60)
                
            if response.status_code != 200:
                raise Exception(f"Error de servidor al subir archivo ({response.status_code}): {response.text}")
                
            res_json = response.json()
            if res_json.get("code") != 0:
                raise Exception(f"Error Tripo API upload: {res_json.get('message', 'Desconocido')}")
                
            file_token = res_json.get("data", {}).get("file_token")
            if not file_token:
                raise Exception("No se recibió el token de archivo (file_token) del servidor.")
                
            # 2. Submit Generation Task
            self.update_status("Iniciando tarea de generación 3D...", 0.3)
            
            headers_json = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            ext = os.path.splitext(image_path)[1][1:].lower()
            if ext not in ("png", "jpg", "jpeg", "webp"):
                ext = "png"
            if ext == "jpeg":
                ext = "jpg"

            payload = {
                "file": {
                    "type": ext,
                    "file_token": file_token
                },
                "model": "v3.0-20250812"
            }
            
            task_resp = requests.post(
                "https://openapi.tripo3d.ai/v3/generation/image-to-model",
                headers=headers_json,
                json=payload,
                timeout=30
            )
            
            if task_resp.status_code != 200:
                raise Exception(f"Error de servidor al iniciar tarea ({task_resp.status_code}): {task_resp.text}")
                
            task_json = task_resp.json()
            if task_json.get("code") != 0:
                raise Exception(f"Error Tripo API task: {task_json.get('message', 'Desconocido')}")
                
            task_id = task_json.get("data", {}).get("task_id")
            if not task_id:
                raise Exception("No se recibió el task_id del servidor.")
                
            # 3. Polling task status
            self.update_status("Generando malla en la nube... (0%)", 0.4)
            
            model_url = None
            while True:
                time.sleep(2)
                
                check_resp = requests.get(
                    f"https://openapi.tripo3d.ai/v3/tasks/{task_id}",
                    headers=headers,
                    timeout=20
                )
                if check_resp.status_code != 200:
                    continue
                    
                check_json = check_resp.json()
                if check_json.get("code") != 0:
                    raise Exception(f"Error de polling Tripo API: {check_json.get('message')}")
                    
                task_data = check_json.get("data", {})
                status = task_data.get("status")
                progress = task_data.get("progress", 0)
                
                # Update status
                self.update_status(f"Generando malla en la nube... ({progress}%)", 0.4 + (progress / 100.0) * 0.4)
                
                if status == "success":
                    model_url = task_data.get("output", {}).get("model_url")
                    break
                elif status in ("failed", "cancelled", "banned"):
                    raise Exception(f"La tarea finalizó con estado: {status}.")
                    
            if not model_url:
                raise Exception("La tarea finalizó exitosamente pero no se encontró la URL del modelo.")
                
            # 4. Download Model
            self.update_status("Descargando archivo GLB generado...", 0.85)
            
            dl_resp = requests.get(model_url, timeout=120)
            if dl_resp.status_code != 200:
                raise Exception(f"Error al descargar el modelo GLB: HTTP {dl_resp.status_code}")
                
            save_path = os.path.join(self.models_dir, f"{proj_name}.glb")
            with open(save_path, "wb") as f_out:
                f_out.write(dl_resp.content)
                
            # 5. Done!
            self.update_status("¡Conversión completada con éxito!", 1.0)
            self.after(0, self.refresh_models_list)
            self.after(0, lambda: messagebox.showinfo("Tripo3D", f"¡Modelo '{proj_name}.glb' creado y descargado con éxito en la carpeta de proyectos!"))
            
        except Exception as e:
            self.update_status("Error en el proceso.", 0.0)
            self.after(0, lambda err=str(e): messagebox.showerror("Error de Conversión", f"Ocurrió un error en el pipeline:\n{err}"))
            
        finally:
            self.generating = False
            self.after(0, lambda: self.btn_create.configure(state="normal", text="Crear Modelo 3D"))
            
    def update_status(self, text, progress_val):
        self.after(0, lambda: self.status_lbl.configure(text=f"Estado: {text}"))
        self.after(0, lambda: self.progress_bar.set(progress_val))


class DomoticaWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Domótica (Home Assistant)")
        self.geometry("950x650")
        self.resizable(True, True)
        
        # Ensure it appears on top
        self.transient(parent)
        self.grab_set()
        
        # State
        self.connecting = False
        self.entities = []
        
        # Layout
        self.grid_rowconfigure(0, weight=0) # Top Panel (credentials)
        self.grid_rowconfigure(1, weight=1) # Main Scrollable content
        self.grid_columnconfigure(0, weight=1)
        
        # TOP PANEL: Credentials & Status
        top_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541", height=80)
        top_f.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        top_f.grid_propagate(False)
        
        # URL Label & Entry
        lbl_url = ctk.CTkLabel(top_f, text="HA URL:", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_url.pack(side="left", padx=(15, 5), pady=25)
        
        self.ent_url = ctk.CTkEntry(top_f, placeholder_text="http://192.168.1.X:8123", width=200)
        self.ent_url.pack(side="left", padx=5, pady=25)
        self.ent_url.insert(0, self.parent.config.get("homeassistant_url", "http://localhost:8123"))
        
        # Token Label & Entry
        lbl_tok = ctk.CTkLabel(top_f, text="Token:", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_tok.pack(side="left", padx=(15, 5), pady=25)
        
        self.ent_token = ctk.CTkEntry(top_f, placeholder_text="Acceso de Larga Duración...", show="*", width=220)
        self.ent_token.pack(side="left", padx=5, pady=25)
        self.ent_token.insert(0, self.parent.config.get("homeassistant_token", ""))
        
        # Connect Button
        self.btn_connect = ctk.CTkButton(
            top_f, text="Conectar y Guardar", font=("Segoe UI", 11, "bold"),
            fg_color="#00ffcc", hover_color="#00b894", text_color="#03071e",
            width=130, command=self.save_and_connect
        )
        self.btn_connect.pack(side="left", padx=15, pady=25)
        
        # Status Light Indicator
        self.status_indicator = ctk.CTkLabel(top_f, text="● Desconectado", font=("Segoe UI", 11, "bold"), text_color="#ff4757")
        self.status_indicator.pack(side="left", padx=10, pady=25)
        
        # Refresh Button
        self.btn_refresh = ctk.CTkButton(
            top_f, text="🔄 Refrescar", font=("Segoe UI", 11, "bold"),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            width=90, command=self.fetch_devices_async
        )
        self.btn_refresh.pack(side="right", padx=15, pady=25)
        
        # MAIN SCROLLABLE CONTENT: Scrollable frame to show cards
        self.scroll_devices = ctk.CTkScrollableFrame(self, fg_color="#03071e", border_width=1, border_color="#1c2541")
        self.scroll_devices.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.scroll_devices.grid_columnconfigure(0, weight=1)
        self.scroll_devices.grid_columnconfigure(1, weight=1) # 2 columns grid for cards
        
        # If credentials exist, try connecting initially
        if self.parent.config.get("homeassistant_token"):
            self.fetch_devices_async()
            
    def save_and_connect(self):
        url = self.ent_url.get().strip()
        token = self.ent_token.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Por favor ingrese la URL de Home Assistant.")
            return
        if not token:
            messagebox.showerror("Error", "Por favor ingrese su Token de Acceso.")
            return
            
        # Remove trailing slash from URL
        if url.endswith("/"):
            url = url[:-1]
            
        self.parent.config["homeassistant_url"] = url
        self.parent.config["homeassistant_token"] = token
        save_config(self.parent.config)
        
        self.fetch_devices_async()
        
    def fetch_devices_async(self):
        if self.connecting:
            return
        self.connecting = True
        self.btn_refresh.configure(state="disabled", text="Cargando...")
        self.status_indicator.configure(text="● Consultando API...", text_color="#eccc68")
        
        threading.Thread(target=self.fetch_devices_worker, daemon=True).start()
        
    def fetch_devices_worker(self):
        url = self.parent.config.get("homeassistant_url", "")
        token = self.parent.config.get("homeassistant_token", "")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            # First, check API connection status
            test_resp = requests.get(f"{url}/api/", headers=headers, timeout=10)
            if test_resp.status_code != 200:
                raise Exception(f"Código de estado HTTP: {test_resp.status_code}")
                
            # Fetch all states
            states_resp = requests.get(f"{url}/api/states", headers=headers, timeout=15)
            if states_resp.status_code != 200:
                raise Exception(f"Error al obtener estados: HTTP {states_resp.status_code}")
                
            entities_data = states_resp.json()
            
            # Filter entities we can show and control
            allowed_domains = ("light", "switch", "input_boolean", "sensor", "binary_sensor", "climate")
            filtered_entities = []
            
            for ent in entities_data:
                ent_id = ent.get("entity_id", "")
                domain = ent_id.split(".")[0] if "." in ent_id else ""
                if domain in allowed_domains:
                    filtered_entities.append(ent)
                    
            # Sort by friendly name
            filtered_entities.sort(key=lambda e: e.get("attributes", {}).get("friendly_name") or e.get("entity_id"))
            
            self.entities = filtered_entities
            self.after(0, lambda: self.status_indicator.configure(text="● Conectado", text_color="#2ed573"))
            self.after(0, self.render_entities)
            
        except Exception as e:
            self.entities = []
            self.after(0, lambda: self.status_indicator.configure(text="● Error", text_color="#ff4757"))
            self.after(0, lambda err=str(e): messagebox.showerror("Error de Conexión", f"No se pudo establecer conexión con Home Assistant:\n{err}"))
            self.after(0, self.render_entities)
            
        finally:
            self.connecting = False
            self.after(0, lambda: self.btn_refresh.configure(state="normal", text="🔄 Refrescar"))
            
    def render_entities(self):
        # Clear main area
        for w in self.scroll_devices.winfo_children():
            w.destroy()
            
        if not self.entities:
            lbl_empty = ctk.CTkLabel(
                self.scroll_devices,
                text="No hay dispositivos compatibles listados o no se pudo conectar.\nVerifique sus credenciales de Home Assistant.",
                font=("Segoe UI", 12, "italic"),
                text_color="#718093"
            )
            lbl_empty.pack(pady=60)
            return
            
        # Draw 2 columns layout
        for i, ent in enumerate(self.entities):
            ent_id = ent.get("entity_id", "")
            domain = ent_id.split(".")[0]
            state = ent.get("state", "unknown")
            attrs = ent.get("attributes", {})
            friendly_name = attrs.get("friendly_name") or ent_id
            
            # Map Emojis
            emoji = "⚙️"
            if domain == "light":
                emoji = "💡"
            elif domain in ("switch", "input_boolean"):
                emoji = "🔌"
            elif domain == "sensor":
                emoji = "🌡️"
            elif domain == "binary_sensor":
                emoji = "🚪"
            elif domain == "climate":
                emoji = "❄️" if state == "cool" else "🔥" if state == "heat" else "🍃"
                
            unit = attrs.get("unit_of_measurement", "")
            state_text = f"{state} {unit}".strip()
            
            # Card Container
            card = ctk.CTkFrame(self.scroll_devices, fg_color="#0b132b", border_width=1, border_color="#1c2541", height=75)
            # Grid layout for cards in 2 columns
            r = i // 2
            c = i % 2
            card.grid(row=r, column=c, sticky="nsew", padx=10, pady=8)
            card.grid_propagate(False)
            
            # Grid internally for card: 3 columns (Icon/Name, State, Control)
            card.columnconfigure(0, weight=2)
            card.columnconfigure(1, weight=1)
            card.columnconfigure(2, weight=1)
            card.rowconfigure(0, weight=1)
            
            # Icon + Name
            info_f = ctk.CTkFrame(card, fg_color="transparent")
            info_f.grid(row=0, column=0, sticky="w", padx=10, pady=10)
            
            lbl_emoji_name = ctk.CTkLabel(
                info_f, 
                text=f"{emoji} {friendly_name}", 
                font=("Segoe UI", 12, "bold"), 
                text_color="#ffffff",
                anchor="w",
                justify="left"
            )
            lbl_emoji_name.pack(anchor="w")
            
            lbl_ent_id = ctk.CTkLabel(info_f, text=ent_id, font=("Consolas", 9), text_color="#718093", anchor="w")
            lbl_ent_id.pack(anchor="w")
            
            # State label
            lbl_state = ctk.CTkLabel(
                card, 
                text=state_text.upper(), 
                font=("Segoe UI", 11, "bold"), 
                text_color="#00ffcc" if state in ("on", "open", "active") or domain == "sensor" else "#a5b1c2"
            )
            lbl_state.grid(row=0, column=1, sticky="center", padx=5)
            
            # Controls
            control_f = ctk.CTkFrame(card, fg_color="transparent")
            control_f.grid(row=0, column=2, sticky="e", padx=10)
            
            if domain in ("light", "switch", "input_boolean"):
                # Toggle Switch
                is_on = state == "on"
                
                # Switch command
                def make_toggle_cmd(eid=ent_id, cur_st=state, label=lbl_state):
                    return lambda val: self.toggle_entity(eid, cur_st, label)
                    
                switch_widget = ctk.CTkSwitch(
                    control_f, text="", width=40, height=20,
                    progress_color="#00ffcc", fg_color="#1c2541"
                )
                if is_on:
                    switch_widget.select()
                switch_widget.configure(command=make_toggle_cmd(ent_id, state, lbl_state))
                switch_widget.pack()
                
            elif domain == "climate":
                # Temperature target controls
                tgt_temp = attrs.get("temperature") or attrs.get("target_temp_high") or 22
                
                lbl_tgt = ctk.CTkLabel(control_f, text=f"{tgt_temp}°", font=("Segoe UI", 11, "bold"), text_color="#ffffff")
                
                def make_temp_cmd(eid=ent_id, cur_t=tgt_temp, diff=1, label=lbl_tgt):
                    return lambda: self.adjust_temperature(eid, cur_t, diff, label)
                    
                btn_down = ctk.CTkButton(
                    control_f, text="-", font=("Segoe UI", 11, "bold"),
                    fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
                    width=22, height=22, command=make_temp_cmd(ent_id, tgt_temp, -1, lbl_tgt)
                )
                btn_down.pack(side="left", padx=2)
                
                lbl_tgt.pack(side="left", padx=2)
                
                btn_up = ctk.CTkButton(
                    control_f, text="+", font=("Segoe UI", 11, "bold"),
                    fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
                    width=22, height=22, command=make_temp_cmd(ent_id, tgt_temp, 1, lbl_tgt)
                )
                btn_up.pack(side="left", padx=2)
                
            else:
                # Sensors and binary sensors don't have control widgets, just display a check icon or state info
                lbl_no_ctrl = ctk.CTkLabel(control_f, text="Lectura", font=("Segoe UI", 9, "italic"), text_color="#718093")
                lbl_no_ctrl.pack()
                
    def toggle_entity(self, entity_id, current_state, label_to_update):
        domain = entity_id.split(".")[0]
        service = "turn_off" if current_state == "on" else "turn_on"
        
        # UI optimistic update
        new_state = "off" if current_state == "on" else "on"
        label_to_update.configure(
            text=new_state.upper(),
            text_color="#a5b1c2" if new_state == "off" else "#00ffcc"
        )
        
        threading.Thread(
            target=self.call_service_worker,
            args=(domain, service, {"entity_id": entity_id}),
            daemon=True
        ).start()
        
    def adjust_temperature(self, entity_id, current_temp, difference, label_to_update):
        new_temp = float(current_temp) + difference
        label_to_update.configure(text=f"{new_temp}°")
        
        threading.Thread(
            target=self.call_service_worker,
            args=("climate", "set_temperature", {"entity_id": entity_id, "temperature": new_temp}),
            daemon=True
        ).start()
        
    def call_service_worker(self, domain, service, service_data):
        url = self.parent.config.get("homeassistant_url", "")
        token = self.parent.config.get("homeassistant_token", "")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(
                f"{url}/api/services/{domain}/{service}",
                headers=headers,
                json=service_data,
                timeout=10
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Error calling service: HTTP {resp.status_code} - {resp.text}")
                
            # Trigger list update after a short delay to get the new state correctly from HA
            time.sleep(1)
            self.after(0, self.fetch_devices_async)
        except Exception as e:
            logger.error(f"Failed to trigger service call: {e}")


class IronmanWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Sistemas del Traje Mark LXXXV")
        self.geometry("920x620")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        # State & Sim Variables
        self.active = True
        self.reactor_power = 98.7
        self.system_temp = 34.2
        self.repulsor_l_charge = 100.0
        self.repulsor_r_charge = 100.0
        self.repulsor_l_status = "LISTO"
        self.repulsor_r_status = "LISTO"
        self.thrust_level = 0.0
        self.hud_status = "TACTICAL PROFILE"
        self.combat_mode = False
        
        # Main Layout: 2 Columns Grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # LEFT COLUMN (Reactor & Thrusters)
        left_f = ctk.CTkFrame(self, fg_color="#0b0b0b", border_width=1, border_color="#ff3e3e")
        left_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_f.grid_columnconfigure(0, weight=1)
        left_f.pack_propagate(False)
        
        # Header
        lbl_l_title = ctk.CTkLabel(left_f, text="NÚCLEO Y PROPULSIÓN", font=("Segoe UI", 16, "bold"), text_color="#ff3e3e")
        lbl_l_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        # Arc Reactor Card
        reac_f = ctk.CTkFrame(left_f, fg_color="#141414", border_width=1, border_color="#333333")
        reac_f.pack(fill="x", padx=20, pady=10)
        
        lbl_reac_title = ctk.CTkLabel(reac_f, text="⚡ REACTOR ARC - STARK INDUSTRIES", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_reac_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.lbl_reac_status = ctk.CTkLabel(reac_f, text="ENERGÍA: 98.7% | ESTABLE", font=("Consolas", 12, "bold"), text_color="#00e5ff")
        self.lbl_reac_status.pack(anchor="w", padx=15, pady=2)
        
        self.reac_progress = ctk.CTkProgressBar(reac_f, progress_color="#00e5ff", fg_color="#222222")
        self.reac_progress.set(0.987)
        self.reac_progress.pack(fill="x", padx=15, pady=(5, 10))
        
        btn_reac_over = ctk.CTkButton(
            reac_f, text="SOBRECARGAR REACTOR", font=("Segoe UI", 10, "bold"),
            fg_color="#ff3e3e", hover_color="#ff6b6b", text_color="#ffffff",
            height=24, command=self.overload_reactor
        )
        btn_reac_over.pack(side="left", padx=15, pady=(0, 15))
        
        btn_reac_cool = ctk.CTkButton(
            reac_f, text="REFRIGERACIÓN", font=("Segoe UI", 10, "bold"),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            height=24, command=self.cool_reactor
        )
        btn_reac_cool.pack(side="left", padx=5, pady=(0, 15))
        
        # Thrusters Card
        thrust_f = ctk.CTkFrame(left_f, fg_color="#141414", border_width=1, border_color="#333333")
        thrust_f.pack(fill="x", padx=20, pady=10)
        
        lbl_thrust_title = ctk.CTkLabel(thrust_f, text="🚀 PROPULSORES DE VUELO (BOTAS)", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_thrust_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.lbl_thrust_status = ctk.CTkLabel(thrust_f, text="EMPUJE: 0.0% (INACTIVO) | TEMP: 34.2°C", font=("Consolas", 12, "bold"), text_color="#a5b1c2")
        self.lbl_thrust_status.pack(anchor="w", padx=15, pady=2)
        
        self.slider_thrust = ctk.CTkSlider(thrust_f, from_=0.0, to=100.0, progress_color="#ff8c00", button_color="#ff3e3e", command=self.adjust_thrust)
        self.slider_thrust.set(0.0)
        self.slider_thrust.pack(fill="x", padx=15, pady=(5, 15))
        
        
        # RIGHT COLUMN (HUD & Weapons)
        right_f = ctk.CTkFrame(self, fg_color="#0b0b0b", border_width=1, border_color="#00e5ff")
        right_f.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right_f.grid_columnconfigure(0, weight=1)
        right_f.pack_propagate(False)
        
        # Header
        lbl_r_title = ctk.CTkLabel(right_f, text="HUD Y ARMAS (SISTEMAS MANUALES)", font=("Segoe UI", 16, "bold"), text_color="#00e5ff")
        lbl_r_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        # Repulsors Card
        rep_f = ctk.CTkFrame(right_f, fg_color="#141414", border_width=1, border_color="#333333")
        rep_f.pack(fill="x", padx=20, pady=10)
        
        lbl_rep_title = ctk.CTkLabel(rep_f, text="💥 REPULSORES EN MANOS", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_rep_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.lbl_rep_l = ctk.CTkLabel(rep_f, text="REPULSOR IZQ: 100% | LISTO", font=("Consolas", 11, "bold"), text_color="#00ffcc")
        self.lbl_rep_l.pack(anchor="w", padx=15, pady=2)
        
        self.lbl_rep_r = ctk.CTkLabel(rep_f, text="REPULSOR DER: 100% | LISTO", font=("Consolas", 11, "bold"), text_color="#00ffcc")
        self.lbl_rep_r.pack(anchor="w", padx=15, pady=2)
        
        btn_fire = ctk.CTkButton(
            rep_f, text="FOGONAZO DE PRUEBA", font=("Segoe UI", 11, "bold"),
            fg_color="#00e5ff", hover_color="#00b894", text_color="#03071e",
            height=30, command=self.test_fire_repulsors
        )
        btn_fire.pack(fill="x", padx=15, pady=15)
        
        # HUD Card
        hud_f = ctk.CTkFrame(right_f, fg_color="#141414", border_width=1, border_color="#333333")
        hud_f.pack(fill="x", padx=20, pady=10)
        
        lbl_hud_title = ctk.CTkLabel(hud_f, text="🕶️ SISTEMAS HUD & ESCANER TÁCTICO", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_hud_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        # Diagnostic Profile
        lbl_diag = ctk.CTkLabel(hud_f, text="Perfil de HUD:", font=("Segoe UI", 10), text_color="#a5b1c2")
        lbl_diag.pack(anchor="w", padx=15, pady=(5, 2))
        
        self.drop_diag = ctk.CTkOptionMenu(
            hud_f, values=["TACTICAL PROFILE", "COMBAT ENGAGEMENT", "FLIGHT NAVIGATION", "STEALTH PROTOCOL"],
            fg_color="#1c2541", button_color="#00e5ff", button_hover_color="#ff3e3e",
            command=self.change_hud_profile
        )
        self.drop_diag.set("TACTICAL PROFILE")
        self.drop_diag.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Combat Mode Toggle
        self.switch_combat = ctk.CTkSwitch(
            hud_f, text="MODO COMBATE COMPLETO", font=("Segoe UI", 11, "bold"),
            progress_color="#ff3e3e", fg_color="#1c2541", command=self.toggle_combat_mode
        )
        self.switch_combat.pack(anchor="w", padx=15, pady=15)
        
        # Start Live Fluctuation Thread
        threading.Thread(target=self.live_fluctuation_worker, daemon=True).start()
        
    def overload_reactor(self):
        self.reactor_power = 125.0
        self.system_temp = 89.4
        self.lbl_reac_status.configure(text="ENERGÍA: 125.0% | !!!SOBRECARGA!!!", text_color="#ff3e3e")
        self.reac_progress.set(1.0)
        self.reac_progress.configure(progress_color="#ff3e3e")
        messagebox.showwarning("Reactor Arc", "¡ADVERTENCIA! Reactor Arc operando al 125%. Incremento crítico de temperatura del traje detectado.")
        
    def cool_reactor(self):
        self.reactor_power = 98.7
        self.system_temp = 32.1
        self.lbl_reac_status.configure(text="ENERGÍA: 98.7% | REFRIGERADO", text_color="#00e5ff")
        self.reac_progress.set(0.987)
        self.reac_progress.configure(progress_color="#00e5ff")
        
    def adjust_thrust(self, value):
        self.thrust_level = float(value)
        self.system_temp = 34.2 + (self.thrust_level * 0.4)
        status = "ACTIVO" if self.thrust_level > 0 else "INACTIVO"
        self.lbl_thrust_status.configure(
            text=f"EMPUJE: {self.thrust_level:.1f}% ({status}) | TEMP: {self.system_temp:.1f}°C",
            text_color="#ff8c00" if self.thrust_level > 0 else "#a5b1c2"
        )
        
    def test_fire_repulsors(self):
        if self.repulsor_l_status != "LISTO":
            return
            
        def anim():
            # Charging
            self.repulsor_l_status = "CARGANDO"
            self.repulsor_r_status = "CARGANDO"
            self.lbl_rep_l.configure(text="REPULSOR IZQ: CARGANDO CAPACITORES...", text_color="#ff8c00")
            self.lbl_rep_r.configure(text="REPULSOR DER: CARGANDO CAPACITORES...", text_color="#ff8c00")
            time.sleep(1.0)
            
            # Firing
            self.repulsor_l_status = "DISPARANDO"
            self.repulsor_r_status = "DISPARANDO"
            self.lbl_rep_l.configure(text="REPULSOR IZQ: !!!DISPARANDO!!!", text_color="#ff3e3e")
            self.lbl_rep_r.configure(text="REPULSOR DER: !!!DISPARANDO!!!", text_color="#ff3e3e")
            self.reactor_power -= 4.2
            time.sleep(0.8)
            
            # Cooling Down
            self.repulsor_l_status = "ENFRIANDO"
            self.repulsor_r_status = "ENFRIANDO"
            self.lbl_rep_l.configure(text="REPULSOR IZQ: ENFRIANDO SISTEMA...", text_color="#eccc68")
            self.lbl_rep_r.configure(text="REPULSOR DER: ENFRIANDO SISTEMA...", text_color="#eccc68")
            time.sleep(1.2)
            
            # Ready
            self.repulsor_l_status = "LISTO"
            self.repulsor_r_status = "LISTO"
            self.lbl_rep_l.configure(text="REPULSOR IZQ: 100% | LISTO", text_color="#00ffcc")
            self.lbl_rep_r.configure(text="REPULSOR DER: 100% | LISTO", text_color="#00ffcc")
            
        threading.Thread(target=anim, daemon=True).start()
        
    def change_hud_profile(self, value):
        self.hud_status = value
        
    def toggle_combat_mode(self):
        self.combat_mode = self.switch_combat.get() == 1
        if self.combat_mode:
            self.configure(border_color="#ff3e3e")
            self.drop_diag.set("COMBAT ENGAGEMENT")
            self.change_hud_profile("COMBAT ENGAGEMENT")
        else:
            self.configure(border_color="#00e5ff")
            self.drop_diag.set("TACTICAL PROFILE")
            self.change_hud_profile("TACTICAL PROFILE")
            
    def live_fluctuation_worker(self):
        import random
        while self.active:
            time.sleep(1)
            if not self.winfo_exists():
                break
                
            # Fluctuate energy slightly
            if self.reactor_power > 0 and self.repulsor_l_status == "LISTO":
                change = random.uniform(-0.15, 0.15)
                self.reactor_power = max(5.0, min(130.0, self.reactor_power + change))
                
                # Slowly draw power if thrusters are on
                if self.thrust_level > 0:
                    self.reactor_power = max(1.0, self.reactor_power - (self.thrust_level * 0.01))
                    
                # Update label and progress bar
                color = "#ff3e3e" if self.reactor_power > 110 else "#00e5ff"
                status_txt = "SOBRECARGADO" if self.reactor_power > 110 else "ESTABLE"
                
                self.lbl_reac_status.configure(
                    text=f"ENERGÍA: {self.reactor_power:.2f}% | {status_txt}",
                    text_color=color
                )
                self.reac_progress.set(min(1.0, self.reactor_power / 100.0))
                self.reac_progress.configure(progress_color=color)
                
            # Fluctuate thruster temp slightly
            if self.thrust_level > 0:
                self.system_temp = max(34.2, min(120.0, self.system_temp + random.uniform(-0.5, 0.5)))
                self.lbl_thrust_status.configure(
                    text=f"EMPUJE: {self.thrust_level:.1f}% (ACTIVO) | TEMP: {self.system_temp:.1f}°C"
                )
                
    def destroy(self):
        self.active = False
        super().destroy()


class SatellitesWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Red de Satélites Stark")
        self.geometry("950x650")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        # State
        self.active = True
        self.selected_satellite = "STARK-I (Veronica)"
        self.sat_angle = 0.0
        
        # Satellite Data Simulator
        self.satellites_db = {
            "STARK-I (Veronica)": {"status": "EN ÓRBITA", "signal": 98, "type": "GEOSÍNCRONA", "lat": 12.45, "lon": -45.67, "alt": 35786},
            "STARK-II (Defensa)": {"status": "STANDBY", "signal": 84, "type": "POLAR BAJA", "lat": -82.11, "lon": 120.34, "alt": 850},
            "STARK-III (Láser Orbital)": {"status": "DIAGNÓSTICO", "signal": 42, "type": "HELIOSÍNCRONA", "lat": 45.12, "lon": 12.98, "alt": 1200},
            "STARK-IV (Comunicación)": {"status": "ACTIVO", "signal": 99, "type": "ÓRBITA ELÍPTICA", "lat": 5.76, "lon": -118.45, "alt": 20200}
        }
        
        # Layout: 2 Columns (Sidebar list vs main view)
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # LEFT BAR (Satellite Selection)
        left_f = ctk.CTkFrame(self, fg_color="#081c15", border_width=1, border_color="#52b788")
        left_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_f.pack_propagate(False)
        
        lbl_l_title = ctk.CTkLabel(left_f, text="RED STARK S.O.D.", font=("Segoe UI", 16, "bold"), text_color="#52b788")
        lbl_l_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        self.scroll_sats = ctk.CTkScrollableFrame(left_f, fg_color="transparent")
        self.scroll_sats.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Render satellite buttons
        self.sat_buttons = {}
        self.render_satellite_buttons()
        
        # RIGHT BAR (Radar Grid & Logs)
        right_f = ctk.CTkFrame(self, fg_color="#020907", border_width=1, border_color="#52b788")
        right_f.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right_f.grid_columnconfigure(0, weight=1)
        right_f.grid_rowconfigure(0, weight=1) # Radar canvas
        right_f.grid_rowconfigure(1, weight=0, minsize=180) # Console logs
        right_f.pack_propagate(False)
        
        # Radar Canvas
        self.canvas_radar = ctk.CTkCanvas(right_f, bg="#020907", highlightthickness=1, highlightbackground="#1b4332")
        self.canvas_radar.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        # Console Log Panel
        log_f = ctk.CTkFrame(right_f, fg_color="#051c12", border_width=1, border_color="#1b4332")
        log_f.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        log_f.grid_columnconfigure(0, weight=1)
        log_f.grid_rowconfigure(0, weight=1)
        
        self.txt_logs = ctk.CTkTextbox(log_f, font=("Consolas", 10), text_color="#74c69d", fg_color="transparent")
        self.txt_logs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.txt_logs.configure(state="disabled")
        
        # Log Init
        self.log_message("Conectando terminal satelital Stark Link...")
        self.log_message("Enlace descendente establecido exitosamente.")
        
        # Start Radar animation & Log simulation
        self.animate_radar()
        threading.Thread(target=self.live_telemetry_worker, daemon=True).start()
        
    def render_satellite_buttons(self):
        for widget in self.scroll_sats.winfo_children():
            widget.destroy()
            
        for name, data in self.satellites_db.items():
            is_sel = name == self.selected_satellite
            bg_card = "#1b4332" if is_sel else "#0b251a"
            border_c = "#52b788" if is_sel else "#1b4332"
            
            card = ctk.CTkFrame(self.scroll_sats, fg_color=bg_card, border_width=1, border_color=border_c, height=65)
            card.pack(fill="x", pady=5)
            card.pack_propagate(False)
            
            # Click trigger
            def make_select(n=name):
                return lambda e: self.select_sat(n)
            card.bind("<Button-1>", make_select(name))
            
            # Labels
            lbl_name = ctk.CTkLabel(card, text=name, font=("Segoe UI", 11, "bold"), text_color="#ffffff")
            lbl_name.pack(anchor="w", padx=10, pady=(6, 2))
            lbl_name.bind("<Button-1>", make_select(name))
            
            lbl_st = ctk.CTkLabel(card, text=f"{data['status']} | Señal: {data['signal']}%", font=("Consolas", 9), text_color="#74c69d" if data['signal'] > 50 else "#ff4757")
            lbl_st.pack(anchor="w", padx=10)
            lbl_st.bind("<Button-1>", make_select(name))
            
    def select_sat(self, name):
        self.selected_satellite = name
        self.render_satellite_buttons()
        self.log_message(f"Enlace de comunicación redirigido a {name} ({self.satellites_db[name]['type']})")
        
    def log_message(self, text):
        import time
        date_str = time.strftime("%H:%M:%S")
        log_line = f"[{date_str}] STARK-NET: {text}\n"
        self.txt_logs.configure(state="normal")
        self.txt_logs.insert("end", log_line)
        self.txt_logs.see("end")
        self.txt_logs.configure(state="disabled")
        
    def animate_radar(self):
        if not self.active or not self.winfo_exists():
            return
            
        try:
            self.canvas_radar.delete("all")
            w = self.canvas_radar.winfo_width()
            h = self.canvas_radar.winfo_height()
            
            if w <= 1 or h <= 1:
                self.after(100, self.animate_radar)
                return
                
            cx = w / 2
            cy = h / 2
            r_max = min(w, h) / 2.2
            
            # Draw radar circles
            for i in range(1, 5):
                r = r_max * (i / 4.0)
                self.canvas_radar.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#1b4332", width=1)
                
            # Draw radar lines
            self.canvas_radar.create_line(cx - r_max, cy, cx + r_max, cy, fill="#1b4332", width=1)
            self.canvas_radar.create_line(cx, cy - r_max, cx, cy + r_max, fill="#1b4332", width=1)
            
            # Draw radar sweep line
            import math
            self.sat_angle = (self.sat_angle + 0.02) % (2 * math.pi)
            sx = cx + r_max * math.cos(self.sat_angle)
            sy = cy + r_max * math.sin(self.sat_angle)
            self.canvas_radar.create_line(cx, cy, sx, sy, fill="#40916c", width=2)
            
            # Draw Satellite dot moving along a path (circle orbit)
            sat_data = self.satellites_db[self.selected_satellite]
            orb_r = r_max * 0.7
            # Determine angle offset based on satellite details
            offset = 1.0 if "Veronica" in self.selected_satellite else 2.5 if "Defensa" in self.selected_satellite else 4.0 if "Láser" in self.selected_satellite else 5.5
            sat_ang = (self.sat_angle * 0.5 + offset) % (2 * math.pi)
            px = cx + orb_r * math.cos(sat_ang)
            py = cy + orb_r * math.sin(sat_ang)
            
            # Draw orbital path line
            self.canvas_radar.create_oval(cx - orb_r, cy - orb_r, cx + orb_r, cy + orb_r, outline="#1b4332", width=1, dash=(3, 5))
            
            # Draw pulsing dot
            pulse = math.sin(self.sat_angle * 10) * 3 + 6
            self.canvas_radar.create_oval(px - pulse, py - pulse, px + pulse, py + pulse, fill="#52b788", outline="#74c69d", width=1)
            self.canvas_radar.create_text(px + pulse + 5, py, text=self.selected_satellite.split()[0], fill="#ffffff", font=("Segoe UI", 8, "bold"), anchor="w")
            
            # Telemetry text overlay in radar canvas
            self.canvas_radar.create_text(
                15, 15,
                text=f"SATÉLITE: {self.selected_satellite.upper()}\n"
                     f"ESTADO: {sat_data['status']}\n"
                     f"ALTITUD: {sat_data['alt']:,} KM\n"
                     f"LATITUD: {sat_data['lat']:.4f}°\n"
                     f"LONGITUD: {sat_data['lon']:.4f}°",
                fill="#74c69d", font=("Consolas", 10), anchor="nw"
            )
            
        except Exception:
            pass
            
        self.after(50, self.animate_radar)
        
    def live_telemetry_worker(self):
        import random
        while self.active:
            time.sleep(random.randint(3, 6))
            if not self.winfo_exists():
                break
                
            # Randomly fluctuate lat/lon coordinates
            sat_data = self.satellites_db[self.selected_satellite]
            sat_data["lat"] = max(-90.0, min(90.0, sat_data["lat"] + random.uniform(-0.02, 0.02)))
            sat_data["lon"] = (sat_data["lon"] + random.uniform(-0.05, 0.05) + 180) % 360 - 180
            
            # Random log entries
            logs = [
                f"Corrección de vector orbital ejecutada. Delta-V: +{random.uniform(0.01, 0.05):.3f} m/s.",
                f"Ping de latencia de enlace descendente: {random.randint(120, 350)} ms.",
                "Estructura térmica estable dentro del rango de operación.",
                f"Carga de baterías solares: {random.randint(92, 100)}%.",
                f"Intensidad de señal del transpondedor: {random.randint(80, 100)}%."
            ]
            self.log_message(random.choice(logs))
            
    def destroy(self):
        self.active = False
        super().destroy()


class AppConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent, app_index):
        super().__init__(parent)
        self.parent = parent
        self.app_index = app_index
        
        self.title("Configuración de Aplicación")
        self.geometry("450x300")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        # Get App details
        self.app = self.parent.config["apps"][self.app_index]
        self.app_name = self.app.get("name", "")
        self.app_path = self.app.get("path", "")
        self.app_id = self.app.get("id") # None for non-native
        
        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        main_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541")
        main_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        # Title
        lbl_title = ctk.CTkLabel(main_f, text=f"CONFIGURACIÓN: {self.app_name.upper()}", font=("Segoe UI", 13, "bold"), text_color="#00e5ff")
        lbl_title.pack(anchor="w", padx=20, pady=(15, 10))
        
        # Name Entry
        lbl_name = ctk.CTkLabel(main_f, text="Nombre de la Aplicación:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_name.pack(anchor="w", padx=20, pady=(5, 2))
        
        self.ent_name = ctk.CTkEntry(main_f, placeholder_text="Nombre...", width=360)
        self.ent_name.pack(anchor="w", padx=20, pady=(0, 10))
        self.ent_name.insert(0, self.app_name)
        
        # Path Entry
        lbl_path = ctk.CTkLabel(main_f, text="Ruta o Ejecutable del Sistema:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_path.pack(anchor="w", padx=20, pady=(5, 2))
        
        path_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        self.ent_path = ctk.CTkEntry(path_frame, placeholder_text="Ruta...", width=260)
        self.ent_path.pack(side="left")
        self.ent_path.insert(0, self.app_path)
        
        # Browse Button
        def browse_path():
            p = filedialog.askopenfilename(
                title="Seleccionar Ejecutable",
                filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
            )
            if p:
                self.ent_path.delete(0, "end")
                self.ent_path.insert(0, p)
                
        btn_browse = ctk.CTkButton(
            path_frame, text="Examinar", font=("Segoe UI", 10),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            width=80, command=browse_path
        )
        btn_browse.pack(side="right")
        
        # Action Buttons Frame
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 10))
        
        # Save Button
        btn_save = ctk.CTkButton(
            btn_frame, text="Guardar", font=("Segoe UI", 11, "bold"),
            fg_color="#2ed573", hover_color="#26af5f", text_color="#0a0f1d",
            width=110, command=self.save_changes
        )
        btn_save.pack(side="left", padx=(0, 5))
        
        # Cancel Button
        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancelar", font=("Segoe UI", 11, "bold"),
            fg_color="#718093", hover_color="#57606f", text_color="#ffffff",
            width=110, command=self.destroy
        )
        btn_cancel.pack(side="left", padx=5)
        
        # Delete Button
        btn_del = ctk.CTkButton(
            btn_frame, text="Eliminar", font=("Segoe UI", 11, "bold"),
            fg_color="#ff4757", hover_color="#ff6b81", text_color="#ffffff",
            width=110, command=self.delete_app
        )
        btn_del.pack(side="right")
        
    def save_changes(self):
        new_name = self.ent_name.get().strip()
        new_path = self.ent_path.get().strip()
        
        if not new_name:
            messagebox.showerror("Error", "El nombre de la aplicación no puede estar vacío.")
            return
            
        apps = self.parent.config.get("apps", [])
        
        for i, app in enumerate(apps):
            if i != self.app_index and app.get("name", "").lower() == new_name.lower():
                messagebox.showerror("Error", f"Ya existe otra aplicación registrada con el nombre '{new_name}'.")
                return
                
        apps[self.app_index]["name"] = new_name
        apps[self.app_index]["path"] = new_path
        
        self.parent.config["apps"] = apps
        save_config(self.parent.config)
        
        self.parent.refresh_apps_list()
        self.parent.console_log(f"Aplicación editada: {new_name}")
        self.destroy()
        
    def delete_app(self):
        if self.app_id:
            messagebox.showerror("Error", f"La aplicación del sistema '{self.app_name}' no puede ser eliminada.")
            return
            
        if not messagebox.askyesno("Eliminar Aplicación", f"¿Desea eliminar la aplicación '{self.app_name}' de la consola?"):
            return
            
        apps = self.parent.config.get("apps", [])
        apps.pop(self.app_index)
        self.parent.config["apps"] = apps
        save_config(self.parent.config)
        
        self.parent.refresh_apps_list()
        self.parent.console_log(f"Aplicación eliminada: {self.app_name}")
        self.destroy()


class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window properties
        self.title("J.A.R.V.I.S. - Centro de Operaciones Stark")
        self.geometry("1100x700")
        self.minsize(950, 600)
        
        # Load configuration
        self.config = load_config()
        
        # Initialize Gemini API client if API key exists
        self.jarvis_ai = None
        self.init_gemini_client()
        
        # Setup Layout grid
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main View
        self.grid_rowconfigure(0, weight=1)
        
        # Tracks active view
        self.active_frame = None
        self.active_button = None
        
        # Build UI Components
        self.setup_sidebar()
        self.setup_views()
        
        # Show default tab (Chat)
        self.show_view("chat", self.btn_tab_chat)

    def init_gemini_client(self):
        """Initializes the JarvisAI gemini client in a separate thread if API Key exists."""
        api_key = self.config.get("gemini_api_key")
        model = self.config.get("gemini_model", "gemini-3.5-flash")
        sys_prompt = self.config.get("system_prompt")
        
        if api_key:
            try:
                def open_app_callback(app_name):
                    return self.open_app_by_name(app_name)
                    
                self.jarvis_ai = JarvisAI(
                    api_key=api_key,
                    model_name=model,
                    system_instruction=sys_prompt,
                    open_app_callback=open_app_callback
                )
                logger.info("Gemini AI Client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
                self.jarvis_ai = None
        else:
            self.jarvis_ai = None

    def setup_sidebar(self):
        """Creates the sidebar frame with title and navigation buttons."""
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#0a0f1d")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(0, weight=0) # Title
        self.sidebar_frame.grid_rowconfigure(1, weight=1) # Buttons Navigation
        self.sidebar_frame.grid_rowconfigure(2, weight=0) # Status Indicator
        
        # Title / Logo
        self.logo_lbl = ctk.CTkLabel(
            self.sidebar_frame, 
            text="J.A.R.V.I.S.", 
            font=("Segoe UI", 26, "bold"), 
            text_color="#00e5ff"
        )
        self.logo_lbl.grid(row=0, column=0, padx=20, pady=(30, 5))
        
        self.subtitle_lbl = ctk.CTkLabel(
            self.sidebar_frame, 
            text="STARK INDUSTRIES", 
            font=("Segoe UI", 9, "bold"), 
            text_color="#ffb300"
        )
        self.subtitle_lbl.grid(row=0, column=0, padx=20, pady=(60, 20))
        
        # Navigation Buttons Frame
        self.nav_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.nav_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Chat Button
        self.btn_tab_chat = ctk.CTkButton(
            self.nav_frame,
            text="💬   Chat",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            height=40,
            fg_color="transparent",
            text_color="#a5b1c2",
            hover_color="#1e272e",
            command=lambda: self.show_view("chat", self.btn_tab_chat)
        )
        self.btn_tab_chat.pack(fill="x", pady=5)
        
        # Apps Button
        self.btn_tab_apps = ctk.CTkButton(
            self.nav_frame,
            text="🚀   Apps",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            height=40,
            fg_color="transparent",
            text_color="#a5b1c2",
            hover_color="#1e272e",
            command=lambda: self.show_view("apps", self.btn_tab_apps)
        )
        self.btn_tab_apps.pack(fill="x", pady=5)
        
        # Config Button
        self.btn_tab_config = ctk.CTkButton(
            self.nav_frame,
            text="⚙️   Configuración",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            height=40,
            fg_color="transparent",
            text_color="#a5b1c2",
            hover_color="#1e272e",
            command=lambda: self.show_view("config", self.btn_tab_config)
        )
        self.btn_tab_config.pack(fill="x", pady=5)
        
        # Status / Connection indicator at the bottom of sidebar
        self.status_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#0e1726", height=60, corner_radius=8)
        self.status_frame.grid(row=2, column=0, padx=15, pady=20, sticky="ew")
        self.status_frame.pack_propagate(False)
        
        self.status_title = ctk.CTkLabel(
            self.status_frame, 
            text="ESTADO DEL SISTEMA", 
            font=("Segoe UI", 10, "bold"), 
            text_color="#57606f"
        )
        self.status_title.pack(anchor="w", padx=10, pady=(5, 2))
        
        # Gemini Status Line
        self.gemini_status_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        self.gemini_status_frame.pack(fill="x", padx=10)
        
        self.gemini_dot = ctk.CTkLabel(self.gemini_status_frame, text="●", text_color="red", font=("Segoe UI", 14))
        self.gemini_dot.pack(side="left")
        self.gemini_status_lbl = ctk.CTkLabel(self.gemini_status_frame, text=" Gemini: Desconectado", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.gemini_status_lbl.pack(side="left")
        
        self.update_system_status()

    def update_system_status(self):
        """Updates the visual status dots and labels for Gemini."""
        if self.jarvis_ai:
            self.gemini_dot.configure(text_color="#00e5ff")
            self.gemini_status_lbl.configure(text=" Gemini: Conectado")
        else:
            self.gemini_dot.configure(text_color="#ff4757")
            self.gemini_status_lbl.configure(text=" Gemini: Clave requerida")

    def setup_views(self):
        """Pre-initializes the views (frames) in the main display area."""
        self.views_container = ctk.CTkFrame(self, fg_color="#0f1423")
        self.views_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.views_container.grid_columnconfigure(0, weight=1)
        self.views_container.grid_rowconfigure(0, weight=1)
        
        # Initialize different view frames
        self.view_chat = self.create_chat_view()
        self.view_apps = self.create_apps_view()
        self.view_config = self.create_config_view()

    def show_view(self, view_name, button_trigger):
        """Handles switching between frames and button highlight styles."""
        # Highlight button trigger
        if self.active_button:
            self.active_button.configure(fg_color="transparent", text_color="#a5b1c2")
        
        button_trigger.configure(fg_color="#1b2538", text_color="#00e5ff")
        self.active_button = button_trigger
        
        # Hide active view
        if self.active_frame:
            self.active_frame.grid_forget()
            
        # Show new view
        if view_name == "chat":
            self.active_frame = self.view_chat
        elif view_name == "apps":
            self.active_frame = self.view_apps
            self.refresh_apps_list()
        elif view_name == "config":
            self.active_frame = self.view_config
            self.load_config_values_into_fields()
            
        self.active_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.update_system_status()

    # ==========================================
    # VIEW: CHAT INTERFACE
    # ==========================================
    def create_chat_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0) # Header
        frame.grid_rowconfigure(1, weight=1) # Chat History
        frame.grid_rowconfigure(2, weight=0) # Suggestions
        frame.grid_rowconfigure(3, weight=0) # Input Area
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title = ctk.CTkLabel(header, text="CONSOLA DE COMUNICACIÓN", font=("Segoe UI", 18, "bold"), text_color="#00e5ff")
        title.pack(anchor="w")
        subtitle = ctk.CTkLabel(header, text="Enlace directo con el asistente de Inteligencia Artificial J.A.R.V.I.S.", font=("Segoe UI", 11), text_color="#57606f")
        subtitle.pack(anchor="w")
        
        # Chat History Scrollable Frame
        self.chat_scroll = ctk.CTkScrollableFrame(frame, fg_color="#080c16", border_width=1, border_color="#1b2538")
        self.chat_scroll.grid(row=1, column=0, sticky="nsew", pady=5)
        
        # Add welcome message
        self.add_chat_bubble("J.A.R.V.I.S.", "Conexión establecida, Señor. Todos los sistemas en línea. ¿En qué puedo asistirle el día de hoy?")
        
        # Quick suggestions frame
        self.suggest_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.suggest_frame.grid(row=2, column=0, sticky="ew", pady=5)
        
        suggestions = [
            "Crear proyecto de Blender 'Armadura_Mark85'",
            "¿Cómo está el estado de la armadura?",
            "Activar propulsores y el HUD de la armadura",
            "Ayúdame a modelar un casco en 3D"
        ]
        
        for i, text in enumerate(suggestions):
            btn = ctk.CTkButton(
                self.suggest_frame, 
                text=text, 
                font=("Segoe UI", 10), 
                fg_color="#101827", 
                hover_color="#1e272e",
                text_color="#00e5ff",
                border_width=1, 
                border_color="#1b2538",
                corner_radius=15,
                height=26,
                command=lambda t=text: self.send_suggestion(t)
            )
            btn.pack(side="left", padx=5)

        # Input Area Frame
        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_columnconfigure(1, weight=0)
        
        self.chat_input = ctk.CTkEntry(
            input_frame, 
            placeholder_text="Ingrese comando o consulta para Jarvis...", 
            font=("Segoe UI", 13),
            fg_color="#0b0f19",
            border_color="#1b2538",
            height=40
        )
        self.chat_input.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.chat_input.bind("<Return>", lambda event: self.send_user_message())
        
        self.btn_send = ctk.CTkButton(
            input_frame, 
            text="ENVIAR", 
            font=("Segoe UI", 12, "bold"),
            fg_color="#00a8ff",
            hover_color="#00c0ff",
            width=100,
            height=40,
            command=self.send_user_message
        )
        self.btn_send.grid(row=0, column=1, sticky="e")
        
        return frame

    def add_chat_bubble(self, sender, text):
        """Adds a beautiful chat bubble aligned based on the sender."""
        # Bubble container
        align = "w" if sender == "J.A.R.V.I.S." else "e"
        bg_col = "#0d1b2a" if sender == "J.A.R.V.I.S." else "#1e272e"
        border_col = "#00e5ff" if sender == "J.A.R.V.I.S." else "#ffb300"
        text_col = "#00e5ff" if sender == "J.A.R.V.I.S." else "#ffb300"
        
        bubble_outer = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        bubble_outer.pack(fill="x", padx=10, pady=5)
        
        bubble = ctk.CTkFrame(bubble_outer, fg_color=bg_col, border_width=1, border_color=border_col)
        bubble.pack(side="left" if sender == "J.A.R.V.I.S." else "right", padx=(5, 50) if sender == "J.A.R.V.I.S." else (50, 5))
        
        # Name tag
        lbl_sender = ctk.CTkLabel(bubble, text=sender, font=("Segoe UI", 11, "bold"), text_color=text_col)
        lbl_sender.pack(anchor="w", padx=12, pady=(6, 2))
        
        # Text label (supports line wrapping)
        lbl_text = ctk.CTkLabel(
            bubble, 
            text=text, 
            font=("Segoe UI", 13), 
            text_color="#ffffff" if sender == "J.A.R.V.I.S." else "#ecf0f1",
            justify="left", 
            wraplength=550
        )
        lbl_text.pack(anchor="w", padx=12, pady=(0, 8))
        
        # Double click to copy feature
        bubble.bind("<Double-1>", lambda e, t=text: self.copy_to_clipboard(t))
        lbl_text.bind("<Double-1>", lambda e, t=text: self.copy_to_clipboard(t))
        
        # Scroll to bottom
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        # Visual hint
        self.show_toast("Texto copiado al portapapeles")

    def show_toast(self, text):
        toast = ctk.CTkToplevel(self)
        toast.geometry("250x40")
        toast.overrideredirect(True)
        toast.configure(fg_color="#0a0f1d")
        
        # Center toast
        x = self.winfo_x() + (self.winfo_width() - 250) // 2
        y = self.winfo_y() + self.winfo_height() - 100
        toast.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(toast, text=text, font=("Segoe UI", 12, "bold"), text_color="#00e5ff")
        lbl.pack(expand=True)
        
        # Fade out
        self.after(1500, toast.destroy)

    def send_suggestion(self, text):
        self.chat_input.delete(0, "end")
        self.chat_input.insert(0, text)
        self.send_user_message()

    def send_user_message(self):
        message = self.chat_input.get().strip()
        if not message:
            return
            
        self.chat_input.delete(0, "end")
        self.add_chat_bubble("Usuario", message)
        
        if not self.jarvis_ai:
            self.add_chat_bubble(
                "J.A.R.V.I.S.", 
                "Señor, no puedo procesar su solicitud. La clave de API de Gemini no está configurada. "
                "Por favor, diríjase a la pestaña de Configuración para ingresarla."
            )
            return
            
        # UI Feedback during processing
        self.btn_send.configure(state="disabled", text="PENSANDO...")
        
        # Run API request in background thread
        threading.Thread(target=self.process_ai_response, args=(message,), daemon=True).start()

    def process_ai_response(self, message):
        try:
            response = self.jarvis_ai.send_message(message)
            # Update UI on main thread
            self.after(0, lambda: self.add_chat_bubble("J.A.R.V.I.S.", response))
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            self.after(0, lambda: self.add_chat_bubble(
                "J.A.R.V.I.S.", 
                f"Lo siento, señor. He experimentado una anomalía en mi núcleo de comunicación. Error: {str(e)}"
            ))
        finally:
            self.after(0, lambda: self.btn_send.configure(state="normal", text="ENVIAR"))

    # ==========================================
    # VIEW: APPS
    # ==========================================
    def create_apps_view(self):
        """Creates the Apps view showing registered programs with open button and an add app button."""
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0) # Header
        frame.grid_rowconfigure(1, weight=1) # Apps Scroll list
        frame.grid_rowconfigure(2, weight=0) # Bottom Actions (Add app)
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        title = ctk.CTkLabel(header, text="CENTRAL DE APLICACIONES", font=("Segoe UI", 18, "bold"), text_color="#00e5ff")
        title.pack(anchor="w")
        subtitle = ctk.CTkLabel(header, text="Gestione y ejecute programas locales desde la interfaz de J.A.R.V.I.S.", font=("Segoe UI", 11), text_color="#57606f")
        subtitle.pack(anchor="w")
        
        # Apps Scroll list container
        self.apps_list_container = ctk.CTkFrame(frame, fg_color="#080c16", border_width=1, border_color="#1b2538")
        self.apps_list_container.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        self.apps_list_container.grid_columnconfigure(0, weight=1)
        self.apps_list_container.grid_rowconfigure(0, weight=1)
        
        self.apps_scroll = ctk.CTkScrollableFrame(self.apps_list_container, fg_color="transparent")
        self.apps_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Bottom controls
        actions_f = ctk.CTkFrame(frame, fg_color="transparent")
        actions_f.grid(row=2, column=0, sticky="ew")
        
        self.btn_add_app = ctk.CTkButton(
            actions_f, 
            text="+ Registrar Nueva Aplicación", 
            font=("Segoe UI", 13, "bold"),
            fg_color="#00e5ff", 
            hover_color="#00a8ff",
            text_color="#0a0f1d",
            command=self.open_add_app_popup
        )
        self.btn_add_app.pack(side="left", padx=5, pady=5)
        
        # Load list initially
        self.refresh_apps_list()
        
        return frame
        
    def refresh_apps_list(self):
        """Re-draws the list of apps inside self.apps_scroll."""
        for widget in self.apps_scroll.winfo_children():
            widget.destroy()
            
        apps = self.config.get("apps", [])
        
        if not apps:
            lbl_empty = ctk.CTkLabel(
                self.apps_scroll, 
                text="No hay aplicaciones registradas en este momento.", 
                font=("Segoe UI", 12, "italic"),
                text_color="#57606f"
            )
            lbl_empty.pack(pady=40)
            return
            
        for i, app in enumerate(apps):
            app_name = app.get("name", "Desconocido")
            app_path = app.get("path", "")
            
            row_frame = ctk.CTkFrame(self.apps_scroll, fg_color="#0d1423", border_width=1, border_color="#1b2538", height=60)
            row_frame.pack(fill="x", pady=5)
            row_frame.pack_propagate(False)
            
            info_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=8)
            
            lbl_name = ctk.CTkLabel(
                info_frame, 
                text=app_name, 
                font=("Segoe UI", 13, "bold"), 
                text_color="#ffffff"
            )
            lbl_name.pack(anchor="w")
            
            lbl_path = ctk.CTkLabel(
                info_frame, 
                text=app_path or "[Ruta no especificada]", 
                font=("Consolas", 10), 
                text_color="#718093",
                anchor="w"
            )
            lbl_path.pack(anchor="w")
            
            # Open Button
            btn_open = ctk.CTkButton(
                row_frame, 
                text="Abrir", 
                font=("Segoe UI", 11, "bold"),
                fg_color="#38ef7d", 
                hover_color="#11998e",
                text_color="#0a0f1d",
                width=80,
                command=lambda name=app_name: self.open_app_by_name(name)
            )
            btn_open.pack(side="right", padx=15, pady=15)
            
            # Config Button ⚙️
            btn_cfg = ctk.CTkButton(
                row_frame, 
                text="⚙️", 
                font=("Segoe UI", 12, "bold"),
                fg_color="#1c2541", 
                hover_color="#3a0ca3",
                text_color="#ffffff",
                width=40,
                command=lambda idx=i: self.open_app_config_popup(idx)
            )
            btn_cfg.pack(side="right", padx=5, pady=15)

    def remove_app_by_name(self, app_name):
        if app_name.lower() in ("image-to-model", "domotica", "iron man", "satelites"):
            messagebox.showerror("Error", f"La aplicación del sistema '{app_name}' no puede ser eliminada.")
            return
        if not messagebox.askyesno("Eliminar Aplicación", f"¿Desea eliminar la aplicación '{app_name}' de la consola?"):
            return
        apps = self.config.get("apps", [])
        new_apps = [app for app in apps if app.get("name") != app_name]
        self.config["apps"] = new_apps
        save_config(self.config)
        self.refresh_apps_list()
        self.console_log(f"Aplicación eliminada de la consola: {app_name}")

    def open_app_config_popup(self, app_index):
        """Opens the configuration modal window for a specific app."""
        self.console_log(f"Abriendo panel de configuración para la aplicación en el índice {app_index}...")
        self.after(0, lambda: AppConfigWindow(self, app_index))

    def open_add_app_popup(self):
        """Displays a dialog box to register a new application."""
        name_dialog = ctk.CTkInputDialog(text="Nombre de la Aplicación:", title="Agregar Aplicación")
        app_name = name_dialog.get_input()
        if not app_name:
            return
            
        app_name = app_name.strip()
        if not app_name:
            return
            
        path = filedialog.askopenfilename(
            title=f"Seleccionar Ejecutable para '{app_name}'",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if not path:
            return
            
        apps = self.config.get("apps", [])
        for app in apps:
            if app.get("name", "").lower() == app_name.lower():
                messagebox.showerror("Error", f"Ya existe una aplicación registrada con el nombre '{app_name}'.")
                return
                
        apps.append({"name": app_name, "path": path})
        self.config["apps"] = apps
        save_config(self.config)
        self.refresh_apps_list()
        self.console_log(f"Nueva aplicación registrada: {app_name} -> {path}")
        messagebox.showinfo("Éxito", f"La aplicación '{app_name}' ha sido registrada con éxito.")

    def open_app_by_name(self, app_name):
        """Launches the external application or system program."""
        name_lower = app_name.lower().strip()
        
        apps = self.config.get("apps", [])
        target_app = None
        for app in apps:
            if app.get("name", "").lower() == name_lower or app.get("id", "").lower() == name_lower:
                target_app = app
                break
                
        if target_app and target_app.get("id"):
            app_id = target_app["id"].lower().strip()
            if app_id == "image-to-model":
                self.console_log("Abriendo aplicación nativa Image-to-model...")
                self.after(0, lambda: ImageToModelWindow(self))
                return "Éxito: Se ha inicializado la aplicación nativa Image-to-model."
            elif app_id == "domotica":
                self.console_log("Abriendo aplicación nativa Domótica...")
                self.after(0, lambda: DomoticaWindow(self))
                return "Éxito: Se ha inicializado la aplicación nativa Domótica."
            elif app_id == "iron man":
                self.console_log("Abriendo simulador de traje Iron Man...")
                self.after(0, lambda: IronmanWindow(self))
                return "Éxito: Se ha inicializado el simulador de traje Iron Man."
            elif app_id == "satelites":
                self.console_log("Abriendo radar de satélites...")
                self.after(0, lambda: SatellitesWindow(self))
                return "Éxito: Se ha inicializado el radar de satélites."
                
        # Fallback matches
        if name_lower == "image-to-model" or name_lower == "image to model":
            self.console_log("Abriendo aplicación nativa Image-to-model...")
            self.after(0, lambda: ImageToModelWindow(self))
            return "Éxito: Se ha inicializado la aplicación nativa Image-to-model."
        elif name_lower == "domotica":
            self.console_log("Abriendo aplicación nativa Domótica...")
            self.after(0, lambda: DomoticaWindow(self))
            return "Éxito: Se ha inicializado la aplicación nativa Domótica."
        elif name_lower in ("iron man", "ironman"):
            self.console_log("Abriendo simulador de traje Iron Man...")
            self.after(0, lambda: IronmanWindow(self))
            return "Éxito: Se ha inicializado el simulador de traje Iron Man."
        elif name_lower in ("satelites", "satélite", "satélites"):
            self.console_log("Abriendo radar de satélites...")
            self.after(0, lambda: SatellitesWindow(self))
            return "Éxito: Se ha inicializado el radar de satélites."
                
        if not target_app:
            error_msg = f"La aplicación '{app_name}' no se encuentra registrada en la central de aplicaciones."
            self.console_log(error_msg)
            return f"Error: {error_msg}"
            
        path = target_app.get("path", "").strip()
        
        import shutil, subprocess
        try:
            if path and os.path.exists(path):
                self.console_log(f"Abriendo aplicación externa: {app_name} ({path})...")
                subprocess.Popen([path], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                return f"Éxito: Se ha lanzado '{app_name}' desde su ruta física."
            else:
                self.console_log(f"Ruta física no encontrada para '{app_name}'. Intentando ejecución directa en shell...")
                resolved_cmd = shutil.which(name_lower)
                if not resolved_cmd and name_lower == "chrome":
                    resolved_cmd = shutil.which("chrome") or shutil.which("google-chrome")
                if not resolved_cmd and name_lower == "blender":
                    resolved_cmd = shutil.which("blender")
                    
                exec_cmd = resolved_cmd if resolved_cmd else name_lower
                subprocess.Popen(exec_cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                return f"Éxito: Se lanzó '{app_name}' a través de alias del sistema."
        except Exception as e:
            error_msg = f"Excepción al ejecutar la aplicación '{app_name}': {str(e)}"
            self.console_log(error_msg)
            return f"Error: {error_msg}"

    def console_log(self, text):
        logger.info(text)

    # ==========================================
    # VIEW: CONFIGURATION
    # ==========================================
    def create_config_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0) # Header
        frame.grid_rowconfigure(1, weight=1) # Scrollable Content
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title = ctk.CTkLabel(header, text="CENTRAL DE CONFIGURACIÓN", font=("Segoe UI", 18, "bold"), text_color="#00e5ff")
        title.pack(anchor="w")
        subtitle = ctk.CTkLabel(header, text="Configure las credenciales de conexión para el asistente conversacional J.A.R.V.I.S.", font=("Segoe UI", 11), text_color="#57606f")
        subtitle.pack(anchor="w")
        
        # Scrollable container for properties
        scroll_body = ctk.CTkScrollableFrame(frame, fg_color="#080c16", border_width=1, border_color="#1b2538")
        scroll_body.grid(row=1, column=0, sticky="nsew", pady=5)
        scroll_body.grid_columnconfigure(0, weight=1)
        
        # 1. API KEY SECTION
        lbl_sec_api = ctk.CTkLabel(scroll_body, text="CREDENCIALES Y MODELO DE GEMINI AI", font=("Segoe UI", 13, "bold"), text_color="#00e5ff")
        lbl_sec_api.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Gemini API Entry
        self.lbl_api_key = ctk.CTkLabel(scroll_body, text="Gemini API Key:", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.lbl_api_key.pack(anchor="w", padx=25, pady=2)
        
        self.ent_api_key = ctk.CTkEntry(scroll_body, placeholder_text="AIzaSy...", width=600, show="*")
        self.ent_api_key.pack(anchor="w", padx=25, pady=(0, 10))
        
        # Gemini Model Selector
        self.lbl_model_sel = ctk.CTkLabel(scroll_body, text="Modelo de Gemini:", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.lbl_model_sel.pack(anchor="w", padx=25, pady=2)
        
        # Add stable 2026/2025 and fallbacks
        self.opt_model = ctk.CTkOptionMenu(
            scroll_body, 
            values=[
                "gemini-3.5-flash", 
                "gemini-3.5-flash-lite", 
                "gemini-3.6-flash", 
                "gemini-3.1-pro", 
                "gemini-3.1-flash-lite", 
                "gemini-3-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ],
            width=250
        )
        self.opt_model.pack(anchor="w", padx=25, pady=(0, 20))
        
        # Save Configuration Button
        self.btn_save_config = ctk.CTkButton(
            scroll_body, 
            text="GUARDAR CONFIGURACIÓN Y CONECTAR SISTEMA", 
            font=("Segoe UI", 13, "bold"),
            fg_color="#00a8ff", 
            hover_color="#00c0ff",
            height=40,
            command=self.save_config_from_fields
        )
        self.btn_save_config.pack(anchor="w", padx=25, pady=(10, 30))
        
        return frame

    def load_config_values_into_fields(self):
        """Fills entry widgets with current config values when Tab Config is opened."""
        self.ent_api_key.delete(0, "end")
        self.ent_api_key.insert(0, self.config.get("gemini_api_key", ""))
        
        # Set selection menu
        model = self.config.get("gemini_model", "gemini-3.5-flash")
        if model in self.opt_model._values:
            self.opt_model.set(model)

    def save_config_from_fields(self):
        """Saves values from entries to local file and updates current state."""
        self.config["gemini_api_key"] = self.ent_api_key.get().strip()
        self.config["gemini_model"] = self.opt_model.get()
        
        if save_config(self.config):
            messagebox.showinfo("Configuración Guardada", "La configuración ha sido persistida con éxito.")
            # Reconnect Gemini
            self.init_gemini_client()
            self.update_system_status()
        else:
            messagebox.showerror("Error de Guardado", "No se pudo guardar la configuración en el archivo local.")

if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
