import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from gorilla.office_mcp import make_server

class BusinessDouble:
    def __init__(self): self.calls=[]
    def request(self,path,body=None):
        self.calls.append((path,body))
        if path.startswith('/api/messages'): return [{'id':'finance-001','subject':'Finance'}]
        return {'status':'verified'}

class MCPTests(unittest.TestCase):
    def setUp(self):
        self.business=BusinessDouble()
        self.server=make_server('127.0.0.1',0,self.business,'test-token')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/mcp'
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def rpc(self,method,params=None,session=None,token='test-token',rid=1):
        h={'Content-Type':'application/json','Authorization':'Bearer '+token}
        if session:h['Mcp-Session-Id']=session
        req=Request(self.url,json.dumps({'jsonrpc':'2.0','id':rid,'method':method,'params':params or {}}).encode(),h)
        with urlopen(req) as r:return json.load(r),r.headers.get('Mcp-Session-Id')
    def test_unauthorized_client_cannot_discover_or_mutate(self):
        with self.assertRaises(HTTPError) as e:self.rpc('tools/list',token='wrong')
        self.assertEqual(e.exception.code,401);self.assertEqual(self.business.calls,[])
    def test_tool_catalog_has_only_three_reads_and_one_guarded_mutation(self):
        _,session=self.rpc('initialize',{'protocolVersion':'2025-03-26'})
        result,_=self.rpc('tools/list',session=session)
        names=[t['name'] for t in result['result']['tools']]
        self.assertEqual(names,['office_inbox_list','office_email_inspect','office_operation_result','office_email_action'])
    def test_normal_action_becomes_canonical_guarded_proposal(self):
        _,session=self.rpc('initialize')
        args={'message_id':'finance-001','action':'DELETE'}
        self.rpc('tools/call',{'name':'office_email_action','arguments':args},session, rid=8)
        path,body=self.business.calls[-1]
        self.assertEqual(path,'/api/act');self.assertEqual(body['proposed_choices'],['DELETE','ARCHIVE','KEEP','FLAG'])
        self.assertEqual(body['agent_activity']['requested_action'],'DELETE')
        self.rpc('tools/call',{'name':'office_email_action','arguments':args},session,rid=8)
        self.assertEqual(body['request_id'],self.business.calls[-1][1]['request_id'])
    def test_unknown_arguments_cannot_replace_execution_arguments(self):
        _,session=self.rpc('initialize')
        result,_=self.rpc('tools/call',{'name':'office_email_action','arguments':{'message_id':'finance-001','action':'DELETE','sql':'anything'}},session)
        self.assertTrue(result['result']['isError']);self.assertEqual(self.business.calls,[])

    def test_reconnection_cannot_repeat_the_one_assigned_business_operation(self):
        args={'message_id':'finance-001','action':'ARCHIVE'}
        _,first=self.rpc('initialize')
        self.rpc('tools/call',{'name':'office_email_action','arguments':args},first,rid=8)
        original=self.business.calls[-1][1]
        _,second=self.rpc('initialize')
        self.rpc('tools/call',{'name':'office_email_action','arguments':args},second,rid=99)
        self.assertEqual(original,self.business.calls[-1][1])

    def test_result_is_recoverable_without_a_lost_decision_identifier(self):
        self.business.request=lambda path,body=None:[{'decision_id':'recovered','request_id':'office-morning-finance-001'}]
        _,session=self.rpc('initialize')
        result,_=self.rpc('tools/call',{'name':'office_operation_result','arguments':{}},session)
        self.assertNotIn('isError',result['result'])
        self.assertIn('recovered',result['result']['content'][0]['text'])

    def test_stateless_reconnects_do_not_exhaust_sessions(self):
        _,session=self.rpc('initialize')
        self.assertIsNone(session)
