
document.addEventListener('DOMContentLoaded',()=>{
 let cal=new FullCalendar.Calendar(document.getElementById('calendar'),{
  initialView:'dayGridMonth',
  editable:true,
  selectable:true
 })
 cal.render()
 window.calendar=cal
})

function saveAll(){
 fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({
  notes:document.getElementById('notesTxt').value,
  events:calendar.getEvents().map(e=>({title:e.title,start:e.start}))
 })})
}

function askAI(){
 fetch('/ai',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({prompt:document.getElementById('prompt').value})
 }).then(r=>r.json()).then(d=>{
  document.getElementById('aiBox').innerText=d
 })
}
