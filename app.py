"""
=============================================================================
DETECTOR EPP - Version Web (Flask)
Misma logica de deteccion de casco/chaleco del script original, adaptada
para recibir fotogramas desde la camara del NAVEGADOR y devolver los
resultados como JSON.

NOTA IMPORTANTE SOBRE EL DETECTOR DE "PERSONA":
Version 1: YOLOv8 (libreria "ultralytics") -> dependia de PyTorch, que
consume varios cientos de MB de RAM y hacia caer el servidor en el plan
gratuito de Render (502 Bad Gateway).

Version 2: HOG+SVM de OpenCV -> no necesita PyTorch, pero esta entrenado
para detectar PEATONES DE CUERPO COMPLETO vistos de lejos (camaras de
seguridad). Con una webcam de laptop, donde la persona esta cerca y solo
se ve cabeza/torso, este detector fallaba con frecuencia.

Version 3 (actual): se reemplaza la deteccion de "persona" por deteccion
de ROSTRO con el clasificador Haar Cascade que trae OpenCV incorporado
(no requiere descargar nada, es instantaneo y muy liviano). A partir del
rectangulo del rostro se estima, con proporciones antropometricas tipicas,
la zona de cabeza (coronilla) y de torso, que es exactamente donde ya
estaban calibradas las funciones detectar_casco() y detectar_chaleco().
Esto es mucho mas confiable para el caso de uso real: una persona cerca
de la camara de una laptop/celular.
=============================================================================
"""

import base64
import time
import os

import cv2
import numpy as np
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

print("Cargando detector de rostros Haar Cascade (OpenCV, sin PyTorch)...")
_cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
face_cascade = cv2.CascadeClassifier(_cascade_path)
print("Detector listo.")


def detectar_personas(frame):
    """Detecta rostros y, a partir de cada uno, estima el recuadro de
    "persona" (cabeza + torso) con proporciones antropometricas tipicas.
    Devuelve una lista de (x1, y1, x2, y2, confianza)."""
    h0, w0 = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    caras = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=6, minSize=(60, 60)
    )

    personas = []
    for (fx, fy, fw, fh) in caras:
        # La cabeza (con casco incluido) empieza bastante antes que el
        # rostro detectado, y el torso se extiende varias veces la altura
        # de la cara hacia abajo.
        cx = fx + fw // 2
        top = fy - int(fh * 0.9)                 # espacio para coronilla/casco
        bottom = fy + int(fh * 6.0)               # hasta la zona de torso/abdomen
        half_w = int(fw * 1.6)                    # ancho de hombros aproximado

        x1 = int(max(0, cx - half_w))
        x2 = int(min(w0, cx + half_w))
        y1 = int(max(0, top))
        y2 = int(min(h0, bottom))

        personas.append((x1, y1, x2, y2, 1.0))
    return personas


# =============================================================================
# CASCO BLANCO (idéntico al script original epp_simple.py)
# =============================================================================
def detectar_casco(roi):
    if roi is None or roi.size == 0:
        return False, 0.0

    h = roi.shape[0]
    zona = roi[0:int(h * 0.18), :]
    if zona.size == 0 or zona.shape[0] < 5:
        return False, 0.0

    hsv = cv2.cvtColor(zona, cv2.COLOR_BGR2HSV)
    mask_brillo = cv2.inRange(hsv, (0, 0, 200), (180, 45, 255))

    b, g, r = cv2.split(zona)
    bgr_max = np.maximum(np.maximum(b, g), r).astype(np.int16)
    bgr_min = np.minimum(np.minimum(b, g), r).astype(np.int16)
    chroma = (bgr_max - bgr_min).astype(np.uint8)
    mask_neutro = cv2.inRange(chroma, 0, 25)

    mask = cv2.bitwise_and(mask_brillo, mask_neutro)

    k = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)
    area_max = 0
    for cnt in contornos:
        area_max = max(area_max, cv2.contourArea(cnt))

    total = zona.shape[0] * zona.shape[1]
    pct = cv2.countNonZero(mask) / total

    ancho_zona = zona.shape[1]
    tercio = max(ancho_zona // 3, 1)
    mask_izq = mask[:, 0:tercio]
    mask_der = mask[:, ancho_zona - tercio:]
    pct_izq = cv2.countNonZero(mask_izq) / mask_izq.size
    pct_der = cv2.countNonZero(mask_der) / mask_der.size
    simetria_ok = pct_izq >= 0.05 and pct_der >= 0.05

    region_ok = area_max > (total * 0.01)
    detectado = pct >= 0.18 and region_ok and simetria_ok

    return detectado, round(pct, 3)


# =============================================================================
# CHALECO NARANJA-SALMON (idéntico al script original epp_simple.py)
# =============================================================================
def detectar_chaleco(roi):
    if roi is None or roi.size == 0:
        return False, 0.0

    h = roi.shape[0]
    zona = roi[int(h * 0.25):int(h * 0.85), :]
    if zona.size == 0:
        return False, 0.0

    hsv = cv2.cvtColor(zona, cv2.COLOR_BGR2HSV)

    mask1 = cv2.inRange(hsv, (0, 120, 160), (6, 255, 255))
    mask2 = cv2.inRange(hsv, (170, 120, 160), (180, 255, 255))
    mask3 = cv2.inRange(hsv, (8, 130, 150), (20, 255, 255))

    mask = cv2.bitwise_or(mask1, mask2)
    mask = cv2.bitwise_or(mask, mask3)

    k = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)

    total = zona.shape[0] * zona.shape[1]
    pct = cv2.countNonZero(mask) / total

    return pct >= 0.08, round(pct, 3)


def decodificar_imagen(data_url):
    """Convierte un dataURL 'data:image/jpeg;base64,...' enviado por el
    navegador en una imagen OpenCV (BGR)."""
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/detect", methods=["POST"])
def detect():
    t0 = time.time()
    data = request.get_json(silent=True)
    if not data or "image" not in data:
        return jsonify({"error": "Falta el campo 'image'"}), 400

    frame = decodificar_imagen(data["image"])
    if frame is None:
        return jsonify({"error": "No se pudo decodificar la imagen"}), 400

    detecciones = detectar_personas(frame)

    personas = []
    tiene_casco = False
    tiene_chaleco = False

    for (x1, y1, x2, y2, conf) in detecciones:
        roi = frame[max(0, y1):y2, max(0, x1):x2]

        casco_ok, pct_c = detectar_casco(roi)
        chaleco_ok, pct_ch = detectar_chaleco(roi)

        if casco_ok:
            tiene_casco = True
        if chaleco_ok:
            tiene_chaleco = True

        personas.append({
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "conf": round(conf, 3),
            "casco_ok": casco_ok, "pct_casco": pct_c,
            "chaleco_ok": chaleco_ok, "pct_chaleco": pct_ch,
        })

    faltantes = []
    if personas:
        if not tiene_casco:
            faltantes.append("casco")
        if not tiene_chaleco:
            faltantes.append("chaleco")

    return jsonify({
        "personas": personas,
        "n_personas": len(personas),
        "tiene_casco": tiene_casco,
        "tiene_chaleco": tiene_chaleco,
        "faltantes": faltantes,
        "ms": round((time.time() - t0) * 1000),
    })


if __name__ == "__main__":
    # Solo para pruebas locales. En Render se usa gunicorn (ver Procfile).
    app.run(host="0.0.0.0", port=5000, debug=True)
