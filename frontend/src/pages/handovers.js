import {handovers} from '../api/entities.js';
import {workspace} from '../stores/workspace.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {table} from '../components/common/table.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
import {HandoverStatus,HandoverPhase,JobStatus} from '../constants/enums.js';

const phaseLabel=HandoverPhase;
const writable=()=>session.user.role==='admin'||session.user.role==='analyst';

function progressBar(p){
 const t=p?.totals||{},d=p?.done||{};
 return '<div class="handover-progress"><div class="bar"><i style="width:'+(p?.percent||0)+'%"></i></div><div class="progress-legend">'+[['datasets','数据批次'],['jobs','分析任务'],['deliveries','已投递简报']].map(([k,l])=>'<span>'+l+' <strong>'+(d[k]||0)+' / '+(t[k]||0)+'</strong></span>').join('')+'<b>'+(p?.percent||0)+'%</b></div></div>';
}

function summary(item){
 return '<article class="handover-card"><div><span class="status '+(item.status==='failed'?'failed':'')+'">'+(HandoverStatus[item.status]||item.status)+'</span><h3>'+esc(item.label)+'</h3><p>交班点 '+date(item.cutoff)+' · 编号 '+esc(item.ref)+'</p>'+(item.status==='completed'?'<small>现场指纹 SHA256 '+esc(item.scene_checksum.slice(0,24))+'…</small>':'<small>阶段：'+esc(phaseLabel[item.phase]||item.phase)+(item.error?' · '+esc(item.error):'')+'</small>')+'</div><div class="handover-actions"><a class="text-button" href="#/handovers/'+item.id+'">核对现场 ↗</a>'+(item.status!=='completed'&&writable()?'<button class="button small" data-resume="'+item.id+'">'+(item.status==='failed'?'从原交班点恢复':'重新排队')+'</button>':'')+'</div></article>';
}

