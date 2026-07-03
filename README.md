# Detector EPP - Versión Web

Versión web del detector de EPP (casco blanco + chaleco naranja). La cámara
la captura el **navegador** del usuario; el servidor solo procesa los
fotogramas con YOLOv8 + OpenCV y devuelve el resultado. Por eso sí puede
desplegarse en un servicio en la nube como Render (a diferencia del script
original, que abría la webcam local y una ventana de escritorio).

## Estructura

```
epp-web/
├── app.py                 # Backend Flask (detección)
├── templates/index.html   # Página principal
├── static/css/style.css
├── static/js/main.js      # Captura de cámara + dibujo de resultados
├── requirements.txt
├── Procfile                # Comando de arranque para Render
└── render.yaml              # Blueprint opcional de Render
```

## 1. Probar en tu computadora (opcional, recomendado)

```bash
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abre `http://localhost:5000` en el navegador y da permiso de cámara.
(La primera vez tardará un poco: descarga el modelo `yolov8n.pt`).

## 2. Subir el código a GitHub

1. Crea una cuenta en https://github.com si no tienes una.
2. Crea un repositorio nuevo (botón verde "New"), por ejemplo `detector-epp`,
   vacío (sin README, sin .gitignore — ya los trae esta carpeta).
3. En tu computadora, dentro de esta carpeta `epp-web`, ejecuta:

```bash
git init
git add .
git commit -m "Detector EPP - version web"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/detector-epp.git
git push -u origin main
```

(Reemplaza `TU_USUARIO` por tu usuario de GitHub y `detector-epp` por el
nombre que le hayas puesto al repositorio).

## 3. Desplegar en Render

1. Entra a https://render.com y crea una cuenta (puedes usar tu cuenta de
   GitHub para registrarte, así quedan conectadas automáticamente).
2. En el Dashboard, clic en **New +** → **Web Service**.
3. Selecciona el repositorio `detector-epp` que acabas de subir (si no
   aparece, usa "Configure account" para darle permiso a Render sobre ese
   repo).
4. Configura:
   - **Name**: `detector-epp` (o el que prefieras)
   - **Region**: la más cercana a tus usuarios
   - **Branch**: `main`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --timeout 120 --workers 1 --worker-class gthread --threads 4`
   - **Instance Type**: ver nota importante abajo
5. Clic en **Create Web Service**. Render instalará las dependencias y
   arrancará la app. La primera build puede tardar varios minutos porque
   instala `torch`/`ultralytics`.
6. Cuando termine, Render te da una URL pública tipo
   `https://detector-epp.onrender.com`. Ábrela, da permiso de cámara y
   listo.

Si prefieres no llenar el formulario a mano, Render también puede leer el
archivo `render.yaml` incluido: al crear el servicio elige **"Apply from
render.yaml"** (Blueprint) en vez de configurarlo campo por campo.

### ⚠️ Sobre el detector de personas (actualizado)

La primera versión de esta app usaba YOLOv8 (librería `ultralytics`), que
depende de PyTorch. PyTorch consume varios cientos de MB de RAM solo para
cargar el modelo, lo cual **excede la memoria del plan gratuito de Render
(512 MB)** y hacía que el servidor se cayera (502 Bad Gateway) apenas
llegaba la primera petición a `/detect`.

Por eso el backend ahora usa el detector de personas **HOG + SVM** que trae
OpenCV incorporado (`cv2.HOGDescriptor`). Ventajas:
- No requiere PyTorch ni descargar ningún modelo externo.
- Consume solo unos pocos MB de RAM → **sí funciona en el plan gratuito**.
- Arranca instantáneamente (no hay descarga de pesos la primera vez).

Contras (a tener en cuenta):
- Es menos preciso que YOLOv8: funciona mejor con la persona de cuerpo casi
  completo o al menos de torso hacia arriba, bien iluminada y sin mucho
  fondo desordenado. Puede fallar si la persona está muy cerca de la
  cámara, de perfil, o con poca luz.
- Si quieres ajustar la sensibilidad, en `app.py` puedes tocar los
  parámetros de `detectar_personas()`:
  - `ANCHO_PROCESO`: más alto = más preciso pero más lento.
  - `scale` (en `detectMultiScale`): más cercano a 1.0 = más preciso pero
    más lento (prueba 1.03-1.05).
  - `winStride`/`padding`: valores más chicos = más preciso pero más lento.

## 4. Cómo funciona (resumen técnico)

- El navegador pide permiso de cámara con `getUserMedia` y muestra el video
  en un `<video>`.
- Cada ~600 ms, JavaScript captura el fotograma actual en un `<canvas>`
  oculto, lo convierte a JPEG en base64 y lo envía por `POST /detect`.
- El backend Flask decodifica la imagen, detecta personas con el detector
  HOG+SVM de OpenCV y, para cada una, aplica exactamente las mismas
  funciones `detectar_casco()` y `detectar_chaleco()` del script original
  (brillo + neutralidad cromática + simetría para el casco; rangos HSV
  calibrados para el chaleco naranja-salmón).
- El backend responde con las coordenadas de cada persona y su estado de
  EPP en JSON.
- El navegador dibuja los recuadros y el panel de estado sobre un
  `<canvas>` superpuesto al video, replicando el look del script original
  (colores, panel "EPP STATUS", alerta parpadeante cuando falta algo).
