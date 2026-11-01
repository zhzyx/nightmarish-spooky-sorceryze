"""Run operator-provided representative cases; retain failures and scope, never self-approve."""
from pathlib import Path
import argparse,json
from runner import digest,read,now,schema_check
from adapters import call

def evaluate(profile,cases,scope):
    results=[]
    for case in cases:
        result={'id':case['id'],'task_type':case['task_type'],'passed':False}
        try:
            response=call(profile,case['messages'],case.get('max_output_tokens',512));result['response']=response
            if response['finish_reason']!='stop':raise ValueError('Incomplete output')
            action=json.loads(response['text'])
            if set(action)!={'action','value'} or action['action']!='final':raise ValueError('Final envelope required')
            schema_check(action['value'],case['schema'])
            if 'expected' in case and action['value']!=case['expected']:raise ValueError('Expected value mismatch')
            result['passed']=True
        except Exception as error:result['error']=str(error)
        results.append(result)
    kinds={r['task_type'] for r in results}
    passed=sorted(k for k in kinds if all(r['passed'] for r in results if r['task_type']==k))
    return {'profile_digest':digest(profile),'scope':scope,'time':now(),'suite_digest':digest(cases),'passed_task_types':passed,'results':results,'approval_granted':False,'limitations':'Only supplied cases; passing is not general semantic competence or production acceptance.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',required=True);p.add_argument('--suite',required=True);p.add_argument('--scope',choices=['synthetic','live'],required=True);p.add_argument('--out',required=True);a=p.parse_args()
    result=evaluate(read(a.profile),read(a.suite),a.scope)
    with open(a.out,'x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({'passed_task_types':result['passed_task_types'],'approval_granted':False}))
