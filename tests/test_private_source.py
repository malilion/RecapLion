import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/github-year-review/scripts'
sys.path.insert(0, str(SCRIPTS))
import private_source as private
import fetch_github_year as fetch
import recap

START = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
END = dt.datetime(2026, 1, 4, tzinfo=dt.timezone.utc)


def page(nodes, following=None):
    return {'nodes': nodes, 'pageInfo': {'hasNextPage': following is not None, 'endCursor': following}}


def repository(name, private=False, fork=False):
    return {'id': name, 'nameWithOwner': 'demo/'+name, 'isPrivate': private, 'isFork': fork,
            'createdAt': '2026-01-01T00:00:00Z'}


class FakeGitHub:
    def __init__(self, already_counted=False, restricted=False):
        self.calls = []
        self.public = repository('public')
        self.private = repository('secret', private=True)
        self.fork = repository('fork', private=True, fork=True)
        self.cc = {
            'totalCommitContributions': 12 if already_counted else 10,
            'totalPullRequestContributions': 1, 'totalIssueContributions': 0,
            'totalPullRequestReviewContributions': 0, 'totalRepositoryContributions': 1,
            'totalRepositoriesWithContributedCommits': 1,
            'restrictedContributionsCount': 6 if restricted else 0,
            'contributionCalendar': {'totalContributions': 16 if already_counted or restricted else 10,
                'weeks': [{'contributionDays': [
                    {'date':'2026-01-01','contributionCount':16 if already_counted or restricted else 10,'weekday':4},
                    {'date':'2026-01-02','contributionCount':0,'weekday':5}]}]},
            'commitContributionsByRepository': [
                {'repository':self.public,'contributions':{'totalCount':10}}],
            'pullRequestContributionsByRepository': [], 'issueContributionsByRepository': [],
            'pullRequestReviewContributionsByRepository': [], 'repositoryContributions': {'nodes':[]},
        }
        if already_counted:
            self.cc['commitContributionsByRepository'].append(
                {'repository':self.private,'contributions':{'totalCount':1}})
        self.viewer = {'id':'ACCOUNT','login':'demo'}

    def __call__(self, document, variables):
        self.calls.append((document, copy.deepcopy(variables)))
        after = variables.get('after')
        if document == private.PROFILE_QUERY:
            return {'viewer':self.viewer, 'user':{'login':'demo','contributionsCollection':copy.deepcopy(self.cc)}}
        if 'ownerAffiliations:OWNER' in document:
            nodes = page([self.public,self.private], 'repos-2') if after is None else page([self.fork])
            return {'viewer':{'repositories':nodes}}
        if 'messageHeadline' in document:
            assert variables['id'] == 'secret', 'Fork histories must not be fetched'
            first = {'oid':'A','authoredDate':'2026-01-01T20:30:00Z','messageHeadline':'Private subject'}
            if after is None:
                obj = {'oid':'PINNED_HEAD','history':page([first], 'commits-2')}
                return {'node':{'defaultBranchRef':{'target':obj}}}
            assert variables['head'] == 'PINNED_HEAD'
            second = {'oid':'B','authoredDate':'2026-01-02T20:30:00Z','messageHeadline':'Private second'}
            at_end = {'oid':'C','authoredDate':'2026-01-04T00:00:00Z','messageHeadline':'Excluded end boundary'}
            return {'node':{'object':{'oid':'PINNED_HEAD','history':page([first,second,at_end])}}}
        if 'orderBy:{field:CREATED_AT,direction:DESC}' in document:
            field = 'pullRequests' if 'viewer{pullRequests' in document else 'issues'
            date = '2026-01-02T00:00:00Z' if field == 'pullRequests' else '2026-01-03T00:00:00Z'
            nodes = page([{'createdAt':date,'repository':self.private},
                          {'createdAt':date,'repository':self.public}], field+'-2') if after is None else page([
                              {'createdAt':'2025-12-01T00:00:00Z','repository':self.private}])
            return {'viewer':{field:nodes}}
        if 'issueCount' in document:
            result = page([{'id':'PR','repository':self.private}]);result['issueCount']=1
            return {'search':result}
        if 'reviews(first:100' in document:
            return {'node':{'reviews':page([
                {'author':{'login':'demo'},'submittedAt':'2026-01-03T05:00:00Z'},
                {'author':{'login':'other'},'submittedAt':'2026-01-03T05:00:00Z'},
                {'author':{'login':'demo'},'submittedAt':None},
            ])}}
        if document == 'SEARCH_COUNTS':
            return {'merged':{'issueCount':1}}
        raise AssertionError('Unexpected query')


def collect(api):
    return private.collect('demo', START, END, 'Asia/Taipei', api, 'nameWithOwner isPrivate',
                           'SEARCH_COUNTS', lambda _:None)


