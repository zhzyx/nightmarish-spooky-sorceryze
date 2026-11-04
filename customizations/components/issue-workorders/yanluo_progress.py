"""Post-merge acceptance reconciliation. Never infer completion from LOC or PR count."""
import hashlib
import json


def assess(items):
    if not items or len({x['id'] for x in items}) != len(items):
        raise ValueError('Unique acceptance items required')
    for item in items:
        if item['state'] not in {'done', 'remaining', 'unknown'}:
            raise ValueError('Unknown acceptance state')
        if not item.get('evidence') or not item.get('module') or not item.get('acceptance'):
            raise ValueError('Every conclusion needs evidence, module and acceptance')
    done = [x for x in items if x['state'] == 'done']
    remaining = [x for x in items if x['state'] == 'remaining']
    unknown = [x for x in items if x['state'] == 'unknown']
    modules = {x['module'] for x in items}
    remaining_modules = {x['module'] for x in remaining}
    # This is an item-count policy, not estimated effort, time or percentage of code.
    majority = len(done) > len(items) / 2
    small_module_tail = bool(done and remaining) and len(remaining_modules) <= 2 and len(remaining_modules) < len(modules)
    return {'done': done, 'remaining': remaining, 'unknown': unknown,
            'complete': len(done) == len(items),
            'split': bool(remaining) and not unknown and (majority or small_module_tail),
            'basis': 'verified_acceptance_item_count_or_at_most_two_remaining_modules',
            'counts': {'done': len(done), 'total': len(items), 'remaining': len(remaining), 'unknown': len(unknown)}}


def followup(parent, request_id, module, items, main_commit):
    stable = hashlib.sha256(json.dumps([parent, request_id, module, sorted(x['id'] for x in items)],
                                      ensure_ascii=False).encode()).hexdigest()[:20]
    rid = 'yanluo-followup-' + stable
    marker = '<!-- gonggong-request:' + rid + ' -->'
    body = marker + '\n\n来源 Issue：#' + str(parent) + '\n已合入 main：`' + main_commit + '`\n\n'
    body += '剩余模块：' + module + '\n\n验收项：\n'
    body += '\n'.join('- [ ] ' + x['id'] + '：' + x['acceptance'] + '\n  依据：' + x['evidence'] for x in items)
    body += '\n\n仅承接上述未完成范围；原 Issue 的整体验收与依赖继续保留。由司南按实际容量推进，不因建单自动获得执行授权。\n'
    return {'request_id': rid, 'marker': marker, 'title': f'#{parent} 剩余推进：{module}', 'body': body}


def reconcile(host, candidate, items):
    result = assess(items)
    remote = host.read_main(candidate)
    if not remote['contained']:
        raise ValueError('Post-merge reconciliation requires verified main receipt')
    links = []
    if result['split']:
        # Search all pages, open and closed; ambiguous duplicates stop rather than
        # creating another issue. Same shared main lock serializes local creators.
        pages = host.issue_pages(candidate)
        for module in sorted({x['module'] for x in result['remaining']}):
            work = followup(candidate.issue, candidate.request_id, module,
                            [x for x in result['remaining'] if x['module'] == module], remote['remote_commit'])
            matches = [x for page in pages for x in page
                       if 'pull_request' not in x and work['marker'] in (x.get('body') or '')]
            if len(matches) > 1:
                raise ValueError('Duplicate remaining-work Issue identity')
            if matches and matches[0]['state'] != 'open':
                raise ValueError('Remaining scope maps to a closed Issue; reconcile closure or successor before advancing')
            issue = matches[0] if matches else host.create_followup(candidate, work)
            links.append({'module': module, 'url': issue['html_url'], 'request_id': work['request_id']})
    summary = {'counts': result['counts'], 'complete': result['complete'], 'split': result['split'],
               'basis': result['basis'], 'followups': links,
               'remaining': result['remaining'], 'unknown': result['unknown'],
               'main_commit': remote['remote_commit']}
    host.record(candidate, 'progress.reconciled', summary)
    return summary
