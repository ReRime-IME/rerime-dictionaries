import base64
import copy
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops'))
from release_watch import (tick, DAY, REPO, V1, V2, V4, PROFILES, RequestError, check_state,
                           release_identity, producer_identity, run_title)


TREE = {'truncated':False, 'tree':[{'path':'recipe/emoji.txt','type':'blob','sha':'a'*40}]}
IDENTITY = producer_identity(TREE)
WORKFLOW_FILE = Path(__file__).resolve().parents[1] / '.github/workflows/dictionary.yml'


def done(release='42', producer=IDENTITY):
    """Every profile has completed `release`; v1 in the original top-level fields."""
    return {'completed_release':release, 'completed_producer':producer,
            'profiles':{profile:{'completed_release':release, 'completed_producer':producer}
                        for profile in (V2, V4)}}


class FakeAPI:
    token = 'test-only'
    def __init__(self, expires=40*DAY, v2_expires=None, v4_expires=None, missing=(), release=42):
        self.calls=[]
        self.expires={V1:expires, V2:expires if v2_expires is None else v2_expires,
                      V4:expires if v4_expires is None else v4_expires}
        self.missing=set(missing)
        self.release=release
        self.runs=[]
        self.fail_post=None
    def posts(self):
        return [call[2] for call in self.calls if call[1]=='POST']
    def run_for(self, request_id, profile, status='completed', conclusion='success'):
        run=dict(id=100+len(self.runs), display_title=run_title(profile, request_id),
                 status=status, conclusion=conclusion)
        self.runs.append(run)
        return run
    def request(self,path,method='GET',body=None,etag=None):
        self.calls.append((path,method,body,etag))
        if method=='POST':
            if self.fail_post: raise self.fail_post
            return None,None
        if '/git/trees/' in path:
            return (None,'producer-etag') if etag else (TREE,'producer-etag')
        if '/releases/latest' in path:
            return (None,'etag') if etag else (dict(id=self.release,draft=False,prerelease=False,published_at='date'),'etag')
        if '/contents/' in path:
            profile=next(profile for profile in PROFILES if profile in path)
            self.assertChannelPath(path, profile)
            if profile in self.missing: raise RequestError(404)
            payload=dict(repository=REPO,expires_at=self.expires[profile])
            envelope=dict(payload_base64=base64.b64encode(json.dumps(payload).encode()).decode())
            return dict(content=base64.b64encode(json.dumps(envelope).encode()).decode()),None
        if '/runs?' in path:return {'workflow_runs':list(self.runs)},None
        if '/actions/runs/' in path:
            return next(run for run in self.runs if str(run['id'])==path.rsplit('/',1)[1]),None
        raise AssertionError(path)
    @staticmethod
    def assertChannelPath(path, profile):
        assert path==f'repos/{REPO}/contents/channels/{profile}.json?ref=channel', path


