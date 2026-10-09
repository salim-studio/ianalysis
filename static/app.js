const $ = s => document.querySelector(s);
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  ['image','audio','text'].forEach(k =>
    $('#panel-'+k).style.display = (k === t.dataset.tab ? 'block' : 'none'));
  hide();
});
function hide(){ $('#result').style.display='none'; }
function show(r){
  $('#result').style.display='block';
  const v = r.verdict;
  const map = {watermarked:['🔴 غالبًا مولّد بالذكاء الاصطناعي','#ef4444'],
               uncertain:['🟡 غير مؤكد — أدلة مختلطة','#f59e0b'],
               not_watermarked:['🟢 غالبًا بشري / بدون علامة','#22c55e']};
  const [txt] = map[v] || map.uncertain;
  $('#verdict').textContent = txt;
  $('#bar').style.width = Math.round((r.score||0)*100)+'%';
  $('#score').textContent = 'الاحتمال: ' + Math.round((r.score||0)*100) + '%';
  $('#details').textContent = JSON.stringify(r.details || r.signals || r, null, 2);
  $('#result').scrollIntoView({behavior:'smooth'});
}
async function post(url, body, isForm){
  $('#verdict').textContent='⏳ جارٍ الفحص...'; $('#result').style.display='block';
  const opts = {method:'POST', body};
  if(!isForm) opts.headers = {'Content-Type':'application/json'};
  const res = await fetch(url, opts);
  const j = await res.json();
  if(j.error) alert(j.error); else show(j);
}
$('#imgFile').onchange = e => {
  const f=e.target.files[0]; if(!f) return;
  const img=$('#preview'); img.src=URL.createObjectURL(f); img.style.display='block';
};
$('#audFile').onchange = e => {
  const f=e.target.files[0]; if(f) $('#audName').textContent='📁 '+f.name;
};
$('#btnImg').onclick = () => {
  const f=$('#imgFile').files[0]; if(!f) return alert('اختر صورة أولًا');
  const fd=new FormData(); fd.append('file',f); post('/api/detect-image',fd,true);
};
$('#btnAud').onclick = () => {
  const f=$('#audFile').files[0]; if(!f) return alert('اختر ملفًا أولًا');
  const fd=new FormData(); fd.append('file',f); post('/api/detect-audio',fd,true);
};
$('#btnTxt').onclick = async () => {
  const t=$('#txt').value; if(!t.trim()) return alert('أدخل نصًا أولًا');
  post('/api/detect-text', JSON.stringify({text:t}));
};
$('#btnSample').onclick = () => {
  $('#txt').value='In conclusion, it is important to note that artificial intelligence plays a crucial role in today\'s fast-paced world. Moreover, this technology is truly remarkable and delves into a tapestry of innovation. Furthermore, it is important to note that progress continues rapidly.';
};
// drag & drop
const drop=$('#drop');
drop.ondragover=e=>{e.preventDefault();drop.style.borderColor='#4f7cff'};
drop.ondrop=e=>{e.preventDefault();const f=e.dataTransfer.files[0];
  if(f){const dt=new DataTransfer();dt.items.add(f);$('#imgFile').files=dt.files;
  const img=$('#preview');img.src=URL.createObjectURL(f);img.style.display='block';}};
