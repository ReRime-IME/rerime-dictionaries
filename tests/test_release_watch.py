import base64
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops'))
from release_watch import tick, DAY, REPO, RequestError, release_identity, producer_identity


TREE = {'truncated':False, 'tree':[{'path':'recipe/emoji.txt','type':'blob','sha':'a'*40}]}
IDENTITY = producer_identity(TREE)

class FakeAPI:
    token = 'test-only'
    def __init__(self, expires=40*DAY):
        self.calls=[]
        self.expires=expires
        self.run=None
        self.fail_post=None
    def request(self,path,method='GET',body=None,etag=None):
        self.calls.append((path,method,body,etag))
        if method=='POST':
            if self.fail_post: raise self.fail_post
            return None,None
        if '/git/trees/' in path:
            return (None,'producer-etag') if etag else (TREE,'producer-etag')
        if '/releases/latest' in path:
            return (None,'etag') if etag else (dict(id=42,draft=False,prerelease=False,published_at='date'),'etag')
        if '/contents/' in path:
            payload=dict(repository=REPO,expires_at=self.expires)
            envelope=dict(payload_base64=base64.b64encode(json.dumps(payload).encode()).decode())
            return dict(content=base64.b64encode(json.dumps(envelope).encode()).decode()),None
        if '/runs?' in path:return {'workflow_runs':[self.run] if self.run else []},None
        if '/actions/runs/' in path:return self.run,None
        raise AssertionError(path)


class WatcherTests(unittest.TestCase):
    def test_daily_poll_etag_and_no_dispatch_when_unchanged(self):
        api=FakeAPI();state={'completed_release':'42', 'completed_producer':IDENTITY}
        self.assertEqual(tick(api,state,0,lambda:None),'unchanged')
        self.assertEqual(len(api.calls),3)
        tick(api,state,900,lambda:None)
        self.assertEqual(len(api.calls),3)
        tick(api,state,DAY,lambda:None)
        self.assertEqual(api.calls[3][3],'etag')
        self.assertFalse(any(call[1]=='POST' for call in api.calls))

    def test_dispatch_persisted_before_post_and_complete_after_success(self):
        api=FakeAPI();state={};saved=[]
        self.assertEqual(tick(api,state,0,lambda:saved.append(copy.deepcopy(state))),'dispatched')
        self.assertIn('pending',saved[-1])
        self.assertNotIn('completed_release',state)
        nonce=state['pending']['request_id']
        api.run=dict(id=7,display_title='Dictionary '+nonce,status='in_progress',conclusion=None)
        self.assertEqual(tick(api,state,900,lambda:None),'running')
        api.run.update(status='completed',conclusion='success')
        self.assertEqual(tick(api,state,1800,lambda:None),'completed')
        self.assertEqual(state['completed_release'],'42')
        self.assertEqual(sum(c[1]=='POST' for c in api.calls),1)

    def test_ambiguous_dispatch_survives_restart_without_resend(self):
        api=FakeAPI();api.fail_post=RequestError();state={}
        with self.assertRaises(RequestError):tick(api,state,0,lambda:None)
        recovered=json.loads(json.dumps(state))
        self.assertEqual(tick(api,recovered,900,lambda:None),'awaiting-run')
        self.assertEqual(sum(c[1]=='POST' for c in api.calls),1)
        tick(api,recovered,DAY+1,lambda:None)
        self.assertEqual(recovered['blocked'],'dispatch-not-found')

    def test_failed_run_backoff_and_access_failure(self):
        api=FakeAPI();state={};tick(api,state,0,lambda:None)
        api.run=dict(id=7,display_title='Dictionary '+state['pending']['request_id'],status='completed',conclusion='failure')
        self.assertEqual(tick(api,state,900,lambda:None),'failed')
        self.assertNotIn('completed_release',state)
        self.assertEqual(tick(api,state,1000,lambda:None),'backoff')
        state={};api.fail_post=RequestError(403)
        with self.assertRaises(RequestError):tick(api,state,0,lambda:None)
        self.assertEqual(state['blocked'],'dispatch-access-or-input')
        self.assertNotIn('pending',state)

    def test_renew_only_near_expiry(self):
        api=FakeAPI(expires=9*DAY);state={'completed_release':'42', 'completed_producer':IDENTITY}
        tick(api,state,0,lambda:None)
        inputs=api.calls[-1][2]['inputs']
        self.assertEqual(inputs['operation'],'renew')
        self.assertEqual(inputs['release_id'],'')
        self.assertEqual(set(inputs),{'operation','release_id','request_id'})

    def test_missing_token_never_dispatches_and_nightly_rejected(self):
        api=FakeAPI();api.token=None
        self.assertEqual(tick(api,{},0,lambda:None),'credential-required')
        self.assertFalse(any(c[1]=='POST' for c in api.calls))
        with self.assertRaises(ValueError):release_identity(dict(id=1,draft=False,prerelease=True,published_at='date'))


class ProducerWatcherTests(unittest.TestCase):
    def test_recipe_change_dispatches_without_new_upstream_release(self):
        api=FakeAPI();state={'completed_release':'42','completed_producer':'old'}
        self.assertEqual(tick(api,state,0,lambda:None),'dispatched')
        self.assertEqual(state['pending']['producer_identity'],IDENTITY)
        api.run=dict(id=8,display_title='Dictionary '+state['pending']['request_id'],status='completed',conclusion='success')
        tick(api,state,900,lambda:None)
        self.assertEqual(state['completed_producer'],IDENTITY)
        self.assertEqual(tick(api,state,1800,lambda:None),'unchanged')

    def test_failed_run_does_not_accept_new_producer(self):
        api=FakeAPI();state={'completed_release':'42','completed_producer':'old'}
        tick(api,state,0,lambda:None)
        api.run=dict(id=8,display_title='Dictionary '+state['pending']['request_id'],status='completed',conclusion='failure')
        tick(api,state,900,lambda:None)
        self.assertEqual(state['completed_producer'],'old')

    def test_documentation_does_not_change_identity_and_partial_tree_rejected(self):
        tree=copy.deepcopy(TREE)
        tree['tree'].append({'path':'docs/readme.md','type':'blob','sha':'b'*40})
        self.assertEqual(producer_identity(tree),IDENTITY)
        tree['truncated']=True
        with self.assertRaises(ValueError):producer_identity(tree)
