'use strict';
// El token se conserva mientras la página está abierta.
const $ = id => document.getElementById(id);
let token = null;
let usuario = null;
let seleccionado = null;
let pacienteDemoId = null;
const rolNombre = {
  administrador: 'Administrador', doctor: 'Doctor', paciente: 'Paciente',
  recepcion: 'Recepción', personal_autorizado: 'Personal autorizado'
};
const rolInfo = {
  administrador: ['Administración', 'Consulta las citas y administra el catálogo de médicos.'],
  doctor: ['Mi agenda', 'Citas y horarios de tu consultorio.'],
  paciente: ['Mis citas', 'Consulta las citas asociadas a tu cuenta.'],
  recepcion: ['Recepción', 'Busca horarios, registra citas y administra las reservas.'],
  personal_autorizado: ['Consulta de horarios', 'Consulta médicos y horarios disponibles.']
};
const hora = t => `${String(Math.floor(t / 60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;
function estado(texto, malo=false) {
  $('status').textContent = texto;
  $('status').classList.toggle('bad', malo);
}
async function api(path, method='GET', body=null) {
  const headers = {'Accept':'application/json'};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== null) headers['Content-Type'] = 'application/json';
  let response;
  try { response = await fetch(path, {method, headers, body:body === null ? undefined : JSON.stringify(body)}); }
  catch { throw new Error('No se pudo conectar con Python. Inicia el servidor mediante python app.py.'); }
  let data;
  try { data = await response.json(); } catch { throw new Error('Respuesta inesperada del servidor'); }
  if (!response.ok || !data.ok) {
    if (response.status === 401 && path !== '/api/mvp/auth/login') cerrarSesion(false);
    throw new Error(data.error || `Error HTTP ${response.status}`);
  }
  return data;
}
const post = (path, body={}) => api(path,'POST',body);
function cerrarSesion(mostrarMensaje=true) {
  const viejo = token;
  token = null; usuario = null; seleccionado = null; pacienteDemoId = null;
  $('dashboard').hidden = true;
  $('login-screen').hidden = false;
  $('user-pill').hidden = true;
  $('logout').hidden = true;
  $('password').value = '';
  $('login-error').hidden = true;
  if (mostrarMensaje && viejo) fetch('/api/mvp/auth/logout',{method:'POST', headers:{Authorization:`Bearer ${viejo}`,'Content-Type':'application/json'},body:'{}'}).catch(()=>{});
}
async function iniciarSesion(event) {
  event.preventDefault();
  $('login-error').hidden = true;
  $('login-button').disabled = true;
  try {
    const data = await post('/api/mvp/auth/login',{usuario:$('username').value,password:$('password').value});
    token = data.token; usuario = data.usuario;
    $('password').value = '';
    $('login-screen').hidden = true;
    $('dashboard').hidden = false;
    $('logout').hidden = false;
    $('user-pill').hidden = false;
    $('user-pill').textContent = `${usuario.nombre} · ${rolNombre[usuario.rol]}`;
    $('dashboard-heading').textContent = rolInfo[usuario.rol][0];
    $('dashboard-description').textContent = rolInfo[usuario.rol][1];
    const puedeGestionar = ['administrador','recepcion'].includes(usuario.rol);
    const puedeConsultar = true;
    $('availability-area').hidden = !puedeConsultar;
    $('booking-form').hidden = !puedeGestionar;
    $('agenda-area').hidden = usuario.rol === 'personal_autorizado';
    $('admin-area').hidden = usuario.rol !== 'administrador';
    $('agenda-heading').textContent = usuario.rol === 'doctor' ? 'Mi agenda médica' : usuario.rol === 'paciente' ? 'Mis citas' : 'Citas registradas';
    $('action-head').hidden = !puedeGestionar;
    $('doctor').disabled = usuario.rol === 'doctor';
    resetSeleccion();
    estado('Sesión iniciada.');
    if (puedeConsultar) await cargarDoctores();
    if (!['personal_autorizado'].includes(usuario.rol)) await cargarAgenda();
    if (usuario.rol === 'administrador') await cargarAdministrador();
    if (puedeGestionar) await cargarPacienteDemo();
  } catch (e) {
    if (token) estado(e.message, true);
    else { $('login-error').textContent = e.message; $('login-error').hidden = false; }
  } finally { $('login-button').disabled = false; }
}
async function cargarDoctores() {
  const data = await api('/api/mvp/doctores');
  const prev = $('doctor').value;
  $('doctor').replaceChildren(...data.doctores.map(d=>{
    const opt=document.createElement('option'); opt.value=d.id;
    opt.textContent=`${d.nombre} — ${d.especialidad}`;return opt;
  }));
  if (usuario.rol === 'doctor') $('doctor').value = usuario.doctor_id;
  else if (data.doctores.some(d=>d.id===prev)) $('doctor').value = prev;
  resetSeleccion();
}
function resetSeleccion() {
  seleccionado = null;
  $('chosen').textContent = 'Ninguna';
  $('book').disabled = true;
  $('slots').replaceChildren();
  const vacio=document.createElement('p'); vacio.className='empty'; vacio.textContent='Busca los horarios de un médico.';
  $('slots').append(vacio);
  $('occupied').textContent = 'Sin consulta todavía';
  $('counter').textContent = '—';
}
async function consultar() {
  resetSeleccion();
  if (!$('date').value || !$('doctor').value) {estado('Selecciona un médico y una fecha.',true);return;}
  const qs=new URLSearchParams({doctor:$('doctor').value,fecha:$('date').value,duracion:$('duration').value});
  try {
    const data = await api(`/api/mvp/disponibilidad?${qs}`);
    $('counter').textContent = `${data.intervalos.length} libres`;
    const puedeGestionar=['recepcion','administrador'].includes(usuario.rol);
    const botones = data.intervalos.map(intervalo => {
      const b=document.createElement('button');b.type='button';b.className='slot';
      if(!puedeGestionar) b.classList.add('readonly');
      b.setAttribute('aria-pressed','false');
      const strong=document.createElement('strong');strong.textContent=hora(intervalo.inicio);
      const small=document.createElement('small');small.textContent=`hasta ${hora(intervalo.fin)}`;
      b.append(strong,small);
      if(puedeGestionar) b.onclick=()=>{
        seleccionado=intervalo.inicio;
        document.querySelectorAll('#slots .slot').forEach(btn=>btn.setAttribute('aria-pressed','false'));
        b.setAttribute('aria-pressed','true');
        $('chosen').textContent = `${hora(intervalo.inicio)} — ${hora(intervalo.fin)}`;
        $('book').disabled = false;
      };
      else b.disabled=true;
      return b;
    });
    $('slots').replaceChildren(...botones);
    if(!botones.length) $('slots').textContent='Sin espacios completos de esta duración.';
    const ocupados = data.citas_ocupadas.map(c=>{
      const s=document.createElement('span');s.textContent=`${hora(c.inicio)} — ${hora(c.fin)}`;return s;
    });
    $('occupied').replaceChildren(...ocupados);
    if(!ocupados.length) $('occupied').textContent='No hay citas ocupadas para este médico y fecha.';
    estado(`Horarios del ${$('date').value}.`);
  } catch(e) {estado(e.message,true);}
}
async function cargarPacienteDemo() {
  const r=await api('/api/mvp/paciente-demo');
  pacienteDemoId=r.paciente.id;
}
function alternarPacienteDemo() {
  const on=$('demo-patient').checked;
  $('patient').disabled=on;
  $('phone').disabled=on;
  if(on) {$('patient').value='Paciente Demo'; $('phone').value='';}
  else {$('patient').value=''; $('phone').value='';}
}
async function reservar() {
  if(seleccionado===null) return;
  $('book').disabled=true;
  try {
    const data={doctor_id:$('doctor').value,fecha:$('date').value,
      inicio:seleccionado,duracion:Number($('duration').value),
      paciente_nombre:$('patient').value,paciente_telefono:$('phone').value};
    if($('demo-patient').checked) data.paciente_id=pacienteDemoId;
    const respuesta=await post('/api/mvp/citas',data);
    $('demo-patient').checked=false;alternarPacienteDemo();
    await cargarAgenda();await consultar();
    estado(`Cita #${respuesta.id} registrada.`);
    if(usuario.rol==='administrador')await cargarAdministrador();
  } catch(e){estado(e.message,true);await consultar();} finally {$('book').disabled=seleccionado===null;}
}
async function cargarAgenda() {
  if(!usuario || usuario.rol==='personal_autorizado')return;
  try {
    const data=await api('/api/mvp/citas');
    const puedeGestionar=['administrador','recepcion'].includes(usuario.rol);
    const rows=data.citas.map(c=>{
      const tr=document.createElement('tr');
      const values=[`#${c.id}`,c.paciente_nombre,c.doctor_nombre,c.fecha,`${hora(c.inicio)} — ${hora(c.inicio+c.duracion)}`];
      for(const val of values){const td=document.createElement('td');td.textContent=String(val);tr.append(td);}
      const td=document.createElement('td');const span=document.createElement('span');span.className=`state ${c.estado}`;span.textContent=c.estado;td.append(span);tr.append(td);
      if(puedeGestionar){const act=document.createElement('td');
        if(c.estado==='programada') {const btn=document.createElement('button');btn.type='button';btn.className='small-btn';btn.textContent='Cancelar';
          btn.onclick=async()=>{if(!confirm(`¿Cancelar la cita #${c.id}?`))return;
            try{await post(`/api/mvp/citas/${c.id}/cancelar`,{});await cargarAgenda();
              if(!$('availability-area').hidden && $('date').value===c.fecha)await consultar();
              if(usuario.rol==='administrador')await cargarAdministrador();
              estado(`Cita #${c.id} cancelada.`);
            }catch(e){estado(e.message,true);}};act.append(btn);
        } else {act.textContent='—';} tr.append(act);}
      return tr;
    });
    $('appointments').replaceChildren(...rows);
    if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=puedeGestionar?7:6;td.textContent='No hay citas registradas.';tr.append(td);$('appointments').append(tr);}
  } catch(e){estado(e.message,true);}
}
async function cargarAdministrador() {
  if(usuario.rol!=='administrador')return;
  try {
    const [r,u]=await Promise.all([api('/api/mvp/resumen'),api('/api/mvp/usuarios')]);
    const labels={doctores:'Médicos',pacientes:'Pacientes',citas_programadas:'Citas programadas',citas_canceladas:'Citas canceladas'};
    $('metrics').replaceChildren(...Object.entries(labels).map(([key,label])=>{
      const div=document.createElement('div'),strong=document.createElement('strong'),small=document.createElement('small');
      strong.textContent=String(r.resumen[key]);small.textContent=label;div.append(strong,small);return div;
    }));
    $('users').replaceChildren(...u.usuarios.map(person=>{
      const tr=document.createElement('tr');
      [person.usuario,person.nombre,rolNombre[person.rol],person.activo?'Activo':'Inactivo'].forEach(t=>{
        const td=document.createElement('td');td.textContent=t;tr.append(td);
      });return tr;
    }));
  } catch(e){estado(e.message,true);}
}
async function registrarDoctor(event) {
  event.preventDefault();
  try {
    const r=await post('/api/mvp/doctores',{id:$('new-id').value,nombre:$('new-name').value,especialidad:$('new-specialty').value});
    $('new-doctor-form').reset();await cargarDoctores();await cargarAdministrador();
    estado(`Se agregó ${r.doctor.nombre} (${r.doctor.id}) al catálogo.`);
  } catch(e) {estado(e.message,true);}
}
$('login-form').addEventListener('submit',iniciarSesion);
$('demo-grid').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  $('username').value=b.dataset.demo;
  $('password').value='Demo2026!';
  $('username').focus();
  $('login-error').hidden=true;
}));
$('logout').addEventListener('click',()=>cerrarSesion());
['date','doctor','duration'].forEach(id=>$(id).addEventListener('change',resetSeleccion));
$('search').addEventListener('click',consultar);
$('demo-patient').addEventListener('change',alternarPacienteDemo);
$('book').addEventListener('click',reservar);
$('refresh').addEventListener('click',cargarAgenda);
$('new-doctor-form').addEventListener('submit',registrarDoctor);
const hoy=new Date();hoy.setMinutes(hoy.getMinutes()-hoy.getTimezoneOffset());
$('date').value=hoy.toISOString().slice(0,10);
