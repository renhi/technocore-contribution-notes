import assert from "node:assert/strict";
import {readFile,writeFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import http from "node:http";

const [root,kit]=process.argv.slice(2);
const p=JSON.parse(await readFile(kit+"/source-provenance.json","utf8"));
const sha=x=>createHash("sha256").update(x).digest("hex");
for(const f of p.files) assert.equal(sha(await readFile(root+"/"+f.label+"/"+f.path)),f.sha256);
const routing={types:{},static_first:[],edge_revalidate:{"/rooms":5},edge_key:{"/rooms":{match:{format:"json"},clamped:{limit:{min:1,max:200}}}}};
// null denotes intentional cache bypass; non-null is the expected effective cache key.
const cases=[
 ["limit=1&limit=2","limit=2"],["limit=2&limit=1","limit=1"],
 ["limit=2&limit=2","limit=2"],["format=json&format=text",""],
 ["format=text&format=json","format=json"],["format=json&format=json","format=json"],
 ["limit=1&format=text&limit=3&format=json","format=json&limit=3"],
 ["limit=3&format=json&limit=1&format=text","limit=1"],
 ["limit=1&limit=2&limit=3","limit=3"],["limit=%2B2&limit=4","limit=4"],
 ["limit=4&limit=%2B2",null],["limit=&limit=3","limit=3"],
 ["limit=3&limit=",null],["limit=201&limit=0","limit=1"],
 ["limit=0&limit=201","limit=200"],["limit=2&%6cimit=3","limit=3"],
 ["format=json&format=",""],["limit=0004","limit=4"],
 ["noise=1&limit=2","limit=2"],["",""],
 ["limit=1000000000",null],["format=json&format=JSON",""],
];
let requests=[];
const origin=http.createServer((req,res)=>{
 requests.push(req.url);
 const q=new URL(req.url,"http://localhost").searchParams;
 const last=k=>q.getAll(k).at(-1);
 const raw=last("limit");
 const n=raw && /^[+]?\d+$/.test(raw)?Math.max(1,Math.min(200,Number(raw))):30;
 const format=last("format")==="json"?"json":"text";
 res.setHeader("Content-Type",format==="json"?"application/json":"text/plain");
 res.end(format==="json"?JSON.stringify({rooms:Array.from({length:n},(_,i)=>"room-"+i)}):"rooms:"+n);
});
await new Promise(resolve=>origin.listen(0,"127.0.0.1",resolve));
const endpoint="http://127.0.0.1:"+origin.address().port+"/rooms";
const report={node:process.version,versions:[]};
try{
 for(const label of ["base","main","candidate"]){
  const original=await readFile(root+"/"+label+"/edge/src/worker.js","utf8");
  const marker='import ROUTING from "./routing.json";';
  assert.equal(original.split(marker).length,2);
  const worker=(await import("data:text/javascript;base64,"+Buffer.from(original.replace(marker,"const ROUTING="+JSON.stringify(routing)+";")).toString("base64")+"#"+label)).default;
  const rows=[];
  for(const [query,key] of cases){
   const path=q=>"/rooms"+(q?"?"+q:"");
   const url=endpoint+(query?"?"+query:"");
   const direct=await fetch(url);
   const expected={body:await direct.text(),type:direct.headers.get("content-type")};
   requests=[];
   const cache=new Map(), puts=[];
   globalThis.caches={default:{match:async r=>cache.get(r.url)?.clone(),put:async(r,s)=>{puts.push(new URL(r.url).pathname+new URL(r.url).search);cache.set(r.url,s.clone());}}};
   const ctx={waitUntil:()=>assert.fail("Unexpected background refresh")};
   const one=async u=>{const r=await worker.fetch(new Request(u),{},ctx);return {body:await r.text(),type:r.headers.get("content-type")};};
   const a=await one(url);
   const b=await one(key===null?url:endpoint+(key?"?"+key:""));
   const wantRequests=key===null?[path(query),path(query)]:[path(key)];
   const wantPuts=key===null?[]:[path(key)];
   const matches=JSON.stringify([a,b,requests,puts])===JSON.stringify([expected,expected,wantRequests,wantPuts]);
   rows.push({query,key,matches,requests:[...requests],puts,bodyAndTypeMatch:JSON.stringify([a,b])===JSON.stringify([expected,expected])});
  }
  report.versions.push({label,cases:rows.length,matches:rows.filter(x=>x.matches).length,rows});
 }
}finally{origin.closeAllConnections();await new Promise(resolve=>origin.close(resolve));}
for(const f of p.files) assert.equal(sha(await readFile(root+"/"+f.label+"/"+f.path)),f.sha256);
await writeFile(kit+"/native-results.json",JSON.stringify(report,null,2)+"\n");
console.log(report.versions.map(({label,cases,matches})=>({label,cases,matches})));
assert.equal(report.versions[2].matches,cases.length);
