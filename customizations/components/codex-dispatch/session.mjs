// Run once for a real event. The current Codex host services native requests.
import fs from 'node:fs';
import {openSession} from './operator.mjs';
import {reservationOperation, withBlockerRouting} from '../issue-workorders/kuafu_dispatch.mjs';
const config=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const host = await withBlockerRouting(config, async () => {
  const {host,bridge}=await openSession(config);
  console.log(JSON.stringify({state:'host_bound',nativeRoot:bridge.root}));
  if(config.action==='reconcile')await reservationOperation(config, () => host.reconcile(config.event,config.reservationKey,config.workerReceipt));
  else if(config.action==='setup')await reservationOperation(config, () => host.completeSetup(config.event,config.reservationKey,config.workerReceipt));
  else if(config.action==='release-unstarted')await reservationOperation(config, () => host.releaseUnstarted(config.event,config.reservationKey));
  else if(config.action&&config.action!=='dispatch')throw Error('Unsupported event action');
  return host;
});
const result = await withBlockerRouting({...config,action:'dispatch'}, () => host.run(config.event,config.requests));
fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2));
console.log(JSON.stringify({state:'event_completed',output:process.argv[3]}));
