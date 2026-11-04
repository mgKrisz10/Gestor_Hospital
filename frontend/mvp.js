/* Interfaz MVP: todas las operaciones escriben y consultan el servidor Python. */
const $ = id => document.getElementById(id);
let startSelected = null;
const toHHMM = n => `${String(Math.floor(n / 60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

async function request(path, options = {}) {
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error('No hay conexión con el servidor. Ejecuta python app.py.'); }
  let data;
  try { data = await response.json(); } catch { throw new Error('Respuesta inválida del servidor'); }
  if (!response.ok || !data.ok) throw new Error(data.error || 'No se pudo completar la operación');
  return data;
}
function post(path, object) {
  return request(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(object)});
}
function status(msg, kind = '') { $('status').className = `status ${kind}`; $('status').textContent = msg; }
function resetChoice() { startSelected = null; $('chosen').textContent = 'Ninguno'; $('book').disabled = true; }

async function loadDoctors() {
  const data = await request('/api/mvp/doctores');
  $('doctor').replaceChildren(new Option('Selecciona un médico', ''),
    ...data.doctores.map(d => new Option(`${d.nombre} · ${d.especialidad}`, d.id)));
}
async function availability() {
  resetChoice();
  const doctor = $('doctor').value, date = $('date').value, dur = Number($('duration').value);
  if (!doctor || !date) { status('Selecciona un médico y una fecha.', 'bad'); return; }
  try {
    const qs = new URLSearchParams({doctor, fecha:date, duracion:String(dur)});
    const data = await request(`/api/mvp/disponibilidad?${qs}`);
    $('counter').textContent = `${data.intervalos.length} libres`;
    $('slots').replaceChildren(...data.intervalos.map(i => {
      const button = document.createElement('button'); button.className = 'slot';
      button.type = 'button'; button.setAttribute('aria-pressed','false');
      const s = document.createElement('strong'), sub = document.createElement('small');
      s.textContent = toHHMM(i.inicio); sub.textContent = `hasta ${toHHMM(i.fin)}`;
      button.append(s,sub);
      button.addEventListener('click', () => {
        document.querySelectorAll('.slot').forEach(b => b.setAttribute('aria-pressed','false'));
        button.setAttribute('aria-pressed','true'); startSelected = i.inicio;
        $('chosen').textContent = `${toHHMM(i.inicio)} - ${toHHMM(i.fin)}`;
        $('book').disabled = false;
      }); return button;
    }));
    $('occupied').replaceChildren(...data.citas_ocupadas.map(i => {
      const span = document.createElement('span'); span.textContent = `${toHHMM(i.inicio)} - ${toHHMM(i.fin)}`; return span;
    }));
    if (!data.citas_ocupadas.length) $('occupied').textContent = 'Sin citas ocupadas para esta fecha.';
    if (!data.intervalos.length) $('slots').textContent = 'Sin horarios disponibles de esta duración.';
    status(`Disponibilidad actualizada para ${date}.`, 'good');
  } catch (err) { $('slots').textContent=''; $('occupied').textContent=''; status(err.message,'bad'); }
}
async function book() {
  if (startSelected === null) return;
  try {
    const obj = {doctor_id:$('doctor').value, fecha:$('date').value, inicio:startSelected,
      duracion:Number($('duration').value), paciente_nombre:$('patient').value,
      paciente_telefono:$('phone').value};
    const data = await post('/api/mvp/citas',obj);
    status(`Cita #${data.id} registrada correctamente.`, 'good');
    $('patient').value = ''; $('phone').value = '';
    await refreshAgenda(); await availability();
    status(`Cita #${data.id} guardada. El horario ya aparece como ocupado.`, 'good');
  } catch (err) { status(err.message,'bad'); await refreshAgenda(); }
}
async function refreshAgenda() {
  try {
    const data = await request('/api/mvp/citas');
    const rows = data.citas;
    $('appointments').replaceChildren(...rows.map(c => {
      const tr = document.createElement('tr');
      for (const content of [c.id,c.paciente_nombre,c.doctor_nombre,c.fecha,
          `${toHHMM(c.inicio)} - ${toHHMM(c.inicio+c.duracion)}`]) {
        const td = document.createElement('td'); td.textContent = content; tr.append(td);
      }
      const stateTd = document.createElement('td'), span = document.createElement('span');
      span.className = `state ${c.estado}`; span.textContent = c.estado; stateTd.append(span); tr.append(stateTd);
      const actions = document.createElement('td');
      if (c.estado === 'programada') {
        const cancel = document.createElement('button'); cancel.className='small-btn cancel'; cancel.textContent='Cancelar';
        cancel.addEventListener('click', async () => {
          if (!confirm(`¿Cancelar la cita #${c.id}?`)) return;
          try { await post(`/api/mvp/citas/${c.id}/cancelar`,{}); await refreshAgenda(); await availability();
            status(`Cita #${c.id} cancelada. Su horario vuelve a estar disponible.`, 'good'); }
          catch (err) { status(err.message,'bad'); }
        });
        actions.append(cancel);
      } else actions.textContent='—';
      tr.append(actions); return tr;
    }));
    if (!rows.length) $('appointments').innerHTML = '<tr><td colspan="7">No hay citas registradas. Agenda una desde el formulario.</td></tr>';
  } catch (err) { $('appointments').innerHTML='<tr><td colspan="7">Error al cargar la agenda. Inicia Python.</td></tr>'; status(err.message,'bad'); }
}
['doctor','date','duration'].forEach(id => $(id).addEventListener('change',resetChoice));
$('search').addEventListener('click',availability);
$('book').addEventListener('click',book);
$('refresh').addEventListener('click',refreshAgenda);
const today = new Date(); today.setMinutes(today.getMinutes()-today.getTimezoneOffset());
$('date').value = today.toISOString().slice(0,10);
(async () => { try { await loadDoctors(); await refreshAgenda(); } catch (err) { status(err.message,'bad'); } })();