class WatcherTests(unittest.TestCase):
    def test_daily_poll_etag_and_no_dispatch_when_unchanged(self):
        api=FakeAPI();state=done()
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'unchanged','v2':'unchanged','v4':'unchanged'})
        self.assertEqual(len(api.calls),5)  # Release, producer tree, three channels.
        tick(api,state,900,lambda:None)
        self.assertEqual(len(api.calls),5)
        tick(api,state,DAY,lambda:None)
        self.assertEqual(api.calls[5][3],'etag')
        self.assertFalse(api.posts())

    def test_dispatch_persisted_before_post_and_complete_after_success(self):
        api=FakeAPI();state={'profiles':{V2:done()['profiles'][V2]}};saved=[]
        self.assertEqual(tick(api,state,0,lambda:saved.append(copy.deepcopy(state)))['v1'],'dispatched')
        self.assertIn('pending',saved[-1])
        self.assertNotIn('completed_release',state)
        run=api.run_for(state['pending']['request_id'],V1,status='in_progress',conclusion=None)
        self.assertEqual(tick(api,state,900,lambda:None)['v1'],'running')
        run.update(status='completed',conclusion='success')
        self.assertEqual(tick(api,state,1800,lambda:None)['v1'],'completed')
        self.assertEqual(state['completed_release'],'42')
        self.assertEqual(len(api.posts()),1)

    def test_ambiguous_dispatch_survives_restart_without_resend(self):
        api=FakeAPI();api.fail_post=RequestError();state={}
        with self.assertRaises(RequestError):tick(api,state,0,lambda:None)
        recovered=json.loads(json.dumps(state))
        self.assertEqual(tick(api,recovered,900,lambda:None),{'v1':'awaiting-run','v2':'waiting','v4':'waiting'})
        self.assertEqual(len(api.posts()),1)
        tick(api,recovered,DAY+1,lambda:None)
        self.assertEqual(recovered['blocked'],'dispatch-not-found')

    def test_failed_run_backoff_and_access_failure(self):
        api=FakeAPI();state=done(release='41');tick(api,state,0,lambda:None)
        api.run_for(state['pending']['request_id'],V1,conclusion='failure')
        self.assertEqual(tick(api,state,900,lambda:None)['v1'],'failed')
        self.assertEqual(state['completed_release'],'41')
        self.assertEqual(tick(api,state,1000,lambda:None)['v1'],'backoff')
        state={};api.fail_post=RequestError(403)
        with self.assertRaises(RequestError):tick(api,state,0,lambda:None)
        self.assertEqual(state['blocked'],'dispatch-access-or-input')
        self.assertNotIn('pending',state)

    def test_renew_only_near_expiry(self):
        api=FakeAPI(expires=9*DAY);state=done()
        tick(api,state,0,lambda:None)
        inputs=api.posts()[-1]['inputs']
        self.assertEqual(inputs['operation'],'renew')
        self.assertEqual(inputs['release_id'],'')
        self.assertEqual(set(inputs),{'operation','release_id','request_id'})

    def test_missing_token_never_dispatches_and_nightly_rejected(self):
        api=FakeAPI();api.token=None
        self.assertEqual(tick(api,{},0,lambda:None),{'v1':'credential-required','v2':'waiting','v4':'waiting'})
        self.assertFalse(api.posts())
        with self.assertRaises(ValueError):release_identity(dict(id=1,draft=False,prerelease=True,published_at='date'))


class ProducerWatcherTests(unittest.TestCase):
    def test_recipe_change_dispatches_without_new_upstream_release(self):
        api=FakeAPI();state=done(producer='old')
        self.assertEqual(tick(api,state,0,lambda:None)['v1'],'dispatched')
        self.assertEqual(state['pending']['producer_identity'],IDENTITY)
        api.run_for(state['pending']['request_id'],V1)
        tick(api,state,900,lambda:None)
        self.assertEqual(state['completed_producer'],IDENTITY)
        self.assertEqual(tick(api,state,1800,lambda:None)['v1'],'unchanged')

    def test_failed_run_does_not_accept_new_producer(self):
        api=FakeAPI();state=done(producer='old')
        tick(api,state,0,lambda:None)
        api.run_for(state['pending']['request_id'],V1,conclusion='failure')
        tick(api,state,900,lambda:None)
        self.assertEqual(state['completed_producer'],'old')

    def test_documentation_does_not_change_identity_and_partial_tree_rejected(self):
        tree=copy.deepcopy(TREE)
        tree['tree'].append({'path':'docs/readme.md','type':'blob','sha':'b'*40})
        self.assertEqual(producer_identity(tree),IDENTITY)
        tree['truncated']=True
        with self.assertRaises(ValueError):producer_identity(tree)


