'use strict';
// El token se conserva mientras la página está abierta.
const $ = id => document.getElementById(id);
let token = null;
let usuario = null;
let modoAccesoDoctor = false;
let seleccionado = null;
let pacienteDemoId = null;
let editingAppointment = null;
let listaPacientes = [];
let listaDoctores = [];
let especialidadesHospital = [];
let citasCalendario = [];
let mesCalendario = new Date().getMonth();
let anioCalendario = new Date().getFullYear();
let fechaCalendario = fechaLocal(new Date());
function fechaLocal(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
const rolNombre = {
  administrador: 'Administrador', doctor: 'Doctor', paciente: 'Paciente',
  recepcion: 'Recepción'
};
const rolInfo = {
  administrador: ['Administración', 'Consulta las citas y administra el catálogo de médicos.'],
  doctor: ['Mi agenda', 'Consulta las citas asignadas a tu consultorio.'],
  paciente: ['Mis citas', 'Fechas, horarios y médicos de tus consultas.'],
  recepcion: ['Recepción', 'Busca horarios, registra citas y administra las reservas.']
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
function mostrarAccesoDoctor(activo) {
  modoAccesoDoctor=activo;
  $('doctor-login').hidden=!activo;
  $('user-login').hidden=activo;
  $('username').required=!activo;
  $('doctor-id-login').required=activo;
  $('password').value='';
  $('login-error').hidden=true;
  if(activo) $('doctor-id-login').focus();
  else $('username').focus();
}
function cerrarSesion(mostrarMensaje=true) {
  const viejo = token;
  token = null; usuario = null; seleccionado = null; pacienteDemoId = null;
  $('dashboard').hidden = true;
  $('login-screen').hidden = false;
  $('user-pill').hidden = true;
  $('logout').hidden = true;
  $('password').value = '';
  $('login-error').hidden = true;
  mostrarAccesoDoctor(false);
  ['patients-area','patient-calendar-area','notifications-area','users-editor','reprogram-area','directory-area'].forEach(id=>$(id).hidden=true);
  if (mostrarMensaje && viejo) fetch('/api/mvp/auth/logout',{method:'POST', headers:{Authorization:`Bearer ${viejo}`,'Content-Type':'application/json'},body:'{}'}).catch(()=>{});
}
async function iniciarSesion(event) {
  event.preventDefault();
  $('login-error').hidden = true;
  $('login-button').disabled = true;
  try {
    const credenciales=modoAccesoDoctor?{doctor_id:$('doctor-id-login').value.trim().toUpperCase(), password:$('password').value}:
      {usuario:$('username').value,password:$('password').value};
    const data = await post('/api/mvp/auth/login',credenciales);
    token = data.token; usuario = data.usuario;
    $('password').value = '';
    $('login-screen').hidden = true;
    $('dashboard').hidden = false;
    $('logout').hidden = false;
    $('user-pill').hidden = false;
    $('user-pill').textContent = `${usuario.nombre} · ${rolNombre[usuario.rol]}`;
    $('dashboard-heading').textContent = usuario.rol==='doctor'?`${usuario.nombre} · ${usuario.doctor_id}`:rolInfo[usuario.rol][0];
    $('patient-key').textContent=usuario.clave_paciente?`Clave de paciente: ${usuario.clave_paciente}`:'';
    $('patient-key').hidden=usuario.rol!=='paciente';
    $('dashboard-description').textContent = rolInfo[usuario.rol][1];
    const puedeGestionar = ['administrador','recepcion'].includes(usuario.rol);
    const soloDoctor = usuario.rol === 'doctor';
    const soloPaciente = usuario.rol === 'paciente';
    const puedeConsultar = !soloDoctor && !soloPaciente;
    $('availability-area').hidden = !puedeConsultar;
    $('booking-form').hidden = !puedeGestionar;
    $('agenda-area').hidden = soloPaciente;
    $('patient-calendar-area').hidden = !soloPaciente;
    $('directory-area').hidden = !['administrador','recepcion'].includes(usuario.rol);
    $('admin-area').hidden = usuario.rol !== 'administrador';
    $('doctors-admin-area').hidden = usuario.rol !== 'administrador';
    $('users-editor').hidden = usuario.rol !== 'administrador';
    $('patients-area').hidden = !puedeGestionar;
    $('notifications-area').hidden = true;
    $('reprogram-area').hidden = true;
    $('agenda-heading').textContent = soloDoctor ? 'Mis consultas' : 'Citas registradas';
    $('action-head').hidden = !puedeGestionar;
    $('doctor').disabled = soloDoctor;
    resetSeleccion();
    estado('Sesión iniciada.');
    if (puedeConsultar) await cargarDoctores();
    if (soloPaciente) await cargarCalendarioPaciente();
    else await cargarAgenda();
    if (puedeGestionar) { await cargarPacientes(); await cargarPacienteDemo(); }
    if (usuario.rol === 'administrador') {await cargarEspecialidades();await cargarAdministrador();}
    if (['administrador','recepcion'].includes(usuario.rol)) await cargarDirectorio();
  } catch (e) {
    if (token) estado(e.message, true);
    else { $('login-error').textContent = e.message; $('login-error').hidden = false; }
  } finally { $('login-button').disabled = false; }
}
async function cargarDoctores() {
  const data = await api('/api/mvp/doctores');
  const prev = $('doctor').value;
  listaDoctores = data.doctores;
  actualizarEspecialidadesCita();
  $('doctor').replaceChildren(...data.doctores.map(d=>{
    const opt=document.createElement('option'); opt.value=d.id;
    opt.textContent=`${d.nombre} — ${d.especialidad}`;return opt;
  }));
  if (usuario.rol === 'doctor') $('doctor').value = usuario.doctor_id;
  else if (data.doctores.some(d=>d.id===prev)) $('doctor').value = prev;
  for(const id of ['reschedule-doctor','account-doctor']){
    const sel=$(id);const current=sel.value;
    sel.replaceChildren(...(id==='account-doctor'?[new Option('Seleccionar','')]:[]),
       ...data.doctores.map(d=>new Option(`${d.nombre} — ${d.especialidad}`,d.id)));
    if(data.doctores.some(d=>d.id===current))sel.value=current;
  }
  actualizarEspecialidadesCita();
  resetSeleccion();
}
function actualizarEspecialidadesCita(){
  const d=listaDoctores.find(d=>d.id===$('doctor').value)||listaDoctores[0];
  const previa=$('appointment-specialty').value;
  const valores=d?.especialidades||[d?.especialidad].filter(Boolean);
  $('appointment-specialty').replaceChildren(...valores.map(e=>new Option(e,e)));
  if(valores.includes(previa))$('appointment-specialty').value=previa;
}
async function cargarEspecialidades(){
  const data=await api('/api/mvp/especialidades');
  especialidadesHospital=data.especialidades;
  $('new-specialty').replaceChildren(...especialidadesHospital.map(e=>new Option(e,e)));
  $('extra-specialties').replaceChildren();
}
function agregarEspecialidad(){
  const line=document.createElement('div');line.className='specialty-line';
  const selector=document.createElement('select');
  selector.required=true;
  selector.replaceChildren(new Option('Seleccionar especialidad',''),...especialidadesHospital.map(e=>new Option(e,e)));
  const quitar=document.createElement('button');quitar.type='button';quitar.className='button ghost';
  quitar.textContent='Quitar';quitar.onclick=()=>line.remove();
  line.append(selector,quitar);$('extra-specialties').append(line);
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
    const data={doctor_id:$('doctor').value,especialidad:$('appointment-specialty').value,fecha:$('date').value,
      inicio:seleccionado,duracion:Number($('duration').value),
      paciente_nombre:$('patient').value,paciente_telefono:$('phone').value,
      paciente_correo:$('email').value};
    if($('demo-patient').checked) data.paciente_id=pacienteDemoId;
    else if($('existing-patient').value) data.paciente_id=Number($('existing-patient').value);
    const respuesta=await post('/api/mvp/citas',data);
    $('demo-patient').checked=false;alternarPacienteDemo();
    await cargarPacientes();await cargarAgenda();await consultar();
    estado(`${respuesta.confirmacion || `Cita #${respuesta.id} registrada.`} Clave: ${respuesta.clave_paciente}`);
    if(usuario.rol==='administrador')await cargarAdministrador();
  } catch(e){estado(e.message,true);await ventana('No se pudo agendar la cita',e.message);await consultar();} finally {$('book').disabled=seleccionado===null;}
}
const mesesCalendario = ['enero','febrero','marzo','abril','mayo','junio',
  'julio','agosto','septiembre','octubre','noviembre','diciembre'];
function fechaDelCalendario(anio,mes,dia) {
  return `${anio}-${String(mes+1).padStart(2,'0')}-${String(dia).padStart(2,'0')}`;
}
async function cargarCalendarioPaciente() {
  if(!usuario || usuario.rol!=='paciente') return;
  try {
    // El servidor devuelve exclusivamente las citas vinculadas a esta cuenta.
    const r=await api('/api/mvp/citas');
    citasCalendario=r.citas.filter(c=>['programada','pendiente_reagendar'].includes(c.estado));
    pintarCalendarioPaciente();
  }catch(e){estado(e.message,true)}
}
function pintarCalendarioPaciente() {
  const titulo=`${mesesCalendario[mesCalendario]} ${anioCalendario}`;
  $('calendar-title').textContent=titulo.charAt(0).toUpperCase()+titulo.slice(1);
  const dias=$('calendar-days');dias.replaceChildren();
  const comienzo=(new Date(anioCalendario,mesCalendario,1).getDay()+6)%7;
  const cuantos=new Date(anioCalendario,mesCalendario+1,0).getDate();
  for(let i=0;i<comienzo;i++){
    const vacio=document.createElement('div');vacio.className='calendar-blank';
    vacio.setAttribute('aria-hidden','true');dias.append(vacio);
  }
  for(let dia=1;dia<=cuantos;dia++){
    const fecha=fechaDelCalendario(anioCalendario,mesCalendario,dia);
    const citas=citasCalendario.filter(c=>c.fecha===fecha);
    const boton=document.createElement('button');boton.type='button';
    boton.className='calendar-day';
    if(fecha===fechaLocal(new Date()))boton.classList.add('is-today');
    if(fecha===fechaCalendario)boton.classList.add('is-selected');
    boton.setAttribute('aria-pressed',String(fecha===fechaCalendario));
    const diaNum=document.createElement('strong');diaNum.textContent=String(dia);
    boton.append(diaNum);
    for(const cita of citas.slice(0,2)){
      const nota=document.createElement('span');nota.className='calendar-appointment';
      nota.textContent=cita.estado==='pendiente_reagendar'?'Pendiente de reagendar':`${hora(cita.inicio)} · ${cita.doctor_nombre}`;
      nota.title=`${hora(cita.inicio)} - ${hora(cita.inicio+cita.duracion)} | ${cita.doctor_nombre}`;
      boton.append(nota);
    }
    if(citas.length>2){const resto=document.createElement('small');resto.textContent=`+${citas.length-2} más`;boton.append(resto)}
    boton.setAttribute('aria-label',`${dia} de ${mesesCalendario[mesCalendario]}: ${citas.length} cita(s)`);
    boton.onclick=()=>{fechaCalendario=fecha;pintarCalendarioPaciente()};
    dias.append(boton);
  }
  const citasDia=citasCalendario.filter(c=>c.fecha===fechaCalendario);
  const partes=fechaCalendario.split('-');
  $('calendar-selected-title').textContent=`Citas del ${Number(partes[2])} de ${mesesCalendario[Number(partes[1])-1]}`;
  const caja=$('calendar-selected-citas');caja.replaceChildren();
  if(!citasDia.length){const nota=document.createElement('p');nota.className='muted';nota.textContent='No tienes citas para esta fecha.';caja.append(nota);return;}
  for(const cita of citasDia.sort((a,b)=>a.inicio-b.inicio)){
    const evento=document.createElement('div');evento.className='calendar-event';
    const horario=document.createElement('strong');horario.textContent=cita.estado==='pendiente_reagendar'?'Por asignar nuevo horario':`${hora(cita.inicio)} – ${hora(cita.inicio+cita.duracion)}`;
    const medico=document.createElement('span');medico.textContent=cita.estado==='pendiente_reagendar'?`Médico anterior: ${cita.doctor_nombre}`:cita.doctor_nombre;
    const estadoCita=document.createElement('small');estadoCita.textContent=cita.estado==='pendiente_reagendar'?'Pendiente de reagendar':cita.estado==='cancelada'?'Cancelada':'Programada';
    evento.append(horario,medico,estadoCita);caja.append(evento);
  }
}
function cambiarMesCalendario(diferencia) {
  const nuevo=new Date(anioCalendario,mesCalendario+diferencia,1);
  anioCalendario=nuevo.getFullYear();mesCalendario=nuevo.getMonth();
  fechaCalendario=fechaDelCalendario(anioCalendario,mesCalendario,1);
  pintarCalendarioPaciente();
}
async function cargarAgenda() {
  if(!usuario)return;
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
  if(!usuario || !['administrador','recepcion'].includes(usuario.rol))return;
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
    const extras=[...$('extra-specialties').querySelectorAll('select')].map(s=>s.value);
    const especialidades=[$('new-specialty').value,...extras];
    if(especialidades.some(e=>!e) || new Set(especialidades).size!==especialidades.length){
      throw new Error('Selecciona especialidades distintas, sin repetir.');
    }
    const r=await post('/api/mvp/doctores',{id:$('new-id').value,nombre:$('new-name').value,
      especialidad:especialidades[0],especialidades});
    $('new-doctor-form').reset();$('extra-specialties').replaceChildren();await cargarDoctores();await cargarAdministrador();
    estado(`Se agregó ${r.doctor.nombre} (${r.doctor.id}) al catálogo.`);
  } catch(e) {estado(e.message,true);}
}

async function cargarPacientes(){
  if(!['administrador','recepcion'].includes(usuario.rol))return;
  const data=await api('/api/mvp/pacientes');listaPacientes=data.pacientes;
  $('patients').replaceChildren(...listaPacientes.map(p=>{
    const tr=document.createElement('tr');
    [p.clave,p.nombre,p.telefono,p.correo].forEach(value=>{const td=document.createElement('td');td.textContent=value;tr.append(td)});
    return tr;
  }));
  const selected=$('existing-patient').value;
  $('existing-patient').replaceChildren(new Option('Nuevo paciente',''),...listaPacientes.map(p=>new Option(`${p.clave} · ${p.nombre}`,p.id)));
  if(listaPacientes.some(p=>String(p.id)===selected))$('existing-patient').value=selected;
  $('account-patient').replaceChildren(new Option('Seleccionar',''),...listaPacientes.map(p=>new Option(`${p.clave} · ${p.nombre}`,p.id)));
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
    estado(`Paciente ${r.paciente.clave} registrado.`);
  }catch(e){estado(e.message,true)}
}
async function abrirReprogramacion(c){
  editingAppointment=c.id;$('reschedule-id').textContent=`#${c.id}`;
  try{
    const response=await api(`/api/mvp/citas/${c.id}/medicos-compatibles`);
    const medicos=response.doctores;
    $('reschedule-doctor').replaceChildren(...medicos.map(d=>new Option(`${d.nombre} — ${d.especialidades.join(', ')}`,d.id)));
    $('reschedule-doctor').value=medicos.some(d=>d.id===c.doctor_id)?c.doctor_id:(medicos[0]?.id||'');
    if(!medicos.length){await ventana('Sin médicos compatibles',`No hay médicos activos con la especialidad ${response.especialidad}.`);return;}
  }catch(e){estado(e.message,true);return;}
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
  const aviso=p.rol==='doctor'?' Si es la última cuenta de ese médico, sus citas futuras quedarán pendientes de reagendar.':'';
  if(!confirm(`¿Eliminar la cuenta ${p.usuario}?${aviso}`))return;
  try{await post(`/api/mvp/usuarios/${p.id}/eliminar`,{});await cargarAdministrador();estado('Cuenta eliminada.');}
  catch(e){estado(e.message,true)}
}
$('login-form').addEventListener('submit',iniciarSesion);
$('demo-grid').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{
  if(b.dataset.demo==='doctor'){mostrarAccesoDoctor(true);return;}
  mostrarAccesoDoctor(false);
  $('username').value=b.dataset.demo;
  $('password').value='Demo2026!';
  $('username').focus();
  $('login-error').hidden=true;
}));
$('doctor-login-back').addEventListener('click',()=>mostrarAccesoDoctor(false));
$('logout').addEventListener('click',()=>cerrarSesion());
['date','duration','appointment-specialty'].forEach(id=>$(id).addEventListener('change',resetSeleccion));
$('doctor').addEventListener('change',()=>{actualizarEspecialidadesCita();resetSeleccion();});
$('add-specialty').addEventListener('click',agregarEspecialidad);
$('search').addEventListener('click',consultar);
$('demo-patient').addEventListener('change',alternarPacienteDemo);
$('book').addEventListener('click',reservar);
$('patient-form').addEventListener('submit',registrarPaciente);
$('existing-patient').addEventListener('change',actualizarPacienteSeleccionado);
$('reschedule-form').addEventListener('submit',guardarReprogramacion);
$('reschedule-close').addEventListener('click',()=>{$('reprogram-area').hidden=true;editingAppointment=null});
$('notifications-refresh').addEventListener('click',cargarNotificaciones);
$('user-form').addEventListener('submit',guardarUsuario);
$('user-form-reset').addEventListener('click',limpiarUsuario);
$('refresh').addEventListener('click',cargarAgenda);
$('calendar-prev').addEventListener('click',()=>cambiarMesCalendario(-1));
$('calendar-next').addEventListener('click',()=>cambiarMesCalendario(1));
$('calendar-today').addEventListener('click',()=>{const d=new Date();anioCalendario=d.getFullYear();mesCalendario=d.getMonth();fechaCalendario=fechaLocal(d);pintarCalendarioPaciente()});
$('calendar-refresh').addEventListener('click',cargarCalendarioPaciente);
$('new-doctor-form').addEventListener('submit',registrarDoctor);
$('directory-refresh').addEventListener('click',cargarDirectorio);
const hoy=new Date();hoy.setMinutes(hoy.getMinutes()-hoy.getTimezoneOffset());
$('date').value=hoy.toISOString().slice(0,10);
for(const id of ['date','reschedule-date'])$(id).min=$('date').value;
$('doctor-admin-refresh').addEventListener('click',()=>cargarCatalogoMedicos().catch(e=>estado(e.message,true)));
