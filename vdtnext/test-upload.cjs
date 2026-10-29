// Offline check of index.html: validation, ZIP signature, upload + registration order, retry without a second upload.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const html=fs.readFileSync(__dirname+'/index.html','utf8');const script=html.match(/<script>([\s\S]*)<\/script>/)[1];
const els=new Map();function el(id){if(!els.has(id))els.set(id,{id,value:'',hidden:false,textContent:'',innerHTML:'',disabled:false,files:[],addEventListener(t,f){this['on'+t]=f}});return els.get(id)}
const radios={};const doc={getElementById:el,querySelector:q=>{const n=/name="(\w+)"/.exec(q)[1];return radios[n]?{value:radios[n]}:null}};
let uploads=[],registers=[],failRegister=true;
class XHR{constructor(){this.upload={};this.headers={}}open(m,u){this.url=u}setRequestHeader(k,v){this.headers[k]=v}send(b){uploads.push({url:this.url,headers:this.headers,size:b.size});this.status=200;this.responseText='{}';setImmediate(()=>this.onload())}}
const fetch=async(url,o)=>{const body=JSON.parse(o.body);registers.push(body);if(failRegister){failRegister=false;throw Error('offline')}return {ok:true,json:async()=>({upload_id:body.p_id,stored_bytes:10485760,receipt:body.p_id.slice(0,8).toUpperCase()})}};
const ctx={document:doc,XMLHttpRequest:XHR,fetch,crypto:crypto.webcrypto,window:{scrollTo(){}},console,setImmediate,Date};vm.createContext(ctx);vm.runInContext(script,ctx);
const zip=Buffer.concat([Buffer.from([0x50,0x4b,3,4]),crypto.randomBytes(10*1024*1024-4)]);
const file={name:'vdt.zip',size:zip.length,lastModified:1,arrayBuffer:async()=>zip.buffer.slice(zip.byteOffset,zip.byteOffset+zip.length)};
const submit=()=>el('form').onsubmit({preventDefault(){}});
(async()=>{
 el('done').hidden=true;
 assert.equal((el('fontOrder').innerHTML.match(/type="radio"/g)||[]).length,6);
 el('studentNumber').value='a123456';el('researchId').value='A123456';el('age').value='20';el('measuredOn').value='2026-10-29';radios.fontOrder='10.5-9-12';radios.consent='disagree';el('zipFile').files=[file];
 await submit();assert.match(el('err').textContent,/学籍番号は使えません/);assert.equal(uploads.length,0);
 el('researchId').value='V001';el('zipFile').files=[{...file,arrayBuffer:async()=>Buffer.from('not a zip file at all!!').buffer}];
 await submit();assert.match(el('err').textContent,/ZIPファイルとして読み取れません/);assert.equal(uploads.length,0);
 el('zipFile').files=[file];await submit();// registration fails once (offline)
 assert.equal(uploads.length,1);assert.match(el('err').textContent,/二重提出にはなりません/);assert.equal(el('done').hidden,true);
 await submit();assert.equal(uploads.length,1,'retry must not upload again');assert.equal(registers.length,2);
 const u=uploads[0],r=registers[1];assert.equal(u.url,'https://plirzczxdhddfcxldnxj.supabase.co/storage/v1/object/vdtnext-pilot/submissions/'+r.p_id+'.zip');assert.equal(u.headers['x-upsert'],'false');assert.equal(u.size,10*1024*1024);
 assert.deepEqual({...r,p_id:0},{p_id:0,p_research_id:'V001',p_age:20,p_measured_on:'2026-10-29',p_font_order:'10.5-9-12',p_research_consent:'disagree',p_sha256:crypto.createHash('sha256').update(zip).digest('hex'),p_student_number:'A123456'});
 assert.equal(el('done').hidden,false);assert.equal(el('receipt').textContent,r.p_id.slice(0,8).toUpperCase());
 console.log('PASS: validation, ZIP signature, 10MB upload, metadata registration, retry without duplicate upload');
})().catch(e=>{console.error(e);process.exit(1)});
