// Real-service check: node e2e-check.mjs dummy.zip
// Uploads the ZIP anonymously, registers it, then confirms anonymous users cannot read it back.
import fs from 'fs'; import crypto from 'crypto';
const API = 'https://plirzczxdhddfcxldnxj.supabase.co', KEY = 'sb_publishable_NCH7QuER6v_83QHr8RvVkA_9U2oprUz', H = { apikey: KEY };
const zip = fs.readFileSync(process.argv[2]), id = crypto.randomUUID(), path = `submissions/${id}.zip`;
const sha = crypto.createHash('sha256').update(zip).digest('hex');
const show = async (label, r) => { const t = await r.text(); console.log(label, r.status, t.slice(0, 200)); return r; };
await show('upload', await fetch(`${API}/storage/v1/object/vdtnext-pilot/${path}`, { method: 'POST', headers: { ...H, 'Content-Type': 'application/zip', 'x-upsert': 'false' }, body: zip }));
await show('overwrite (expect rejection)', await fetch(`${API}/storage/v1/object/vdtnext-pilot/${path}`, { method: 'POST', headers: { ...H, 'Content-Type': 'application/zip', 'x-upsert': 'true' }, body: Buffer.from('PK\x05\x06' + '\0'.repeat(18)) }));
await show('register', await fetch(`${API}/rest/v1/rpc/vdtnext_register_upload`, { method: 'POST', headers: { ...H, 'Content-Type': 'application/json' }, body: JSON.stringify({ p_id: id, p_research_id: 'TEST-E2E', p_age: 20, p_measured_on: new Date().toISOString().slice(0, 10), p_font_order: '12-10.5-9', p_research_consent: 'disagree', p_sha256: sha, p_student_number: 'TEST0000' }) }));
await show('anon download (expect 400/404)', await fetch(`${API}/storage/v1/object/vdtnext-pilot/${path}`, { headers: H }));
await show('anon public URL (expect 400)', await fetch(`${API}/storage/v1/object/public/vdtnext-pilot/${path}`));
await show('anon list (expect [])', await fetch(`${API}/storage/v1/object/list/vdtnext-pilot`, { method: 'POST', headers: { ...H, 'Content-Type': 'application/json' }, body: '{"prefix":"submissions/"}' }));
await show('anon table read (expect denied)', await fetch(`${API}/rest/v1/vdtnext_uploads?select=*`, { headers: H }));
console.log('upload id', id, 'bytes', zip.length, 'sha256', sha);
