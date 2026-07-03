const video       = document.getElementById('video');
const overlay     = document.getElementById('overlay');
const ctx         = overlay.getContext('2d');
const stage       = document.getElementById('stage');
const alertaBox   = document.getElementById('alerta');
const btnStart    = document.getElementById('btn-start');
const pPersonas   = document.getElementById('p-personas');
const pCasco      = document.getElementById('p-casco');
const pChaleco    = document.getElementById('p-chaleco');
const estadoGral  = document.getElementById('estado-general');
const latenciaTxt = document.getElementById('latencia');

const INTERVALO_MS = 600; // cada cuánto se envía un fotograma al servidor
let capturando = false;
let parpadeo = true;

// Canvas oculto usado solo para convertir el frame de <video> a JPEG
const capCanvas = document.createElement('canvas');
const capCtx = capCanvas.getContext('2d');

async function iniciarCamara() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480 },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    overlay.width = video.videoWidth || 640;
    overlay.height = video.videoHeight || 480;
    capCanvas.width = overlay.width;
    capCanvas.height = overlay.height;
    capturando = true;
    btnStart.textContent = 'Cámara activa';
    btnStart.disabled = true;
    loop();
    setInterval(() => { parpadeo = !parpadeo; }, 500);
  } catch (err) {
    alert('No se pudo acceder a la cámara: ' + err.message);
  }
}

function capturarFrameB64() {
  capCtx.drawImage(video, 0, 0, capCanvas.width, capCanvas.height);
  return capCanvas.toDataURL('image/jpeg', 0.7);
}

async function loop() {
  if (!capturando) return;
  const t0 = performance.now();
  try {
    const imagen = capturarFrameB64();
    const res = await fetch('/detect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: imagen }),
    });
    const data = await res.json();
    if (!data.error) {
      dibujar(data);
      actualizarPanel(data);
      latenciaTxt.textContent =
        `servidor: ${data.ms} ms · red+total: ${Math.round(performance.now() - t0)} ms`;
    }
  } catch (e) {
    console.error(e);
  }
  setTimeout(loop, INTERVALO_MS);
}

function dibujar(data) {
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  data.personas.forEach(p => {
    const ok = p.casco_ok && p.chaleco_ok;
    ctx.strokeStyle = ok ? '#24d67d' : '#ff3b3b';
    ctx.lineWidth = 2;
    ctx.strokeRect(p.x1, p.y1, p.x2 - p.x1, p.y2 - p.y1);

    ctx.font = '13px Segoe UI, Arial';
    ctx.fillStyle = '#00e6e6';
    ctx.fillText(`Casco ${p.casco_ok ? 'OK' : 'NO'} (${Math.round(p.pct_casco * 100)}%)`,
                 p.x1, Math.max(p.y1 - 22, 12));
    ctx.fillStyle = '#ff8c00';
    ctx.fillText(`Chaleco ${p.chaleco_ok ? 'OK' : 'NO'} (${Math.round(p.pct_chaleco * 100)}%)`,
                 p.x1, Math.max(p.y1 - 6, 26));

    ctx.fillStyle = ok ? '#24d67d' : '#ff3b3b';
    const label = `Persona ${Math.round(p.conf * 100)}%`;
    const w = ctx.measureText(label).width + 8;
    ctx.fillRect(p.x1, p.y1 - 18, w, 18);
    ctx.fillStyle = '#000';
    ctx.fillText(label, p.x1 + 4, p.y1 - 4);
  });
}

function actualizarPanel(data) {
  pPersonas.textContent = `Personas: ${data.n_personas}`;

  pCasco.textContent = `${data.tiene_casco ? '[OK]' : '[NO]'} Casco blanco`;
  pCasco.className = data.tiene_casco ? 'ok' : 'no';

  pChaleco.textContent = `${data.tiene_chaleco ? '[OK]' : '[NO]'} Chaleco naranja`;
  pChaleco.className = data.tiene_chaleco ? 'ok' : 'no';

  estadoGral.classList.remove('cumple', 'incumple', 'sin-persona');
  if (data.n_personas === 0) {
    estadoGral.textContent = 'Sin persona';
    estadoGral.classList.add('sin-persona');
  } else if (data.tiene_casco && data.tiene_chaleco) {
    estadoGral.textContent = 'CUMPLE EPP';
    estadoGral.classList.add('cumple');
  } else {
    estadoGral.textContent = 'INCUMPLIMIENTO';
    estadoGral.classList.add('incumple');
  }

  if (data.faltantes && data.faltantes.length > 0) {
    alertaBox.textContent = '! ALERTA: Falta ' +
      data.faltantes.map(f => f.toUpperCase()).join(' + ');
    alertaBox.classList.remove('oculto');
    stage.classList.toggle('parpadeo', parpadeo);
  } else {
    alertaBox.classList.add('oculto');
    stage.classList.remove('parpadeo');
  }
}

btnStart.addEventListener('click', iniciarCamara);
