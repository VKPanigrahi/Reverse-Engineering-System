"""Checkpointed research: retry failures and reuse commit-pinned successful profiles."""
from datetime import datetime, timezone
import hashlib
import json
import time
from .repositories import acquire, repository_name
from .synthesis import synthesize, handoff

def investigate(project, references, checkpoint, refresh=False):
    if not isinstance(references,list) or not 1<=len(references)<=4:
        raise ValueError('Provide between one and four GitHub repository URLs.')
    names=list(dict.fromkeys(repository_name(r) for r in references))
    old=project.get('investigation',{})
    existing={p['repository']:p for p in old.get('profiles',[])}
    run={'status':'running','started_at':datetime.now(timezone.utc).isoformat(),
         'references':names,'profiles':[],'errors':[],'events':[]}
    project['investigation']=run
    project.pop('design',None)
    checkpoint(project)
    for name in names:
        start=time.monotonic()
        try:
            cached=not refresh and name in existing
            profile=existing[name] if cached else acquire(name)
            run['profiles'].append(profile)
            run['events'].append({'repository':name,'stage':'profile','status':'reused' if cached else 'completed',
                                  'commit':profile['commit'],'seconds':round(time.monotonic()-start,2)})
        except (ValueError,OSError) as error:
            run['errors'].append({'repository':name,'message':str(error)[:500]})
            run['events'].append({'repository':name,'stage':'profile','status':'failed'})
        checkpoint(project)
    run['analysis']=synthesize(project['requirements'],run['profiles'])
    run['handoff']=handoff(project['goal'],run['analysis'],run['profiles'])
    run['status']='partial' if run['errors'] and run['profiles'] else 'failed' if run['errors'] else 'completed'
    run['finished_at']=datetime.now(timezone.utc).isoformat()
    identity={'references':[(p['repository'],p['commit']) for p in run['profiles']], 'requirements':project['requirements']}
    run['input_hash']=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    project['stage']='Investigate'
    checkpoint(project)
    return project
