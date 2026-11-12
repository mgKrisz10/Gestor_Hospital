'use strict';
// El token se conserva mientras la página está abierta.
const $ = id => document.getElementById(id);
let token = null;
let usuario = null;
let seleccionado = null;
let pacienteDemoId = null;
let editingAppointment = null;
let listaPacientes = [];
let listaDoctores = [];
const rolNombre = {
  administrador: 'Administrador', doctor: 'Doctor', paciente: 'Paciente',
  recepcion: 'Recepción', personal_autorizado: 'Personal autorizado'
};
const rolInfo = {
  administrador: ['Administración', 'Consulta las citas y administra el catálogo de médicos.'],
  doctor: ['Mi agenda', 'Citas y horarios de tu consultorio.'],
  paciente: ['Mis citas', 'Consulta las citas asociadas a tu cuenta.'],
  recepcion: ['Recepción', 'Busca horarios, registra citas y administra las reservas.'],
  personal_autorizado: ['Coordinación de atención', 'Consulta el directorio médico, sus especialidades y los horarios disponibles, sin acceder a datos personales.']
};
const hora = t => `${String(Math.floor(t / 60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`;
function ventana(titulo, texto, confirmacion=false){
  const d=$('action-dialog');
  if(!d || typeof d.showModal!=='function'){
    return Promise.resolve(confirmacion ? window.confirm(`${titulo}\n${texto}`) : (window.alert(`${titulo}\n${texto}`),true));
  }
  return new Promise(resolve=>{
    $('dialog-title').textContent=titulo;
    $('dialog-text').textContent=texto;
    $('dialog-cancel').hidden=!confirmacion;
    function terminar(valor){
      d.removeEventListener('cancel',cancelar);
      $('dialog-ok').removeEventListener('click',aceptar);
      $('dialog-cancel').removeEventListener('click',rechazar);
      d.close();resolve(valor);
    }
    const aceptar=()=>terminar(true), rechazar=()=>terminar(false);
    function cancelar(e){e.preventDefault();terminar(false)}
    $('dialog-ok').addEventListener('click',aceptar);
    $('dialog-cancel').addEventListener('click',rechazar);
    d.addEventListener('cancel',cancelar);
    d.showModal();
  });
}
function fechaAnterior(fecha){
  const hoy=new Date();hoy.setMinutes(hoy.getMinutes()-hoy.getTimezoneOffset());
  return Boolean(fecha && fecha<hoy.toISOString().slice(0,10));
}

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
  ['patients-area','absences-area','notifications-area','users-editor','reprogram-area','directory-area'].forEach(id=>$(id).hidden=true);
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
    $('directory-area').hidden = !['personal_autorizado','administrador','recepcion'].includes(usuario.rol);
    $('admin-area').hidden = usuario.rol !== 'administrador';
    $('doctors-admin-area').hidden = usuario.rol !== 'administrador';
    $('users-editor').hidden = usuario.rol !== 'administrador';
    $('patients-area').hidden = !puedeGestionar;
    $('absences-area').hidden = !['doctor','administrador'].includes(usuario.rol);
    $('notifications-area').hidden = usuario.rol !== 'paciente';
    $('reprogram-area').hidden = true;
    $('agenda-heading').textContent = usuario.rol === 'doctor' ? 'Mi agenda médica' : usuario.rol === 'paciente' ? 'Mis citas' : 'Citas registradas';
    $('action-head').hidden = !puedeGestionar;
    $('doctor').disabled = usuario.rol === 'doctor';
    resetSeleccion();
    estado('Sesión iniciada.');
    if (puedeConsultar) await cargarDoctores();
    if (!['personal_autorizado'].includes(usuario.rol)) await cargarAgenda();
    if (puedeGestionar) { await cargarPacientes(); await cargarPacienteDemo(); }
    if (usuario.rol === 'administrador') await cargarAdministrador();
    if (['administrador','doctor'].includes(usuario.rol)) await cargarAusencias();
    if (usuario.rol === 'paciente') await cargarNotificaciones();
    if (['personal_autorizado','administrador','recepcion'].includes(usuario.rol)) await cargarDirectorio();
  } catch (e) {
    if (token) estado(e.message, true);
    else { $('login-error').textContent = e.message; $('login-error').hidden = false; }
  } finally { $('login-button').disabled = false; }
}
async function cargarDoctores() {
  const data = await api('/api/mvp/doctores');
  const prev = $('doctor').value;
  listaDoctores = data.doctores;
  $('doctor').replaceChildren(...data.doctores.map(d=>{
    const opt=document.createElement('option'); opt.value=d.id;
    opt.textContent=`${d.nombre} — ${d.especialidad}`;return opt;
  }));
  if (usuario.rol === 'doctor') $('doctor').value = usuario.doctor_id;
  else if (data.doctores.some(d=>d.id===prev)) $('doctor').value = prev;
  for(const id of ['reschedule-doctor','absence-doctor','account-doctor']){
    const sel=$(id);const current=sel.value;
    sel.replaceChildren(...(id==='account-doctor'?[new Option('Seleccionar','')]:[]),
       ...data.doctores.map(d=>new Option(`${d.nombre} — ${d.especialidad}`,d.id)));
    if(data.doctores.some(d=>d.id===current))sel.value=current;
  }
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
  if(fechaAnterior($('date').value)){
    estado('No se pueden agendar citas para fechas anteriores a hoy.',true);
    await ventana('Fecha anterior', 'Para registrar una cita, selecciona el día de hoy o una fecha posterior.');
    return;
  }
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
    if(!botones.length){
      $('slots').textContent=data.ausencia?'El médico está ausente en esta fecha.':'No hay horarios disponibles.';
      await ventana('Médico no disponible',data.ausencia?
        'El médico está ausente en esta fecha. Elige otro día o levanta su ausencia desde la agenda.':
        'Todos los horarios que cumplen con esa duración están ocupados. Cancela una cita para liberar un espacio.');
    }
    const ocupados = data.citas_ocupadas.map(c=>{
      const s=document.createElement('span');s.textContent=`${hora(c.inicio)} — ${hora(c.fin)}`;return s;
    });
    $('occupied').replaceChildren(...ocupados);
    if(!ocupados.length) $('occupied').textContent='No hay citas ocupadas para este médico y fecha.';
    estado(`Horarios del ${$('date').value}.`);
  } catch(e) {estado(e.message,true);}
}
async function cargarPacienteDemo() {
  try { const r=await api('/api/mvp/paciente-demo');pacienteDemoId=r.paciente.id; }
  catch { pacienteDemoId=null;$('demo-patient').disabled=true; }
}
function alternarPacienteDemo() {
  const on=$('demo-patient').checked;
  $('existing-patient').disabled=on;
  if(on){$('existing-patient').value='';$('patient').value='Paciente Demo';}
  else $('patient').value='';
  actualizarPacienteSeleccionado();
}
async function reservar() {
  if(seleccionado===null) return;
  $('book').disabled=true;
  try {
    const data={doctor_id:$('doctor').value,fecha:$('date').value,
      inicio:seleccionado,duracion:Number($('duration').value),
      paciente_nombre:$('patient').value,paciente_telefono:$('phone').value,
      paciente_correo:$('email').value};
    if($('demo-patient').checked) data.paciente_id=pacienteDemoId;
    else if($('existing-patient').value) data.paciente_id=Number($('existing-patient').value);
    const respuesta=await post('/api/mvp/citas',data);
    $('demo-patient').checked=false;alternarPacienteDemo();
    await cargarPacientes();await cargarAgenda();await consultar();
    estado(respuesta.confirmacion || `Cita #${respuesta.id} registrada.`);
    if(usuario.rol==='administrador')await cargarAdministrador();
  } catch(e){estado(e.message,true);await ventana('No se pudo agendar la cita',e.message);await consultar();} finally {$('book').disabled=seleccionado===null;}
}
async function cargarAgenda() {
  if(!usuario || usuario.rol==='personal_autorizado')return;
  try {
    const data=await api(usuario.rol==='paciente'?'/api/mvp/citas-proximas':'/api/mvp/citas');
    const puedeGestionar=['administrador','recepcion'].includes(usuario.rol);
    const rows=data.citas.map(c=>{
      const tr=document.createElement('tr');
      const values=[`#${c.id}`,c.paciente_nombre,c.doctor_nombre,c.fecha,`${hora(c.inicio)} — ${hora(c.inicio+c.duracion)}`];
      for(const val of values){const td=document.createElement('td');td.textContent=String(val);tr.append(td);}
      const td=document.createElement('td');const span=document.createElement('span');span.className=`state ${c.estado}`;span.textContent=c.estado==='pendiente_reagendar'?'Pendiente de reagendar':c.estado;td.append(span);tr.append(td);
      if(puedeGestionar){const act=document.createElement('td');
        if(c.estado==='programada') {const btn=document.createElement('button');btn.type='button';btn.className='small-btn';btn.textContent='Cancelar';
          const edit=document.createElement('button');edit.type='button';edit.className='small-btn';edit.textContent='Reprogramar';
          edit.style.marginLeft='5px';edit.onclick=()=>abrirReprogramacion(c);act.append(edit);
          btn.onclick=async()=>{if(!confirm(`¿Cancelar la cita #${c.id}?`))return;
            try{await post(`/api/mvp/citas/${c.id}/cancelar`,{});await cargarAgenda();
              if(!$('availability-area').hidden && $('date').value===c.fecha)await consultar();
              if(usuario.rol==='administrador')await cargarAdministrador();
              estado(`Cita #${c.id} cancelada.`);
            }catch(e){estado(e.message,true);}};act.append(btn);
        } else if(c.estado==='pendiente_reagendar'){
          const edit=document.createElement('button');edit.type='button';edit.className='small-btn';
          edit.textContent='Reagendar';edit.onclick=()=>abrirReprogramacion(c);act.append(edit);
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
    const labels={doctores:'Médicos',pacientes:'Pacientes',citas_programadas:'Citas programadas',citas_canceladas:'Citas canceladas',citas_pendientes_reagendar:'Por reagendar'};
    $('metrics').replaceChildren(...Object.entries(labels).map(([key,label])=>{
      const div=document.createElement('div'),strong=document.createElement('strong'),small=document.createElement('small');
      strong.textContent=String(r.resumen[key]);small.textContent=label;div.append(strong,small);return div;
    }));
    $('users').replaceChildren(...u.usuarios.map(person=>{
      const tr=document.createElement('tr');
      [person.usuario,person.nombre,rolNombre[person.rol],person.activo?'Activo':'Inactivo'].forEach(t=>{
        const td=document.createElement('td');td.textContent=t;tr.append(td);
      });
      const actions=document.createElement('td');actions.className='actions';
      const edit=document.createElement('button');edit.type='button';edit.textContent='Editar';edit.onclick=()=>editarUsuario(person);
      const del=document.createElement('button');del.type='button';del.textContent='Eliminar';
      del.onclick=()=>eliminarUsuario(person);actions.append(edit,del);tr.append(actions);
      return tr;
    }));
    await cargarCatalogoMedicos();
    await cargarDirectorio();
  } catch(e){estado(e.message,true);}
}
async function cargarDirectorio(){
  if(!usuario || !['personal_autorizado','administrador','recepcion'].includes(usuario.rol))return;
  try{
    const data=await api('/api/mvp/doctores/directorio');
    $('directory-doctors').replaceChildren(...data.doctores.map(d=>{
      const tr=document.createElement('tr');
      for(const value of [d.id,d.nombre,d.especialidad,d.activo?'Activo':'De baja',
        d.citas_programadas,d.citas_por_reagendar]){
        const td=document.createElement('td');td.textContent=String(value);tr.append(td);
      }
      return tr;
    }));
  }catch(e){estado(e.message,true)}
}
async function cargarCatalogoMedicos(){
  if(usuario.rol!=='administrador')return;
  const r=await api('/api/mvp/doctores/admin');
  $('doctor-admin-list').replaceChildren(...r.doctores.map(d=>{
    const tr=document.createElement('tr');
    for(const dato of [d.id,d.nombre,d.especialidad,d.activo?'Activo':'De baja',d.citas_programadas]){
      const td=document.createElement('td');td.textContent=String(dato);tr.append(td);
    }
    const td=document.createElement('td');
    const boton=document.createElement('button');boton.className='small-btn';boton.type='button';
    boton.textContent=d.activo?'Dar de baja':'Reactivar';
    boton.addEventListener('click',()=>cambiarEstadoDoctor(d));td.append(boton);tr.append(td);
    return tr;
  }));
}
async function cambiarEstadoDoctor(doctor){
  try{
    if(doctor.activo){
      const impacto=await api(`/api/mvp/doctores/${encodeURIComponent(doctor.id)}/impacto`);
      const cantidad=impacto.citas_por_reagendar;
      const aprobado=await ventana('Dar de baja al médico',
        `${doctor.nombre} tiene ${cantidad} cita(s) que quedarán pendientes de reagendar.\n`+
        `Su historial de ${impacto.citas_historicas} cita(s) se conservará.\n¿Continuar?`,true);
      if(!aprobado)return;
      const r=await post(`/api/mvp/doctores/${encodeURIComponent(doctor.id)}/baja`,{});
      await ventana('Médico dado de baja',`Citas por reagendar: ${r.pendientes_reagendar.length}. El historial se conserva.`);
    }else{
      if(!await ventana('Reactivar médico',`¿Volver a permitir citas para ${doctor.nombre}?`,true))return;
      await post(`/api/mvp/doctores/${encodeURIComponent(doctor.id)}/reactivar`,{});
      await ventana('Médico reactivado',`${doctor.nombre} vuelve a estar disponible para nuevas citas.`);
    }
    await cargarDoctores();await cargarCatalogoMedicos();await cargarAgenda();await cargarAdministrador();await cargarDirectorio();
  }catch(e){estado(e.message,true);await ventana('No se pudo completar',e.message)}
}
async function registrarDoctor(event) {
  event.preventDefault();
  try {
    const r=await post('/api/mvp/doctores',{id:$('new-id').value,nombre:$('new-name').value,especialidad:$('new-specialty').value});
    $('new-doctor-form').reset();await cargarDoctores();await cargarAdministrador();
    estado(`Se agregó ${r.doctor.nombre} (${r.doctor.id}) al catálogo.`);
  } catch(e) {estado(e.message,true);}
}

async function cargarPacientes(){
  if(!['administrador','recepcion'].includes(usuario.rol))return;
  const data=await api('/api/mvp/pacientes');listaPacientes=data.pacientes;
  $('patients').replaceChildren(...listaPacientes.map(p=>{
    const tr=document.createElement('tr');
    [p.id,p.nombre,p.telefono,p.correo].forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td)});
    return tr;
  }));
  const selected=$('existing-patient').value;
  $('existing-patient').replaceChildren(new Option('Nuevo paciente',''),...listaPacientes.map(p=>new Option(`${p.id} · ${p.nombre}`,p.id)));
  if(listaPacientes.some(p=>String(p.id)===selected))$('existing-patient').value=selected;
  $('account-patient').replaceChildren(new Option('Seleccionar',''),...listaPacientes.map(p=>new Option(`${p.id} · ${p.nombre}`,p.id)));
  actualizarPacienteSeleccionado();
}
function actualizarPacienteSeleccionado(){
  const demo=$('demo-patient').checked;
  const id=demo?pacienteDemoId:Number($('existing-patient').value);
  const patient=listaPacientes.find(p=>p.id===id);
  for(const key of ['patient','phone','email'])$(key).disabled=Boolean(demo||patient);
  if(patient){$('patient').value=patient.nombre;$('phone').value=patient.telefono;$('email').value=patient.correo;}
  else if(!demo){$('patient').value='';$('phone').value='';$('email').value='';}
}
async function registrarPaciente(event){
  event.preventDefault();
  try{
    const r=await post('/api/mvp/pacientes',{
      nombre:$('patient-new-name').value,telefono:$('patient-new-phone').value,correo:$('patient-new-email').value
    });
    $('patient-form').reset();await cargarPacientes();
    $('existing-patient').value=String(r.paciente.id);actualizarPacienteSeleccionado();
    estado(`Paciente #${r.paciente.id} registrado.`);
  }catch(e){estado(e.message,true)}
}
function abrirReprogramacion(c){
  editingAppointment=c.id;$('reschedule-id').textContent=`#${c.id}`;
  const puedeSeleccionar=listaDoctores.some(d=>d.id===c.doctor_id);
  $('reschedule-doctor').value=puedeSeleccionar?c.doctor_id:(listaDoctores[0]?.id||'');
  $('reschedule-date').value=c.fecha;
  $('reschedule-time').value=hora(c.inicio);
  $('reschedule-duration').value=String(c.duracion);
  $('reprogram-area').hidden=false;
  $('reprogram-area').scrollIntoView({behavior:'smooth',block:'start'});
}
async function guardarReprogramacion(event){
  event.preventDefault();
  if(editingAppointment===null)return;
  const [h,m]=$('reschedule-time').value.split(':').map(Number);
  if(fechaAnterior($('reschedule-date').value)){
    await ventana('Fecha anterior','No se pueden reprogramar citas para un día anterior a hoy.');return;
  }
  try{
    const r=await post(`/api/mvp/citas/${editingAppointment}/reprogramar`,{
      doctor_id:$('reschedule-doctor').value,fecha:$('reschedule-date').value,
      inicio:h*60+m,duracion:Number($('reschedule-duration').value)
    });
    $('reprogram-area').hidden=true;editingAppointment=null;
    await cargarAgenda();await consultar();
    if(usuario.rol==='administrador')await cargarAdministrador();
    estado(r.confirmacion||'Cita reprogramada.');
  }catch(e){estado(e.message,true)}
}
async function cargarAusencias(){
  if(!['administrador','doctor'].includes(usuario.rol))return;
  $('absence-doctor-row').hidden=usuario.rol==='doctor';
  const r=await api('/api/mvp/ausencias');
  $('absences').replaceChildren(...r.ausencias.map(a=>{
    const tr=document.createElement('tr');
    [a.doctor_nombre,a.fecha,a.motivo].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.append(td)});
    const td=document.createElement('td');const boton=document.createElement('button');
    boton.type='button';boton.className='small-btn';boton.textContent='Liberar fecha';
    boton.addEventListener('click',async()=>{
      if(!await ventana('Liberar fecha',`¿Quitar la ausencia del ${a.fecha} de ${a.doctor_nombre}? Las citas ya canceladas permanecerán canceladas.`,true))return;
      try{
        const resp=await post(`/api/mvp/ausencias/${a.id}/levantar`,{});
        await cargarAusencias();await consultar();
        estado(resp.mensaje);await ventana('Fecha liberada',resp.mensaje);
      }catch(e){estado(e.message,true);await ventana('No se pudo liberar',e.message)}
    });td.append(boton);tr.append(td);
    return tr;
  }));
}
async function guardarAusencia(event){
  event.preventDefault();
  try{
    const doctor_id=usuario.rol==='doctor'?usuario.doctor_id:$('absence-doctor').value;
    const r=await post('/api/mvp/ausencias',{
      doctor_id,fecha:$('absence-date').value,motivo:$('absence-reason').value
    });
    $('absence-form').reset();await cargarAusencias();await cargarAgenda();
    estado(`Ausencia registrada. Citas canceladas: ${r.canceladas.length}.`);
    if(usuario.rol==='administrador')await cargarAdministrador();
    await consultar();
  }catch(e){estado(e.message,true)}
}
async function cargarNotificaciones(){
  if(usuario.rol!=='paciente')return;
  const r=await api('/api/mvp/notificaciones');
  $('notifications').replaceChildren(...r.notificaciones.map(n=>{
    const div=document.createElement('div');div.className='notice';
    const p=document.createElement('p');p.textContent=n.mensaje;
    const small=document.createElement('small');small.textContent=n.creado_en;
    div.append(p,small);
    if(!n.leida){
      const btn=document.createElement('button');btn.type='button';btn.className='small-btn';btn.textContent='Marcar como leída';
      btn.onclick=async()=>{try{await post(`/api/mvp/notificaciones/${n.id}/leida`,{});await cargarNotificaciones()}catch(e){estado(e.message,true)}};
      div.append(btn);
    }
    return div;
  }));
  if(!r.notificaciones.length)$('notifications').textContent='No hay notificaciones.';
}
function editarUsuario(p){
  $('editing-user').value=String(p.id);$('user-form-title').textContent=`Editar usuario #${p.id}`;
  $('account-login').value=p.usuario;$('account-name').value=p.nombre;
  $('account-role').value=p.rol;$('account-password').value='';
  $('account-doctor').value=p.doctor_id||'';
  $('account-patient').value=p.paciente_id||'';
  $('users-editor').scrollIntoView({behavior:'smooth'});
}
function limpiarUsuario(){
  $('user-form').reset();$('editing-user').value='';$('user-form-title').textContent='Registrar usuario';
}
async function guardarUsuario(event){
  event.preventDefault();
  const id=$('editing-user').value;
  const data={usuario:$('account-login').value,nombre:$('account-name').value,
    rol:$('account-role').value,doctor_id:$('account-doctor').value||null,
    paciente_id:$('account-patient').value?Number($('account-patient').value):null,
    password:$('account-password').value};
  try{
    const r=await post(id?`/api/mvp/usuarios/${id}/editar`:'/api/mvp/usuarios',data);
    limpiarUsuario();await cargarAdministrador();estado(`Usuario #${r.id} guardado.`);
  }catch(e){estado(e.message,true)}
}
async function eliminarUsuario(p){
  if(!confirm(`¿Eliminar la cuenta ${p.usuario}?`))return;
  try{await post(`/api/mvp/usuarios/${p.id}/eliminar`,{});await cargarAdministrador();estado('Cuenta eliminada.');}
  catch(e){estado(e.message,true)}
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
$('patient-form').addEventListener('submit',registrarPaciente);
$('existing-patient').addEventListener('change',actualizarPacienteSeleccionado);
$('reschedule-form').addEventListener('submit',guardarReprogramacion);
$('reschedule-close').addEventListener('click',()=>{$('reprogram-area').hidden=true;editingAppointment=null});
$('absence-form').addEventListener('submit',guardarAusencia);
$('notifications-refresh').addEventListener('click',cargarNotificaciones);
$('user-form').addEventListener('submit',guardarUsuario);
$('user-form-reset').addEventListener('click',limpiarUsuario);
$('refresh').addEventListener('click',cargarAgenda);
$('new-doctor-form').addEventListener('submit',registrarDoctor);
$('directory-refresh').addEventListener('click',cargarDirectorio);
const hoy=new Date();hoy.setMinutes(hoy.getMinutes()-hoy.getTimezoneOffset());
$('date').value=hoy.toISOString().slice(0,10);
$('absence-date').value=$('date').value;
for(const id of ['date','absence-date','reschedule-date'])$(id).min=$('date').value;
$('doctor-admin-refresh').addEventListener('click',()=>cargarCatalogoMedicos().catch(e=>estado(e.message,true)));
