
const FALLBACK_DOCTORS = [
  {id:'MED001', nombre:'Dra. Ana Lopez', especialidad:'Medicina general', citas:[{inicio:540,duracion:30},{inicio:600,duracion:60},{inicio:630,duracion:30}]},
  {id:'MED002', nombre:'Dr. Carlos Martinez', especialidad:'Cardiologia', citas:[{inicio:480,duracion:30},{inicio:570,duracion:30},{inicio:720,duracion:60}]},
  {id:'MED003', nombre:'Dra. Sofia Hernandez', especialidad:'Pediatria', citas:[]}
];

const fallbackAvailability = (citas, duracion) => {
  if (duracion <= 0) throw new Error('Duracion invalida');
  if (duracion > 360) throw new Error('La duracion excede el horario laboral');
  const sorted = citas.map(c => ({...c, fin:c.inicio+c.duracion})).sort((a,b)=>a.inicio-b.inicio);
  if (sorted.some(c => c.duracion <= 0 || c.inicio < 480 || c.fin > 840)) throw new Error('Cita fuera del horario laboral');
  const merged = sorted.reduce((acc,c) => {
    const last = acc[acc.length-1];
    if (!last) return [...acc, c];
    return c.inicio <= last.fin ? [...acc.slice(0,-1), {...last, fin:Math.max(last.fin,c.fin)}] : [...acc,c];
  }, []);
  const gaps = merged.reduce((acc,c,i) => {
    const start = i === 0 ? 480 : merged[i-1].fin;
    return c.inicio > start ? [...acc,{inicio:start,fin:c.inicio}] : acc;
  }, []);
  if (!merged.length) gaps.push({inicio:480,fin:840});
  else if (merged[merged.length-1].fin < 840) gaps.push({inicio:merged[merged.length-1].fin,fin:840});
  return gaps.flatMap(g => Array.from({length:Math.floor((g.fin-g.inicio)/duracion)}, (_,k)=>({inicio:g.inicio+k*duracion,fin:g.inicio+(k+1)*duracion})));
};

const doctorSelect = document.querySelector('#doctor');
const dateInput = document.querySelector('#date');
const durationSelect = document.querySelector('#duration');
const searchButton = document.querySelector('#search');
const schedule = document.querySelector('#schedule');
const occupied = document.querySelector('#occupied');
const message = document.querySelector('#message');
const resultTitle = document.querySelector('#result-title');
const count = document.querySelector('#count');
const connection = document.querySelector('#connection');
const doctorInfo = document.querySelector('#doctor-info');

const minutesToTime = minutes => {
  const h = Math.floor(minutes / 60).toString().padStart(2, '0');
  const m = (minutes % 60).toString().padStart(2, '0');
  return `${h}:${m}`;
};

const setToday = () => {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  dateInput.value = local.toISOString().slice(0, 10);
};

function renderDoctors(doctors) {
  doctorSelect.innerHTML = doctors.map(d =>
    `<option value="${d.id}">${d.nombre} - ${d.especialidad}</option>`
  ).join('');
  renderDoctorInfo();
}

function renderDoctorInfo() {
  const option = doctorSelect.options[doctorSelect.selectedIndex];
  if (!option) return;
  doctorInfo.classList.remove('hidden');
  doctorInfo.innerHTML = `<strong>${option.textContent}</strong><br><span>ID del médico: ${option.value}</span>`;
}

function renderOccupied(items) {
  if (!items.length) {
    occupied.innerHTML = '<div class="muted">No hay citas ocupadas. Todo el horario laboral está libre.</div>';
    return;
  }
  occupied.innerHTML = items.map(i =>
    `<div class="occupied-slot">${i.inicio_texto} - ${i.fin_texto}</div>`
  ).join('');
}

function renderSlots(items, duration) {
  schedule.innerHTML = '';
  if (!items.length) {
    schedule.innerHTML = '<div class="empty">No existen bloques completos con esa duración en los espacios libres.</div>';
    return;
  }
  schedule.innerHTML = items.map(i => `
    <button class="slot" type="button" data-time="${i.inicio}">
      <strong>${minutesToTime(i.inicio)}</strong>
      <span>hasta ${minutesToTime(i.fin)} · ${duration} min</span>
    </button>`).join('');
  schedule.querySelectorAll('.slot').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('.slot').forEach(x => x.removeAttribute('aria-pressed'));
    btn.setAttribute('aria-pressed', 'true');
    message.className = 'message';
    message.textContent = `Horario seleccionado: ${minutesToTime(Number(btn.dataset.time))}.`;
  }));
}

async function cargarDoctores() {
  try {
    const response = await fetch('/api/doctores');
    if (!response.ok) throw new Error('No se pudo conectar');
    const doctors = await response.json();
    renderDoctors(doctors);
    connection.textContent = 'Python conectado correctamente.';
  } catch (error) {
    renderDoctors(FALLBACK_DOCTORS);
    connection.textContent = 'Modo demostración: frontend sin servidor.';
  }
}

async function buscar() {
  const doctor = doctorSelect.value;
  const duracion = durationSelect.value;
  if (!doctor) return;
  searchButton.disabled = true;
  searchButton.querySelector('span').textContent = 'Calculando...';
  message.className = 'message';
  message.textContent = 'Procesando la agenda...';
  count.classList.add('hidden');
  try {
    const response = await fetch(`/api/disponibilidad?doctor=${encodeURIComponent(doctor)}&duracion=${encodeURIComponent(duracion)}`);
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || 'No se pudo obtener disponibilidad');
    }
    resultTitle.textContent = `Horarios para ${data.doctor.nombre}`;
    count.classList.remove('hidden');
    count.textContent = `${data.intervalos.length} disponibles`;
    message.textContent = `Fecha: ${dateInput.value || 'sin fecha'} · Duración: ${duracion} minutos`;
    renderSlots(data.intervalos, duracion);
    renderOccupied(data.citas_ocupadas);
  } catch (error) {
    try {
      const selected = FALLBACK_DOCTORS.find(d => d.id === doctor);
      const items = fallbackAvailability(selected.citas, Number(duracion));
      resultTitle.textContent = `Horarios para ${selected.nombre}`;
      count.classList.remove('hidden');
      count.textContent = `${items.length} disponibles`;
      message.className = 'message';
      message.textContent = `Fecha: ${dateInput.value || 'sin fecha'} · Duración: ${duracion} minutos · Modo demostración`;
      renderSlots(items, Number(duracion));
      renderOccupied(selected.citas.map(c => ({inicio:c.inicio,fin:c.inicio+c.duracion,inicio_texto:minutesToTime(c.inicio),fin_texto:minutesToTime(c.inicio+c.duracion)})));
    } catch (fallbackError) {
      message.className = 'message error';
      message.textContent = fallbackError.message;
      schedule.innerHTML = '';
    }
  } finally {
    searchButton.disabled = false;
    searchButton.querySelector('span').textContent = 'Buscar horarios';
  }
}

dateInput.addEventListener('change', () => {});
doctorSelect.addEventListener('change', renderDoctorInfo);
searchButton.addEventListener('click', buscar);
setToday();
cargarDoctores();
