const q=s=>document.querySelector(s);
const msg=t=>q("#message").textContent=t;
const KEY="islam-lab-draft-v1";
function download(name,data,type){const a=document.createElement("a");const u=URL.createObjectURL(new Blob([data],{type}));a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)}
function validateNetlist(source){
 const lines=source.split(/\r?\n/),errors=[],warnings=[],names=new Set();let endCount=0,active=0;
 lines.forEach((raw,i)=>{const s=raw.trim();if(!s||s.startsWith("*"))return;const n=i+1,parts=s.split(/\s+/),head=parts[0].toLowerCase();
 if(head===".end"){endCount++;if(parts.length>1)warnings.push("السطر "+n+": نص زائد بعد .end");return}
 if(head.startsWith(".")){if(![".tran",".ac",".dc",".op",".end"].includes(head))warnings.push("السطر "+n+": أمر غير مدعوم في الفاحص الأولي: "+parts[0]);return}
 active++;const id=parts[0].toLowerCase();if(names.has(id))errors.push("السطر "+n+": اسم عنصر مكرر "+parts[0]);names.add(id);
 const kind=id[0],minimum={r:4,l:4,c:4,v:4,i:4,d:3,q:4,m:6}[kind];
 if(!minimum){warnings.push("السطر "+n+": نوع عنصر غير معروف للفاحص الأولي: "+parts[0]);return}
 if(parts.length<minimum)errors.push("السطر "+n+": عدد الحقول أقل من المطلوب للعنصر "+parts[0]);
 if(["r","l","c"].includes(kind)&&parts[3]&&!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?[tgkmunpf]?$/i.test(parts[3]))errors.push("السطر "+n+": قيمة غير رقمية أو صيغة قيمة غير مدعومة: "+parts[3]);
 });
 if(endCount===0)errors.push("الأمر .end غير موجود");if(endCount>1)errors.push("يوجد أكثر من أمر .end");if(active===0)errors.push("لا توجد عناصر دائرة");
 return {errors,warnings,lines:lines.length,components:active};
}
function showValidation(){
 const r=validateNetlist(q("#netlist").value),el=q("#validation");
 el.innerHTML="";
 const h=document.createElement("p");h.textContent=r.errors.length?"توجد أخطاء بنيوية":"لم يعثر الفاحص الأولي على أخطاء بنيوية واضحة";h.className=r.errors.length?"error":"status";el.append(h);
 [...r.errors,...r.warnings].forEach(t=>{const p=document.createElement("p");p.textContent=(r.errors.includes(t)?"خطأ: ":"تنبيه: ")+t;p.className=r.errors.includes(t)?"error":"muted";el.append(p)});
 const f=document.createElement("small");f.textContent="العناصر: "+r.components+" • الأسطر: "+r.lines+" • هذا فحص نصي أولي وليس تحليلاً كهربائياً أو تشغيل SPICE.";el.append(f);
}
function saveDraft(){try{localStorage.setItem(KEY,q("#netlist").value);msg("حُفظت مسودة محلية على هذا الجهاز")}catch{msg("تعذر الحفظ المحلي في هذا المتصفح")}}
q("#save").onclick=()=>download("islam-lab-experiment.cir",q("#netlist").value,"text/plain");
q("#export").onclick=()=>{const project={format:"islamlab",version:1,name:"ISLAM 2 Mono Spiral PI",created:new Date().toISOString(),engine:{name:"ngspice",status:"not-integrated"},netlist:q("#netlist").value};download("islam-lab-project.json",JSON.stringify(project,null,2),"application/json")};
q("#validate").onclick=showValidation;
q("#saveDraft").onclick=saveDraft;
q("#netlist").addEventListener("input",()=>{try{localStorage.setItem(KEY,q("#netlist").value)}catch{}});
q("#open").onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const t=await f.text();if(f.name.toLowerCase().endsWith(".json")){const p=JSON.parse(t);if(p.format!=="islamlab"||typeof p.netlist!=="string")throw Error("صيغة المشروع غير معروفة");q("#netlist").value=p.netlist;msg("تم فتح ملف المشروع")}else{q("#netlist").value=t;msg("تم فتح netlist")}showValidation()}catch(err){msg("تعذر فتح الملف: "+err.message)}};
try{const draft=localStorage.getItem(KEY);if(draft)q("#netlist").value=draft}catch{}
showValidation();
if("serviceWorker" in navigator)navigator.serviceWorker.register("./sw.js").catch(()=>{});
