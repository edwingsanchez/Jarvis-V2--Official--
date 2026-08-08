# J.A.R.V.I.S. V2 - Centro de Operaciones Stark (Official)

J.A.R.V.I.S. V2 (Just A Rather Very Intelligent System) es un asistente personal de inteligencia artificial de escritorio diseñado con la estética premium y futurista del traje de Iron Man y las industrias Stark. Desarrollado en Python con CustomTkinter, integra control de domótica real (Home Assistant), modelado 3D en la nube (Tripo3D API) e inteligencia artificial conversacional (Gemini AI), acompañado de simuladores interactivos de la armadura Stark y radar satelital.

---

## Características Principales

### 1. 💬 Interfaz Conversacional Inteligente
*   **Asistente Gemini**: Conexión directa con los modelos de Gemini AI utilizando tu propia API Key.
*   **Tono Stark**: Jarvis responde de forma servicial, sofisticada y con el característico tono tecnológico de asistente personal de Tony Stark.
*   **Function Calling**: Jarvis puede abrir aplicaciones del sistema operativo o lanzar aplicaciones nativas de Stark mediante comandos de voz o texto en lenguaje natural (ej. *"Jarvis, inicia la app de domótica"*).

### 2. 🚀 Central de Aplicaciones Stark
*   Un listado unificado para abrir ejecutables físicos de tu sistema operativo (ej. Chrome, Blender, etc.) y aplicaciones nativas integradas.
*   **Botón ⚙️ de Configuración de Tarjeta**: Cada aplicación de la lista tiene su propio modal emergente (`AppConfigWindow`) que permite:
    *   **Renombrar** la aplicación (ej. cambiar "Domotica" a "Domótica Stark").
    *   **Editar la Ruta** del ejecutable (con selector de archivos integrado).
    *   **Eliminar** la aplicación de la consola (con bloqueos de seguridad estrictos que impiden la eliminación de las aplicaciones nativas del sistema).
*   **Lanzamiento Inteligente por ID**: El sistema mapea las aplicaciones del sistema mediante un ID interno inmutable, asegurando que sigan abriéndose correctamente incluso si las renombras en la consola.

### 3. 📷 Aplicación Image-to-model (Tripo3D API V3)
*   **Pipeline de Generación Asíncrona**: Sube imágenes locales a los servidores de Tripo3D mediante `POST /v3/files` para obtener un token de archivo.
*   **Generación de Mallas 3D**: Lanza tareas de renderizado 3D en la nube utilizando el modelo V3 compatible (`v3.0-20250812`) a través de `POST /v3/generation/image-to-model`.
*   **Polling Dinámico y Descarga**: Monitorea el progreso con barras y estados de carga en vivo mediante `GET /v3/tasks/{id}`, descarga el archivo binario `.glb` resultante y lo guarda en la carpeta local `models/`.
*   **Visualizador Integrado**: Abre los archivos `.glb` generados directamente en el visor 3D predeterminado del sistema operativo o Blender desde la propia app.

### 4. 🏠 Panel de Domótica (Home Assistant REST API)
*   Panel de control nativo conectado a tu instancia personal de Home Assistant mediante Long-Lived Access Tokens.
*   **Controladores en Tiempo Real**:
    *   💡 **Iluminación (`light.*`)**: Toggles de encendido/apagado rápido.
    *   🔌 **Interruptores (`switch.*`, `input_boolean.*`)**: Toggles para control de energía.
    *   🌡️ **Sensores (`sensor.*`)**: Lecturas de telemetría (temperatura, humedad, energía).
    *   🚪 **Sensores de Seguridad (`binary_sensor.*`)**: Visualiza estados de apertura/cierre o movimiento.
    *   ❄️/🔥 **Climatizadores (`climate.*`)**: Ajusta la temperatura objetivo del termostato con botones nativos `+` y `-`.
*   **Operación Asíncrona**: Optimización visual inmediata en el panel de control y llamadas en segundo plano (`POST /api/services/<domain>/<service>`) para una latencia de control nula.

### 5. 🛡️ Simulador de Armadura: Iron Man
*   Consola interactiva de diagnóstico del traje Mark LXXXV:
    *   **Reactor Arc**: Nivel de energía fluctuante. Incluye comandos interactivos para sobrecargar (125% con alarmas térmicas) o refrigerar el núcleo.
    *   **Repulsores (Manos)**: Botón de fogonazo de prueba con animación de ciclo de disparo (Cargando capacitores -> Disparando -> Enfriando -> Listo).
    *   **Propulsores (Pies)**: Deslizador de potencia que drena la energía del reactor y eleva la temperatura térmica del traje en tiempo real.
    *   **HUD y Combate**: Selector de perfiles HUD y switch de modo combate con realce de alerta en la interfaz.

### 6. 🛰️ Radar de Satélites Stark
*   Sistema de monitoreo de satélites Stark (`Veronica`, `Defensa`, `Comunicación`):
    *   **Radar Orbital Canvas**: Un canvas dinámico que simula un radar militar con rejillas, barrido láser giratorio y la traslación fluida y parpadeante del satélite seleccionado en su órbita.
    *   **Consola de Telemetría**: Caja de logs en vivo que reporta periódicamente las coordenadas fluctuantes (Latitud, Longitud, Altitud) y comandos del satélite.

---

## Configuración y Requisitos

### Requisitos Previos
*   Python 3.10 o superior.
*   Librerías requeridas: `customtkinter`, `pillow`, `requests`.

Para instalar las dependencias:
```bash
pip install customtkinter pillow requests
```

### Ejecución
Para iniciar el panel central de J.A.R.V.I.S. V2:
```bash
python jarvis_app.py
```

### Estructura de Archivos
*   `jarvis_app.py`: Archivo principal que inicializa el hilo de Tkinter y contiene el diseño de todas las ventanas nativas y la lógica de flujo.
*   `gemini_client.py`: Cliente de IA conversacional e inyección de herramientas (Function Calling).
*   `config_manager.py`: Módulo de persistencia y estructuración por defecto de `config.json`.
*   `config.json`: Base de datos de configuración (API Keys, URLs, Tokens y Apps registradas).
*   `models/`: Carpeta del proyecto donde se almacenan y leen físicamente los modelos `.glb` descargados de Tripo3D.

---

## Licencia e Integridad Stark

Desarrollado bajo protocolos de Industrias Stark. Queda prohibida la reproducción no autorizada de la telemetría del Reactor Arc y el despliegue del Láser Orbital de Stark-III sin autorización del creador. 

*J.A.R.V.I.S. V2 - Rediseñado para la eficiencia operativa del Creador.*