class PrivateCollectionTests(unittest.TestCase):
    def test_omitted_private_activity_is_paginated_reconstructed_and_timezoned(self):
        api = FakeGitHub()
        result = collect(api)
        cc = result['contributions']
        self.assertEqual(result['owned_repositories']['totalCount'],3)
        self.assertEqual(cc['totalCommitContributions'],12)
        self.assertEqual(cc['totalPullRequestContributions'],2)
        self.assertEqual(cc['totalIssueContributions'],1)
        self.assertEqual(cc['totalPullRequestReviewContributions'],1)
        self.assertEqual(cc['contributionCalendar']['totalContributions'],16)
        days = {d['date']:d['contributionCount'] for w in cc['contributionCalendar']['weeks'] for d in w['contributionDays']}
        self.assertEqual(days,{'2026-01-01':11,'2026-01-02':2,'2026-01-03':3})
        self.assertEqual(result['private_activity']['commits'],2)
        self.assertEqual(result['private_activity']['reviews'],1)
        self.assertEqual(result['private_activity']['repositories_visible'],1)
        self.assertTrue(result['private_activity']['calendar_reconstructed'])

    def test_existing_private_calendar_is_not_counted_twice(self):
        api = FakeGitHub(already_counted=True)
        result = collect(api)
        self.assertEqual(result['contributions']['contributionCalendar'],api.cc['contributionCalendar'])
        self.assertEqual(result['contributions']['totalCommitContributions'],12)
        rows = result['contributions']['commitContributionsByRepository']
        self.assertEqual(len([r for r in rows if r['repository']['isPrivate']]),1)
        self.assertEqual(rows[-1]['contributions']['totalCount'],2)
        self.assertFalse(result['private_activity']['calendar_reconstructed'])

    def test_anonymous_restricted_calendar_is_not_counted_twice(self):
        api = FakeGitHub(restricted=True)
        result = collect(api)
        self.assertEqual(result['contributions']['contributionCalendar'],api.cc['contributionCalendar'])
        self.assertEqual(result['contributions']['totalCommitContributions'],12)
        self.assertEqual(result['contributions']['totalPullRequestContributions'],2)
        self.assertFalse(result['private_activity']['calendar_reconstructed'])

    def test_private_read_failure_is_fatal(self):
        api = FakeGitHub()
        def failing(document, variables):
            if 'messageHeadline' in document:
                raise RuntimeError('Access denied')
            return api(document,variables)
        with self.assertRaisesRegex(RuntimeError,'Access denied'):
            collect(failing)

    def test_private_repository_creation_already_in_calendar_prevents_double_counting(self):
        api = FakeGitHub()
        api.cc['repositoryContributions']['nodes'] = [{'repository': api.private}]
        result = collect(api)
        self.assertEqual(result['contributions']['contributionCalendar'], api.cc['contributionCalendar'])
        self.assertFalse(result['private_activity']['calendar_reconstructed'])

    def test_pagination_that_does_not_advance_fails_instead_of_looping(self):
        with self.assertRaisesRegex(RuntimeError, 'non-advancing'):
            list(private.connection_pages(lambda q, v:page([], 'same'), 'q', {}, lambda d:d))

    def test_private_review_search_cap_fails_instead_of_returning_partial_results(self):
        def capped(q, v):
            result=page([]);result['issueCount']=1001
            return {'search':result}
        with self.assertRaisesRegex(RuntimeError, '1,000-result cap'):
            private.private_reviews(capped, 'demo', START, END)

    def test_wrong_authenticated_account_is_rejected(self):
        api = FakeGitHub();api.viewer={'id':'OTHER','login':'other'}
        with self.assertRaisesRegex(RuntimeError,'match the authenticated'):
            collect(api)
        self.assertEqual(len(api.calls),1)

    def test_partial_graphql_data_is_not_accepted_for_inclusive_collection(self):
        with patch.object(fetch,'request',return_value=({'data':{'viewer':{}},'errors':[{'message':'Denied'}]},{})):
            with self.assertRaisesRegex(RuntimeError,'Denied'):
                fetch.graphql('query',{},'token',strict=True)


class InclusiveCliTests(unittest.TestCase):
    def test_missing_token_does_not_fall_back_to_public_search(self):
        with patch.object(sys,'argv',['fetch','--user','demo','--include-private']), \
             patch.object(fetch,'get_token',return_value=None), patch.object(fetch,'fetch_search') as search:
            with self.assertRaises(SystemExit) as error:
                fetch.main()
            self.assertEqual(error.exception.code,2)
            search.assert_not_called()

    def test_source_that_cannot_include_private_is_rejected(self):
        with patch.object(sys,'argv',['fetch','--user','demo','--include-private','--source','rest']), \
             patch.object(fetch,'get_token',return_value='token'), patch.object(fetch,'fetch_rest') as rest:
            with self.assertRaises(SystemExit):
                fetch.main()
            rest.assert_not_called()

    def test_public_cache_cannot_be_presented_as_an_inclusive_report(self):
        with tempfile.TemporaryDirectory() as out:
            Path(out,'raw.json').write_text(json.dumps({'meta':{}}))
            with patch.object(sys,'argv',['recap','--user','demo','--include-private','--skip-fetch','--out',out]), \
                 patch.object(recap,'run') as run:
                with self.assertRaises(SystemExit):
                    recap.main()
                run.assert_not_called()

    def test_token_is_not_printed_in_command_log(self):
        import contextlib,io
        output=io.StringIO()
        with patch.object(recap.subprocess,'run') as run, contextlib.redirect_stderr(output):
            recap.run('fetch_github_year.py','--token','SECRET_TEST_TOKEN')
        self.assertNotIn('SECRET_TEST_TOKEN',output.getvalue())
        self.assertIn('[redacted]',output.getvalue())
        self.assertIn('SECRET_TEST_TOKEN',run.call_args.args[0])

    def test_private_cache_for_another_account_or_year_is_rejected(self):
        for user,year in [('someone-else',2026),('demo',2025)]:
            with self.subTest(user=user,year=year), tempfile.TemporaryDirectory() as out:
                Path(out,'raw.json').write_text(json.dumps({'meta':{
                    'include_private':True,'user':user,'year':year}}))
                with patch.object(sys,'argv',['recap','--user','demo','--year','2026',
                     '--include-private','--skip-fetch','--out',out]),patch.object(recap,'run') as run:
                    with self.assertRaises(SystemExit):
                        recap.main()
                    run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
