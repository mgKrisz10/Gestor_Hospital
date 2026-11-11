/* Consulta de disponibilidad. */
const $ = id => document.getElementById(id);
const FALLBACK_DOCTORS=[
 {id:'MED001',nombre:'Dra. Ana Lopez',especialidad:'Medicina general',citas:[{inicio:540,duracion:30},{inicio:600,duracion:60},{inicio:630,duracion:30}]},
 {id:'MED002',nombre:'Dr. Carlos Martinez',especialidad:'Cardiologia',citas:[{inicio:480,duracion:30},{inicio:570,duracion:30},{inicio:720,duracion:60}]},
 {id:'MED003',nombre:'Dra. Sofia Hernandez',especialidad:'Pediatria',citas:[]}];
const toTime=n=>`${String(Math.floor(n/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`;
function fallbackAvailability(citas,duracion){
 if(duracion<=0)throw Error('Duracion invalida');
 if(duracion>360)throw Error('La duracion excede el horario laboral');
 const intervals=citas.map(c=>({inicio:c.inicio,fin:c.inicio+c.duracion})).sort((a,b)=>a.inicio-b.inicio);
 if(citas.some(c=>c.duracion<=0||c.inicio<480||c.inicio+c.duracion>840))throw Error('Cita fuera del horario laboral');
 const merged=intervals.reduce((out,c)=>{const prev=out.at(-1);if(!prev)return[c];return c.inicio<=prev.fin?[...out.slice(0,-1),{inicio:prev.inicio,fin:Math.max(prev.fin,c.fin)}]:[...out,c]},[]);
 const points=[{inicio:480,fin:480},...merged,{inicio:840,fin:840}];
 return points.slice(0,-1).flatMap((a,i)=>{const b=points[i+1],n=Math.floor((b.inicio-a.fin)/duracion);return Array.from({length:Math.max(n,0)},(_,k)=>({inicio:a.fin+k*duracion,fin:a.fin+(k+1)*duracion}))});
}
async function loadDoctors(){let items=FALLBACK_DOCTORS;try{const response=await fetch('/api/doctores');if(!response.ok)throw Error();items=await response.json();$('connection').textContent='Conectado al servidor.'}catch{$('connection').textContent='Usando los horarios guardados en esta página.'}
$('doctor').innerHTML=items.map(d=>`<option value="${d.id}">${d.nombre} - ${d.especialidad}</option>`).join('');}
async function search(){const id=$('doctor').value,dur=Number($('duration').value);let data;
try{const response=await fetch(`/api/disponibilidad?doctor=${encodeURIComponent(id)}&duracion=${dur}`);data=await response.json();if(!response.ok||!data.ok)throw Error(data.error||'Error de servidor')}catch{
 try{const doc=FALLBACK_DOCTORS.find(x=>x.id===id);if(!doc)throw Error('Doctor no encontrado');
 data={ok:true,doctor:doc,intervalos:fallbackAvailability(doc.citas,dur),citas_ocupadas:doc.citas.map(c=>({inicio:c.inicio,fin:c.inicio+c.duracion}))}}catch(err){$('message').textContent=err.message;return}}
$('result-title').textContent=`Horarios para ${data.doctor.nombre}`;$('count').textContent=`${data.intervalos.length} disponibles`;
$('message').textContent=`Fecha: ${$('date').value||'sin fecha'} · Duración: ${dur} minutos`;
$('schedule').replaceChildren(...data.intervalos.map(i=>{const button=document.createElement('button');button.className='slot';button.innerHTML=`<strong>${toTime(i.inicio)}</strong>hasta ${toTime(i.fin)}`;button.addEventListener('click',()=>{document.querySelectorAll('.slot').forEach(x=>x.setAttribute('aria-pressed','false'));button.setAttribute('aria-pressed','true');$('message').textContent=`Horario seleccionado: ${toTime(i.inicio)}.`});return button}));
$('occupied').replaceChildren(...data.citas_ocupadas.map(i=>{const div=document.createElement('div');div.className='busy';div.textContent=`${toTime(i.inicio)} - ${toTime(i.fin)}`;return div}));
if(!data.citas_ocupadas.length)$('occupied').textContent='No hay citas ocupadas. Todo el horario laboral está libre.'}
const today=new Date();today.setMinutes(today.getMinutes()-today.getTimezoneOffset());$('date').value=today.toISOString().slice(0,10);
$('search').addEventListener('click',search);loadDoctors();
