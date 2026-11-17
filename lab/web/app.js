const q=s=>document.querySelector(s);const msg=t=>q("#message").textContent=t;
function download(name,data,type){const a=document.createElement("a");const u=URL.createObjectURL(new Blob([data],{type}));a.href=u;a.download=name;a.click();URL.revokeObjectURL(u)}
q("#save").onclick=()=>download("islam-lab-experiment.cir",q("#netlist").value,"text/plain");
q("#export").onclick=()=>{const project={format:"islamlab",version:1,name:"ISLAM 2 Mono Spiral PI",created:new Date().toISOString(),engine:{name:"ngspice",status:"not-integrated"},netlist:q("#netlist").value};download("islam-lab-project.json",JSON.stringify(project,null,2),"application/json")};
q("#open").onchange=async e=>{const f=e.target.files[0];if(!f)return;const t=await f.text();if(f.name.endsWith(".json")){try{const p=JSON.parse(t);q("#netlist").value=p.netlist||"";msg("تم فتح ملف المشروع")}catch{msg("ملف JSON غير صالح")}}else{q("#netlist").value=t;msg("تم فتح netlist")}};
if("serviceWorker" in navigator)navigator.serviceWorker.register("./sw.js").catch(()=>{});
