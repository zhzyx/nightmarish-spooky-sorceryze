// Run once for a real event. The current Codex host services native requests.
import fs from 'node:fs';
import {openSession} from './operator.mjs';
const config=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const {host,bridge}=await openSession(config);
console.log(JSON.stringify({state:'host_bound',nativeRoot:bridge.root}));
if(config.action==='reconcile')await host.reconcile(config.event,config.reservationKey,config.workerReceipt);
else if(config.action==='setup')await host.completeSetup(config.event,config.reservationKey,config.workerReceipt);
else if(config.action==='release-unstarted')await host.releaseUnstarted(config.event,config.reservationKey);
else if(config.action&&config.action!=='dispatch')throw Error('Unsupported event action');
const result=await host.run(config.event,config.requests);
fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2));
console.log(JSON.stringify({state:'event_completed',output:process.argv[3]}));
