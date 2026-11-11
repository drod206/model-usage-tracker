'use strict';
function realBackend(group){const b=group.backend_model||group.backend||group.model;return b || '—';}
function formatLastUsed(value){if(!Number.isFinite(value))return '—';const d=new Date(value*1000);return Number.isNaN(d.getTime())?'—':d.toISOString().slice(0,19).replace('T',' ')+' UTC';}
function modelLabel(g){return g.backend&&g.backend!==g.model?g.model+' - '+g.backend:g.model;}
const $=id=>document.getElementById(id),fmt=n=>Number(n||0).toLocaleString();
// Verified standard short-context API rates; USD per million tokens, 2026-11-08.
// Cache writes assume the documented 30-minute tier. Long-context premiums are not reconstructed.
const API_RATES=Object.freeze({
  'gpt-6.1-sol':Object.freeze({inputPerMillion:2,cachedInputPerMillion:0.1,cacheWritePerMillion:2.5,outputPerMillion:10}),
  'gpt-6-luna':Object.freeze({inputPerMillion:0.1,cachedInputPerMillion:0.01,cacheWritePerMillion:0.125,outputPerMillion:0.5})
});
const LOCAL_API_BENCHMARK='gpt-6.1-sol';
function estimateApiRetail(group){
  if(!['local','cloud'].includes(group.scope))return null;
  const pricingModel=group.scope==='local'?LOCAL_API_BENCHMARK:group.model;
  const rates=API_RATES[pricingModel];if(!rates)return null;
  const input=group.input_tokens,output=group.output_tokens,read=group.cache_read_tokens??0,write=group.cache_write_tokens??0;
  if([input,output,read,write].some(n=>!Number.isFinite(n)||n<0)||read+write>input)return null;
  if(group.unknown_records>0&&group.unknown_records===group.records)return null;
  const uncached=input-read-write;
  return {usd:(uncached*rates.inputPerMillion+read*rates.cachedInputPerMillion+write*rates.cacheWritePerMillion+output*rates.outputPerMillion)/1000000,partial:group.unknown_records>0,pricingModel,pricingBasis:group.scope==='local'?'benchmark':'model',uncachedInputTokens:uncached,cachedInputTokens:read,cacheWriteTokens:write};
}
function formatApiRetail(group){
  if(!['local','cloud'].includes(group.scope))return '—';
  const estimate=estimateApiRetail(group);
  if(!estimate)return 'Unknown';
  const dollars=estimate.usd>0&&estimate.usd<0.0001?'< $0.0001':estimate.usd.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:4});
  return (estimate.partial?'≥ ':'')+dollars;
}
function retailTotals(groups){
  const retail={usd:0,partial:false,pricedGroups:0,excludedGroups:0},saved={usd:0,partial:false,pricedGroups:0,excludedGroups:0};
  for(const group of groups){
    if(!['cloud','local'].includes(group.scope))continue;
    const estimate=estimateApiRetail(group);
    for(const total of group.scope==='local'?[retail,saved]:[retail]){
      if(!estimate){total.excludedGroups++;total.partial=true;continue;}
      total.usd+=estimate.usd;total.pricedGroups++;total.partial||=estimate.partial;
    }
  }
  for(const total of [retail,saved])if(!total.pricedGroups&&total.excludedGroups)total.usd=null;
  return {retail,saved};
}
function formatRetailTotal(total){
  if(!Number.isFinite(total.usd))return 'Unknown';
  if(total.usd>0&&total.usd<0.01&&!total.partial)return '< $0.01';
  const tiny=total.usd>0&&total.usd<0.01;
  const dollars=total.usd.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:tiny?4:2,maximumFractionDigits:tiny?8:2});
  return (total.partial?'≥ ':'')+dollars;
}
function updateRetailTotals(groups){
  const totals=retailTotals(groups);
  for(const [id,total] of [['total-retail',totals.retail],['total-saved',totals.saved]]){
    $(id).textContent=formatRetailTotal(total);
    $(id).title=total.pricedGroups+' priced language-model groups; '+total.excludedGroups+' groups unpriced/unmeasured'+(total.partial?'; incomplete measured coverage':'');
  }
}
function formatMetric(value){return Number.isFinite(value)?value.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1}):'—';}
const SORT_COLUMNS=[
  {value:g=>g.machine},{value:g=>modelLabel(g)},{value:g=>g.role},{value:g=>g.scope},
  ...['input_tokens','output_tokens','cache_read_tokens','reasoning_tokens'].map(key=>({numeric:true,value:g=>g.scope==='image'?null:g[key]})),
  ...['calls','unknown_records'].map(key=>({numeric:true,value:g=>g[key]})),
  {value:g=>g.scope==='cloud'?null:g.gpu_name},
  ...['gpu_temp_min','gpu_temp_max','gpu_temp_avg','avg_tokens_per_second'].map(key=>({numeric:true,value:g=>g[key]})),
  {value:g=>g.backend_model||g.backend||g.model||null},
  {numeric:true,value:g=>estimateApiRetail(g)?.usd??null},
  {numeric:true,value:g=>g.last_used}
];
let latestGroups=[];
let sortState={column:null,direction:'asc'};
try{const stored=JSON.parse(localStorage.getItem('usage-tracker.table-sort'));if(stored&&Number.isInteger(stored.column)&&stored.column>=0&&stored.column<SORT_COLUMNS.length&&['asc','desc'].includes(stored.direction))sortState=stored;}catch{}
function sortGroups(groups,column,direction){
  const spec=Number.isInteger(column)?SORT_COLUMNS[column]:null;
  if(!spec)return [...groups];
  const value=g=>{const v=spec.value(g);return spec.numeric?(Number.isFinite(v)?v:null):(v==null||v===''?null:String(v));};
  return groups.map((group,index)=>({group,index,value:value(group)})).sort((a,b)=>{
    if(a.value===null)return b.value===null?a.index-b.index:1;
    if(b.value===null)return -1;
    const comparison=spec.numeric?a.value-b.value:a.value.localeCompare(b.value,'en',{numeric:true,sensitivity:'base'});
    return (direction==='desc'?-comparison:comparison)||a.index-b.index;
  }).map(item=>item.group);
}
function updateSortHeaders(){
  document.querySelectorAll('thead th').forEach((header,index)=>{
    const selected=sortState.column===index;
    header.setAttribute('aria-sort',selected?(sortState.direction==='asc'?'ascending':'descending'):'none');
    const button=header.querySelector('button');
    button.textContent=header.dataset.sortLabel+' '+(selected?(sortState.direction==='asc'?'▲':'▼'):'↕');
    const next=selected?(sortState.direction==='asc'?'descending':'ascending'):(SORT_COLUMNS[index].numeric?'descending':'ascending');
    button.setAttribute('aria-label','Sort by '+header.dataset.sortLabel+', '+next);
  });
}
function setupSorting(){
  document.querySelectorAll('thead th').forEach((header,index)=>{
    header.dataset.sortLabel=header.textContent;
    const button=document.createElement('button');button.type='button';button.className='sort-button';
    button.addEventListener('click',()=>{
      sortState={column:index,direction:sortState.column===index?(sortState.direction==='asc'?'desc':'asc'):(SORT_COLUMNS[index].numeric?'desc':'asc')};
      try{localStorage.setItem('usage-tracker.table-sort',JSON.stringify(sortState));}catch{}
      updateSortHeaders();renderGroups(latestGroups);
    });
    header.replaceChildren(button);
  });
  updateSortHeaders();
}
function renderGroups(groups){$('rows').replaceChildren();for(const g of sortGroups(groups,sortState.column,sortState.direction)){const row=document.createElement('tr');for(const [idx,val]of[g.machine,modelLabel(g),g.role,g.scope,g.scope==='image'?'—':fmt(g.input_tokens),g.scope==='image'?'—':fmt(g.output_tokens),g.scope==='image'?'—':fmt(g.cache_read_tokens),g.scope==='image'?'—':fmt(g.reasoning_tokens),fmt(g.calls),fmt(g.unknown_records),g.scope==='cloud'?'—':g.gpu_name||'Not recorded',formatMetric(g.gpu_temp_min),formatMetric(g.gpu_temp_max),formatMetric(g.gpu_temp_avg),formatMetric(g.avg_tokens_per_second),realBackend(g),formatApiRetail(g),formatLastUsed(g.last_used)].entries()){const cell=document.createElement('td');cell.textContent=val;if(idx===16){const e=estimateApiRetail(g);cell.title=e?(e.pricingBasis==='benchmark'?'API comparison: ':'Matched API model: ')+e.pricingModel+'; standard short-context rates; 30-minute cache-write assumption':'No verified model price or complete usage available';}if(idx===10)cell.className='gpu';else if(idx>3)cell.className='num';row.append(cell)}$('rows').append(row)}if(!groups.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=18;cell.className='empty';cell.textContent='No measured records in this window yet. Historical baseline is available under All recorded usage.';row.append(cell);$('rows').append(row)}}
async function refresh(){try{const response=await fetch('/api/summary?days='+$('window').value,{cache:'no-store'});if(!response.ok)throw Error('Collector returned '+response.status);const data=await response.json();$('error').textContent='';$('total').textContent=fmt(data.total_tokens);$('inout').textContent=fmt(data.input_tokens)+' / '+fmt(data.output_tokens);$('calls').textContent=fmt(data.calls);$('unknown').textContent=fmt(data.unknown_records);updateRetailTotals(data.groups);$('status').textContent='Updated '+new Date(data.generated_at*1000).toLocaleString()+' · '+fmt(data.records)+' accounting records';$('coverage').textContent=data.coverage;latestGroups=data.groups;renderGroups(latestGroups);$('sources').replaceChildren();for(const s of data.sources){const e=document.createElement('span'),age=Math.floor(Date.now()/1000-s.last_seen);e.textContent=s.id+' · last seen '+(age<120?'just now':Math.floor(age/60)+' min ago');$('sources').append(e)}}catch(e){$('error').textContent='Could not refresh: '+e.message+' — last successful values remain visible.'}}
$('refresh').addEventListener('click',refresh);$('window').addEventListener('change',refresh);setupSorting();refresh();setInterval(refresh,30000);