export async function handoverPage(id){
 const list=await handovers.list();workspace.handovers=list;
 if(id){
  const h=await handovers.get(id);
  if(h.status!=='completed'){
   return heading('06 / HANDOVER','待封存现场',h.label,'<a class="button" href="#/handovers">返回交班清单 ↗</a>')+
    '<section class="panel"><div class="section-title"><h2>'+esc(h.ref)+'</h2><span>交班点固定于 '+date(h.cutoff)+'，不会随后续写入改变</span></div><div id="pending-progress" data-id="'+h.id+'">'+progressBar(h.progress)+'</div>'+'<p class="hint">封存只收录交班点之前已生效的数据批次、分析任务状态、业务批准和已投递简报。中断后从原交班点继续，重试不会重复生成现场行。</p><p class="hint">当前阶段：'+esc(phaseLabel[h.phase]||h.phase)+'。'+(session.user.role!=='viewer'?'由后台 worker 分批推进。':'')+'</p>'+(h.status==='failed'?'<p class="warning">封存中断：'+esc(h.error)+'</p>':'')+((session.user.role==='admin'||session.user.role==='analyst')?'<button class="primary" id="resume-handover" data-id="'+h.id+'">'+(h.status==='failed'?'从原交班点恢复封存':'重新排队封存')+'</button>':'')+'</section>';
  }
  return heading('06 / HANDOVER','交班现场','交班点已固定。这里只呈现封存时已生效的状态与简报出处，之后的补算和分发不会回写本现场。','<a class="button" href="#/handovers">返回交班清单 ↗</a>')+
   '<section class="panel"><div class="section-title"><h2>'+esc(h.label)+'</h2><span class="status completed">已封存</span></div><div class="handover-meta"><div><span>交班点</span><strong>'+date(h.cutoff)+'</strong></div><div><span>完成时间</span><strong>'+date(h.completed_at)+'</strong></div><div><span>现场编号</span><strong>'+esc(h.ref)+'</strong></div><div><span>现场指纹核对</span><strong id="verify-state">'+(h.verified?'一致':'不一致')+'</strong></div></div><p class="hint">SHA256 '+esc(h.scene_checksum)+'</p><button class="button small" id="verify-handover" data-id="'+h.id+'">重新核对现场指纹 ↻</button></section>'+
   '<section class="panel"><div class="section-title"><h2>已入库批次</h2><span>'+h.datasets.length+' 批</span></div>'+table([{key:'dataset_id',label:'批次编号'},{key:'name',label:'批次名称'},{key:'source',label:'来源'},{key:'rows',label:'记录数'},{key:'checksum',label:'内容指纹'}],h.datasets)+'</section>'+
   '<section class="panel"><div class="section-title"><h2>分析状态与批准</h2><span>'+h.jobs.length+' 个任务</span></div>'+table([{key:'job_id',label:'任务编号'},{key:'name',label:'任务名称'},{key:'dataset_name',label:'数据批次'},{key:'status_label',label:'交班时状态'},{key:'approval',label:'交班时批准'},{key:'finished_at',label:'完成时间'}],h.jobs.map(j=>({...j,status_label:JobStatus[j.status]||j.status,approval:j.approved?'已批准 · '+date(j.approved_at):'未批准',finished_at:j.finished_at?date(j.finished_at):'—'})))+'</section>'+
   '<section class="panel"><div class="section-title"><h2>已投递简报与出处</h2><span>'+h.deliveries.length+' 份</span></div>'+table([{key:'filename',label:'投递文件'},{key:'destination',label:'接收组'},{key:'report_name',label:'分发计划'},{key:'job_name',label:'分析任务'},{key:'dataset_name',label:'数据批次'},{key:'checksum',label:'SHA256'},{key:'created_at',label:'投递时间'}],h.deliveries.map(d=>({...d,created_at:date(d.created_at)})))+'</section>';
 }
 return heading('06 / HANDOVER','交班现场封存','登记一个交班点，封存当时已入库的批次、分析状态、批准和已投递简报。日常业务照跑，封存与批准、投递并发时也只收交班前已生效的状态。','<a class="button" href="#/workbench">查看待封存进度 ↗</a>')+
  '<div class="handover-grid"><section class="panel"><div class="section-title"><h2>登记交班点</h2></div><form id="handover-form"><label>交班说明<input name="label" maxlength="160" placeholder="例如：早班交夜班 · 2026-11-18"></label><button type="submit" class="primary" '+(writable()?'':'disabled')+'>封存交班现场 ↗</button><p class="hint">负责人和分析员可登记；交班点以提交时刻为准，观察员只读。</p></form><div class="section-title"><h2>待封存进度</h2><span>封存中断可恢复</span></div>'+(list.filter(x=>x.status!=='completed').map(x=>'<div class="pending-item"><div><strong>'+esc(x.label)+'</strong><small>'+esc(HandoverStatus[x.status]||x.status)+' · '+esc(x.ref)+'</small></div>'+progressBar(x.progress)+'<a class="text-button" href="#/handovers/'+x.id+'">查看 ↗</a></div>').join('')||'<p class="empty">暂无待封存现场。</p>')+'</section><section><div class="section-title"><h2>已封存现场</h2><span>'+list.filter(x=>x.status==='completed').length+' 个</span></div><div class="handover-list">'+(list.filter(x=>x.status==='completed').map(summary).join('')||'<p class="empty">交班点封存后，现场会出现在这里。</p>')+'</div></section></div>';
}

export function bindHandovers(refresh){
 const form=document.querySelector('#handover-form');
 if(form)submit(form,async f=>{await handovers.create({label:f.get('label')||''});notify('交班点已登记，封存将由后台分批推进');await refresh();});
 document.querySelectorAll('[data-resume]').forEach(b=>b.onclick=async()=>{try{await handovers.resume(b.dataset.resume);notify('已从原交班点恢复封存');await refresh();}catch(e){notify(e.message,true);}});
 const verify=document.querySelector('#verify-handover');
 if(verify)verify.onclick=async()=>{try{const r=await handovers.verify(verify.dataset.id);document.querySelector('#verify-state').textContent=r.verified?'一致':'不一致';notify(r.verified?'现场指纹一致：后续补算与分发未改写本现场':'现场指纹不一致，请复核归档行');}catch(e){notify(e.message,true);}};
 const resume=document.querySelector('#resume-handover');
 if(resume)resume.onclick=async()=>{try{await handovers.resume(resume.dataset.id);notify('已从原交班点恢复封存');await refresh();}catch(e){notify(e.message,true);}};
 // 待封存现场在后台分批推进；页面停留时轮询进度，完成后自动展示现场。
 if(document.querySelector('#pending-progress')){
  const timer=setInterval(async()=>{
   if(!document.body.contains(document.querySelector('#pending-progress'))){clearInterval(timer);return;}
   try{const node=document.querySelector('#pending-progress');if(!node){clearInterval(timer);return;}const h=await handovers.get(node.dataset.id);if(h.status==='completed'){clearInterval(timer);refresh();}else node.innerHTML=progressBar(h.progress);}catch(e){clearInterval(timer);}
  },3000);
  addEventListener('hashchange',()=>clearInterval(timer),{once:true});
 }
}
