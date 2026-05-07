let _devs=[],_sid=null,_routes=[];
document.addEventListener('DOMContentLoaded',async()=>{
    _devs=await API.get('/api/devices')||[];
    const s=document.getElementById('devSel');
    _devs.forEach(d=>s.innerHTML+=`<option value="${d.id}">${Util.escapeHtml(d.device_name||d.hostname||d.ip)}</option>`);
});
async function loadRoutes(){
    _sid=parseInt(document.getElementById('devSel').value);
    document.getElementById('btnAdd').disabled=!_sid;
    document.getElementById('card').style.display=_sid?'':'none';
    if(!_sid)return;
    _routes=await API.get(`/api/routes/${_sid}`)||[];
    const t=document.getElementById('routeTable');
    if(!_routes.length){t.innerHTML='<tr class="table-empty"><td colspan="5">暂无静态路由</td></tr>';return}
    t.innerHTML=_routes.map(r=>`<tr><td>${r.destination}/${r.mask}</td><td>${r.mask}</td><td>${r.next_hop}</td><td>${r.preference}</td><td><button class="btn btn-sm btn-outline" style="color:var(--danger)" onclick="delRoute('${r.destination}','${r.mask}','${r.next_hop}')"><i class="bi bi-trash"></i></button></td></tr>`).join('');
}
function showForm(){document.getElementById('formModal').classList.add('open')}
function closeForm(){document.getElementById('formModal').classList.remove('open')}
document.getElementById('routeForm').addEventListener('submit',async e=>{
    e.preventDefault();
    const b={destination:document.getElementById('dest').value,mask:document.getElementById('mask').value,next_hop:document.getElementById('nexthop').value,preference:parseInt(document.getElementById('pref').value)};
    try{await API.post(`/api/routes/${_sid}`,b);closeForm();loadRoutes()}catch(err){alert('添加失败: '+err.message)}
});
async function delRoute(d,m,n){if(!confirm('删除路由?'))return;try{await fetch(`/api/routes/${_sid}`,{method:'DELETE',headers:{'Content-Type':'application/json'},body:JSON.stringify({destination:d,mask:m,next_hop:n})});loadRoutes()}catch(e){alert('删除失败')}}