class ProfileWatcherTests(unittest.TestCase):
    def test_v1_only_state_file_keeps_v1_and_seeds_v2_then_v4_once(self):
        # Exactly the fields the single-profile watcher wrote.
        old={'format_version':1,'completed_release':'42','completed_producer':IDENTITY,
             'observed_release':'42','release_etag':'etag','next_release_check':DAY,
             'observed_producer':IDENTITY,'producer_etag':'producer-etag','next_producer_check':DAY,
             'expires_at':40*DAY,'next_channel_check':DAY,'attempts':0,'last_run_id':7,
             'last_conclusion':'success'}
        state=check_state(json.loads(json.dumps(old)))
        api=FakeAPI()
        self.assertEqual(tick(api,state,900,lambda:None),{'v1':'unchanged','v2':'dispatched','v4':'waiting'})
        self.assertEqual([call[0].split('/')[-1] for call in api.calls if call[1]=='GET'],
                         [f'{V2}.json?ref=channel',f'{V4}.json?ref=channel'])
        self.assertEqual({k:state[k] for k in old},old)  # v1 fields untouched, no v1 dispatch.
        self.assertEqual(api.posts()[0]['inputs']['profile'],V2)
        self.assertEqual(set(state),set(old)|{'profiles'})
        api.run_for(api.posts()[0]['inputs']['request_id'],V2)
        self.assertEqual(tick(api,state,1800,lambda:None),{'v1':'waiting','v2':'completed','v4':'waiting'})
        self.assertEqual(tick(api,state,2700,lambda:None),{'v1':'unchanged','v2':'unchanged','v4':'dispatched'})
        self.assertEqual(api.posts()[1]['inputs']['profile'],V4)
        with self.assertRaises(ValueError):check_state({'format_version':2})
        with self.assertRaises(ValueError):check_state({'format_version':1,'profiles':{V1:{}}})
        with self.assertRaises(ValueError):
            check_state({'format_version':1,'profiles':{'wanxiang-ios-arm64-rime1161-v3':{}}})

    def test_two_profile_state_file_keeps_v1_v2_and_seeds_v4_once(self):
        # Exactly what the two-profile watcher wrote: v1 top level, v2 under profiles.
        state=check_state(json.loads(json.dumps(dict(done(),format_version=1,observed_release='42',
            release_etag='etag',next_release_check=DAY,observed_producer=IDENTITY,
            producer_etag='producer-etag',next_producer_check=DAY,expires_at=40*DAY,
            next_channel_check=DAY))))
        del state['profiles'][V4]
        state['profiles'][V2].update(expires_at=40*DAY,next_channel_check=DAY)
        before=copy.deepcopy(state)
        api=FakeAPI()
        self.assertEqual(tick(api,state,900,lambda:None),{'v1':'unchanged','v2':'unchanged','v4':'dispatched'})
        self.assertEqual([call[0].split('/')[-1] for call in api.calls if call[1]=='GET'],
                         [f'{V4}.json?ref=channel'])
        self.assertEqual(api.posts()[0]['inputs'],dict(operation='release',release_id='42',profile=V4,
                         request_id=state['profiles'][V4]['pending']['request_id']))
        self.assertEqual({k:v for k,v in state.items() if k!='profiles'},
                         {k:v for k,v in before.items() if k!='profiles'})
        self.assertEqual(state['profiles'][V2],before['profiles'][V2])
        api.run_for(api.posts()[0]['inputs']['request_id'],V4)
        self.assertEqual(tick(api,state,1800,lambda:None),{'v1':'waiting','v2':'waiting','v4':'completed'})
        self.assertEqual(tick(api,state,2700,lambda:None),{'v1':'unchanged','v2':'unchanged','v4':'unchanged'})
        self.assertEqual(state['profiles'][V4]['completed_release'],'42')
        self.assertEqual(len(api.posts()),1)

    def test_one_release_dispatches_v1_v2_then_v4_sequentially(self):
        api=FakeAPI(release=43);state=done()
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'dispatched','v2':'waiting','v4':'waiting'})
        v1=api.posts()[0]
        self.assertNotIn('profile',v1['inputs'])
        self.assertEqual(v1['inputs']['release_id'],'43')
        run=api.run_for(v1['inputs']['request_id'],V1,status='in_progress',conclusion=None)
        self.assertEqual(tick(api,state,900,lambda:None),{'v1':'running','v2':'waiting','v4':'waiting'})
        run.update(status='completed',conclusion='success')
        self.assertEqual(tick(api,state,1800,lambda:None),{'v1':'completed','v2':'waiting','v4':'waiting'})
        self.assertEqual(len(api.posts()),1)
        self.assertEqual(tick(api,state,2700,lambda:None),{'v1':'unchanged','v2':'dispatched','v4':'waiting'})
        v2=api.posts()[1]
        self.assertEqual(v2['inputs'],dict(operation='release',release_id='43',
                                           request_id=v2['inputs']['request_id'],profile=V2))
        api.run_for(v2['inputs']['request_id'],V2)
        self.assertEqual(tick(api,state,3600,lambda:None),{'v1':'waiting','v2':'completed','v4':'waiting'})
        self.assertEqual(len(api.posts()),2)
        self.assertEqual(tick(api,state,4500,lambda:None),{'v1':'unchanged','v2':'unchanged','v4':'dispatched'})
        v4=api.posts()[2]
        self.assertEqual(v4['inputs'],dict(operation='release',release_id='43',
                                           request_id=v4['inputs']['request_id'],profile=V4))
        api.run_for(v4['inputs']['request_id'],V4)
        self.assertEqual(tick(api,state,5400,lambda:None),{'v1':'waiting','v2':'waiting','v4':'completed'})
        self.assertEqual(tick(api,state,6300,lambda:None),{'v1':'unchanged','v2':'unchanged','v4':'unchanged'})
        self.assertEqual([profile_completed(state,profile) for profile in PROFILES],['43','43','43'])
        self.assertEqual(sum('/releases/latest' in call[0] for call in api.calls),1)
        self.assertEqual(len(api.posts()),3)

    def test_v2_renew_near_expiry_while_v1_fine(self):
        api=FakeAPI(expires=25*DAY,v2_expires=8*DAY);state=done()
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'unchanged','v2':'dispatched','v4':'unchanged'})
        self.assertEqual(api.posts()[0]['inputs'],dict(operation='renew',release_id='',profile=V2,
                         request_id=state['profiles'][V2]['pending']['request_id']))
        self.assertNotIn('pending',state)

    def test_v4_renew_near_expiry_while_v1_and_v2_fine(self):
        api=FakeAPI(expires=25*DAY,v4_expires=8*DAY);state=done()
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'unchanged','v2':'unchanged','v4':'dispatched'})
        self.assertEqual(api.posts()[0]['inputs'],dict(operation='renew',release_id='',profile=V4,
                         request_id=state['profiles'][V4]['pending']['request_id']))
        self.assertNotIn('pending',state)
        self.assertNotIn('pending',state['profiles'][V2])

    def test_missing_v2_channel_never_blocks_or_bootstraps_and_others_continue(self):
        api=FakeAPI(release=43,missing={V2});state=done()
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'dispatched','v2':'channel-missing','v4':'waiting'})
        api.run_for(api.posts()[0]['inputs']['request_id'],V1)
        self.assertEqual(tick(api,state,900,lambda:None)['v1'],'completed')
        self.assertEqual(tick(api,state,1800,lambda:None),{'v1':'unchanged','v2':'channel-missing','v4':'dispatched'})
        api.run_for(api.posts()[1]['inputs']['request_id'],V4)
        self.assertEqual(tick(api,state,2700,lambda:None)['v4'],'completed')
        self.assertEqual(tick(api,state,3600,lambda:None),{'v1':'unchanged','v2':'channel-missing','v4':'unchanged'})
        self.assertEqual(len(api.posts()),2)
        self.assertNotIn('blocked',state['profiles'][V2])
        api.missing.clear()  # Rechecked daily; a restored channel resumes v2.
        self.assertEqual(tick(api,state,DAY,lambda:None)['v2'],'dispatched')

    def test_missing_v4_channel_reports_and_v1_v2_continue(self):
        api=FakeAPI(release=43,missing={V4});state=done()
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'dispatched','v2':'waiting','v4':'channel-missing'})
        self.assertNotIn('blocked',state['profiles'][V4])
        self.assertTrue(state['profiles'][V4]['channel_missing'])

    def test_transient_v2_channel_error_does_not_starve_v1(self):
        api=FakeAPI(expires=9*DAY);state=done()
        original=api.request
        def request(path,**kw):
            if V2 in path: raise RequestError(502)
            return original(path,**kw)
        api.request=request
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'dispatched','v2':'channel-error','v4':'waiting'})
        self.assertNotIn('next_channel_check',state['profiles'][V2])

    def test_reconcile_matches_each_profile_exact_run_title(self):
        workflow=WORKFLOW_FILE.read_text()
        self.assertIn("run-name: Dictionary ${{ inputs.request_id || github.run_id }}"
                      "${{ inputs.profile == 'wanxiang-ios-arm64-rime1161-v2' && ' v2' || "
                      "inputs.profile == 'wanxiang-ios-arm64-rime1161-v4' && ' v4' || '' }}",workflow)
        self.assertIn('options: [wanxiang-ios-arm64-rime1161-v1, wanxiang-ios-arm64-rime1161-v2, '
                      'wanxiang-ios-arm64-rime1161-v4]',workflow)
        self.assertEqual(run_title(V1,'abc'),'Dictionary abc')
        self.assertEqual(run_title(V2,'abc'),'Dictionary abc v2')
        self.assertEqual(run_title(V4,'abc'),'Dictionary abc v4')
        api=FakeAPI(v2_expires=8*DAY);state=done()
        tick(api,state,0,lambda:None)
        request_id=state['profiles'][V2]['pending']['request_id']
        api.run_for(request_id,V1)  # Same nonce, v1 title: must not be adopted as the v2 run.
        self.assertEqual(tick(api,state,900,lambda:None)['v2'],'awaiting-run')
        api.run_for(request_id,V2,status='in_progress',conclusion=None)
        self.assertEqual(tick(api,state,1800,lambda:None)['v2'],'running')
        self.assertEqual(state['profiles'][V2]['pending']['run_id'],api.runs[1]['id'])

    def test_reconcile_v4_ignores_other_profiles_titles(self):
        api=FakeAPI(v4_expires=8*DAY);state=done()
        tick(api,state,0,lambda:None)
        request_id=state['profiles'][V4]['pending']['request_id']
        api.run_for(request_id,V1);api.run_for(request_id,V2)
        self.assertEqual(tick(api,state,900,lambda:None)['v4'],'awaiting-run')
        api.run_for(request_id,V4)
        self.assertEqual(tick(api,state,1800,lambda:None),{'v1':'waiting','v2':'waiting','v4':'completed'})
        self.assertEqual(state['profiles'][V4]['last_run_id'],api.runs[2]['id'])

    def test_blocked_and_backoff_are_isolated_per_profile(self):
        api=FakeAPI(release=43);state=done();state['blocked']='workflow-failed'
        state['profiles'][V4]['completed_release']='43'  # Keep v4 idle; covered below.
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'blocked','v2':'dispatched','v4':'unchanged'})
        self.assertEqual(api.posts()[0]['inputs']['profile'],V2)
        api.run_for(api.posts()[0]['inputs']['request_id'],V2,conclusion='failure')
        self.assertEqual(tick(api,state,900,lambda:None),{'v1':'blocked','v2':'failed','v4':'waiting'})
        self.assertEqual(tick(api,state,1800,lambda:None),{'v1':'blocked','v2':'backoff','v4':'unchanged'})
        self.assertEqual(state['blocked'],'workflow-failed')
        self.assertNotIn('retry_after',state)
        # v2 backoff does not hold v1 once v1 is unblocked.
        del state['blocked']
        self.assertEqual(tick(api,state,2700,lambda:None),{'v1':'dispatched','v2':'backoff','v4':'unchanged'})
        # A blocked v4 does not hold v1 or v2.
        api=FakeAPI(release=43);state=done();state['profiles'][V4]['blocked']='workflow-failed'
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'dispatched','v2':'waiting','v4':'blocked'})
        api=FakeAPI();state=done()
        for slot in (state,state['profiles'][V2],state['profiles'][V4]):slot['blocked']='x'
        self.assertEqual(tick(api,state,0,lambda:None),{'v1':'blocked','v2':'blocked','v4':'blocked'})
        self.assertFalse(api.calls)


def profile_completed(state, profile):
    return state['completed_release'] if profile==V1 else state['profiles'][profile]['completed_release']
