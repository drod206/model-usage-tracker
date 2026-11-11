'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/dashboard.js','utf8');
function run(groups,column,direction){const ctx=vm.createContext({groups,column,direction,console});vm.runInContext(source.split("$('refresh').addEventListener")[0],ctx);return Array.from(vm.runInContext('sortGroups(groups,column,direction)',ctx),g=>g.id);}
function row(id,extra={}){return {id,machine:id,model:'gpt-6.1-sol',role:'coordinator',scope:'cloud',input_tokens:0,output_tokens:0,cache_read_tokens:0,cache_write_tokens:0,records:1,unknown_records:0,calls:0,...extra};}
test('every displayed column sorts using its underlying value',()=>{
 const cases=[['machine','b','a'],['model','z-model','a-model'],['role','vision','code'],['scope','local','cloud'],['input_tokens',10,2],['output_tokens',10,2],['cache_read_tokens',10,2],['reasoning_tokens',10,2],['calls',10,2],['unknown_records',10,2],['gpu_name','V100','RTX 2080 Ti'],['gpu_temp_min',70,40],['gpu_temp_max',80,50],['gpu_temp_avg',75,45],['avg_tokens_per_second',100,9],['backend','z-backend','a-backend'],['input_tokens',1000000,1],['last_used',1794300000,1794200000]];
 for(const [index,[key,high,low]]of cases.entries()){
  const more=index===10?{scope:'local'}:{};
  const rows=[row('high',{...more,[key]:high}),row('low',{...more,[key]:low})];
  assert.deepEqual(run(rows,index,'asc'),['low','high'],'ascending column '+index);
  assert.deepEqual(run(rows,index,'desc'),['high','low'],'descending column '+index);
 }
});
test('UTC timestamps sort chronologically with unknown dates last in both directions',()=>{const rows=[row('unknown',{last_used:null}),row('new',{last_used:1794300000}),row('old',{last_used:1794200000})];assert.deepEqual(run(rows,17,'asc'),['old','new','unknown']);assert.deepEqual(run(rows,17,'desc'),['new','old','unknown']);});
test('unknown costs and GPU metrics remain last regardless of direction',()=>{for(const index of [11,12,13,14,16]){const key={11:'gpu_temp_min',12:'gpu_temp_max',13:'gpu_temp_avg',14:'avg_tokens_per_second'}[index];const rows=[row('unknown',{model:'no-price'}),row('known',{[key||'input_tokens']:25})];assert.deepEqual(run(rows,index,'asc'),['known','unknown']);assert.deepEqual(run(rows,index,'desc'),['known','unknown']);}});
test('numeric sorting is not lexicographic and does not mutate source data',()=>{const rows=[row('ten',{calls:10}),row('two',{calls:2}),row('hundred',{calls:100})];assert.deepEqual(run(rows,8,'asc'),['two','ten','hundred']);assert.deepEqual(rows.map(r=>r.id),['ten','two','hundred']);});
test('equal values keep stable order and no selection preserves API order',()=>{const rows=[row('z'),row('a')];assert.deepEqual(run(rows,8,'desc'),['z','a']);assert.deepEqual(run(rows,null,'asc'),['z','a']);});
test('refresh applies selected sort and header controls are accessible',()=>{assert.match(source,/for\(const g of sortGroups\(groups,sortState\.column,sortState\.direction\)\)/);assert.match(source,/aria-sort/);assert.match(source,/addEventListener\('click'/);assert.match(source,/createElement\('button'\)/);});

test('all public dashboard headers have a corresponding sort descriptor',()=>{const html=fs.readFileSync(__dirname+'/dashboard.html','utf8'),ctx=vm.createContext({});vm.runInContext(source.split("$('refresh').addEventListener")[0],ctx);assert.equal((html.match(/<th(?=[\s>])/g)||[]).length,18);assert.equal(vm.runInContext('SORT_COLUMNS.length',ctx),18);assert.match(source,/cell\.colSpan=18/);assert.match(html,/Real backend/);});
test('currency sorting uses unrounded estimates instead of identical displayed amounts',()=>{const rows=[row('two',{input_tokens:2}),row('one',{input_tokens:1})];assert.deepEqual(run(rows,16,'asc'),['one','two']);assert.deepEqual(run(rows,16,'desc'),['two','one']);});
test('missing real backend sorts last without treating its display placeholder as a value',()=>{const rows=[row('unknown',{model:null,backend:null,backend_model:null}),row('z',{backend:'z-backend'}),row('a',{backend_model:'a-backend'})];assert.deepEqual(run(rows,15,'asc'),['a','z','unknown']);assert.deepEqual(run(rows,15,'desc'),['z','a','unknown']);});
