"""Non-streaming model transports. Provider text is data, never executable code."""
import json, os, urllib.request, urllib.parse

class TransportUnknown(RuntimeError):
    """Request may have reached the provider. Never automatically retry."""

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)

def call(profile, messages, output_limit):
    protocol=profile['protocol'];endpoint=profile['endpoint'];url=urllib.parse.urlsplit(endpoint)
    if url.username or url.password or url.fragment or url.query:
        raise ValueError('Endpoint must not embed credentials, query or fragment')
    if url.scheme!='https' and not (url.scheme=='http' and url.hostname in {'localhost','127.0.0.1','::1'}):
        raise ValueError('HTTPS required outside loopback')
    if profile.get('system_role',True) is False:
        messages=[{'role':'user','content':'\n\n'.join(m['role']+':\n'+m['content'] for m in messages)}]
    body={'model':profile['model'],'messages':messages,'stream':False}
    if protocol=='chat-completions':
        parameter=profile.get('output_parameter','max_tokens')
        if parameter not in {'max_tokens','max_completion_tokens'}:raise ValueError('Invalid output parameter')
        body[parameter]=output_limit
    elif protocol=='ollama-chat':body['options']={'num_predict':output_limit}
    elif protocol=='gonggong-json':body['max_output_tokens']=output_limit
    else:raise ValueError('Unsupported protocol')
    headers={'Content-Type':'application/json'}
    if profile.get('api_key_env'):
        secret=os.environ.get(profile['api_key_env'])
        if not secret:raise ValueError('Credential environment variable missing')
        headers['Authorization']='Bearer '+secret
    request=urllib.request.Request(endpoint,data=canonical(body).encode(),headers=headers,method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=profile.get('timeout_seconds',30)) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Response exceeds limit')
        data=json.loads(raw)
    except Exception as error:
        # Do not log provider response bodies, keys or URLs in exceptions.
        raise TransportUnknown(type(error).__name__+': transport outcome requires reconciliation') from None
    try:
        if protocol=='chat-completions':
            choice=data['choices'][0];text=choice['message'].get('content');finish=choice['finish_reason'];u=data.get('usage') or {}
            usage={'input_tokens':u.get('prompt_tokens'),'output_tokens':u.get('completion_tokens')}
            usage['cache_read_input_tokens']=(u.get('prompt_tokens_details') or {}).get('cached_tokens')
            usage['reasoning_output_tokens']=(u.get('completion_tokens_details') or {}).get('reasoning_tokens')
        elif protocol=='ollama-chat':
            text=data['message']['content'];finish=data.get('done_reason','stop') if data.get('done') is True else 'incomplete'
            usage={'input_tokens':data.get('prompt_eval_count'),'output_tokens':data.get('eval_count'),'cache_read_input_tokens':data.get('prompt_eval_cached_count')}
        else:
            text=data['text'];finish=data['finish_reason'];usage=data.get('usage') or {}
        if not isinstance(text,str):raise ValueError('Text response required')
        usage={k:v for k,v in usage.items() if k in {'input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens','reasoning_output_tokens'}}
        if any(type(v) is not int or v<0 for v in usage.values() if v is not None):raise ValueError('Invalid usage')
        for subset,total in [('cache_read_input_tokens','input_tokens'),('cache_creation_input_tokens','input_tokens'),('reasoning_output_tokens','output_tokens')]:
            if usage.get(subset) is not None and usage.get(total) is not None and usage[subset]>usage[total]:raise ValueError('Usage subset exceeds total')
        return {'text':text,'finish_reason':finish,'usage':usage,'provider_request_id':str(data.get('id','unavailable'))}
    except (KeyError,IndexError,TypeError,ValueError,AttributeError):
        raise TransportUnknown('Malformed provider response; usage and completion require reconciliation') from None
