import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
export const handovers={list:()=>api('/handovers'),get:id=>api('/handovers/'+id),create:data=>api('/handovers',{method:'POST',body:JSON.stringify(data)}),resume:id=>api('/handovers/'+id+'/resume',{method:'POST'}),verify:id=>api('/handovers/'+id+'/verify',{method:'POST'})};
