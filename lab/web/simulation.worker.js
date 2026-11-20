import { Simulation } from "eecircuit-engine";
let simulator=null;let ready=false;let busy=false;
async function init(){if(ready)return;simulator=new Simulation();await simulator.start();ready=true}
self.onmessage=async({data})=>{
 if(data?.type==="init"){try{await init();self.postMessage({type:"ready",info:simulator.getInitInfo?.()||""})}catch(e){self.postMessage({type:"error",message:String(e?.stack||e)})}return}
 if(data?.type!=="run")return;
 if(busy){self.postMessage({type:"error",message:"المحرك مشغول بتجربة أخرى"});return}
 busy=true;
 try{
  await init();
  simulator.setNetList(data.netlist);
  const result=await simulator.runSim();
  const errors=simulator.getError?.()||[];
  if(!result||!Array.isArray(result.data)||!result.data.length)throw new Error("لم يرجع المحرك بيانات رقمية");
  const serial={header:result.header,numVariables:result.numVariables,numPoints:result.numPoints,dataType:result.dataType,data:result.data.map(v=>({name:v.name,type:v.type,values:Array.from(v.values)})),info:simulator.getInfo?.()||"",errors};
  self.postMessage({type:"result",result:serial});
 }catch(e){self.postMessage({type:"error",message:String(e?.stack||e),details:simulator?.getInfo?.()||""})}
 finally{busy=false}
};