"""Minimal authenticated office tools for NemoClaw's native MCP integration."""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .core import CATALOG
from .telegram import GatewayClient, ROOT

def schema(properties, required=()):
    return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}

MESSAGE = {'type':'string','enum':['finance-001']}
OPERATION_ID = 'office-morning-finance-001'
TOOLS = [
    {'name':'office_inbox_list','description':'List business correspondence in inbox or archive.',
     'inputSchema':schema({'folder':{'type':'string','enum':['inbox','archive']}}, ['folder'])},
    {'name':'office_email_inspect','description':'Read the complete assigned email and authoritative metadata.',
     'inputSchema':schema({'message_id':MESSAGE}, ['message_id'])},
    {'name':'office_operation_result','description':'Read the assigned morning operation result. Omit decision_id to recover a lost response.',
     'inputSchema':schema({'decision_id':{'type':'string'}})},
    {'name':'office_email_action','description':'Request DELETE, ARCHIVE, KEEP, or FLAG for the one assigned morning email operation. Retries reuse the same operation. The office service applies company policy and returns the actual executed operation and verified result. Report the returned result, not your requested action.',
     'inputSchema':schema({'message_id':MESSAGE,'action':{'type':'string','enum':list(CATALOG)}}, ['message_id','action'])},
]

def call_tool(business, session, rid, name, args):
    spec = next((t for t in TOOLS if t['name']==name),None)
    if spec is None or not isinstance(args,dict): raise ValueError('Unknown tool or invalid arguments')
    s=spec['inputSchema']
    if set(args)-set(s['properties']) or set(s['required'])-set(args): raise ValueError('Unexpected or missing arguments')
    for key,value in args.items():
        rule=s['properties'][key]
        if not isinstance(value,str) or len(value)>128 or ('enum' in rule and value not in rule['enum']):
            raise ValueError('Invalid scoped argument')
    if name=='office_inbox_list':return business.request('/api/messages?folder='+args['folder'])
    if name=='office_email_inspect':
        for folder in ['inbox','archive','trash']:
            for msg in business.request('/api/messages?folder='+folder):
                if msg['id']==args['message_id']:return msg
        raise ValueError('Assigned email not found')
    if name=='office_operation_result':
        for d in business.request('/api/decisions'):
            if d['request_id']==OPERATION_ID and (not args.get('decision_id') or d['decision_id']==args['decision_id']):return d
        return {'status':'not_requested','operation_id':OPERATION_ID}
    action=args['action']
    return business.request('/api/act', {
        'request_id':OPERATION_ID, 'message_id':args['message_id'],
        'proposed_choices':[action]+[x for x in CATALOG if x!=action],
        'agent_activity':{'agent':'NemoClaw-managed OpenClaw','tool':'office_email_action','requested_action':action},
    })

def make_server(host,port,business,token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,data=None,session=None):
            body=json.dumps(data,allow_nan=False).encode() if data is not None else b''
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            if session:self.send_header('Mcp-Session-Id',session)
            self.end_headers();self.wfile.write(body)
        def do_GET(self):self.reply(405)
        def do_POST(self):
            if self.path!='/mcp':return self.reply(404)
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply(401)
            try:
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<=32768:return self.reply(413)
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict) or body.get('jsonrpc')!='2.0':return self.reply(400)
                method=body.get('method');rid=body.get('id');params=body.get('params') or {}
                if not isinstance(params,dict):return self.reply(400)
                if method=='initialize':
                    return self.reply(200,{'jsonrpc':'2.0','id':rid,'result':{
                        'protocolVersion':params.get('protocolVersion','2025-03-26'),
                        'capabilities':{'tools':{'listChanged':False}},
                        'serverInfo':{'name':'gorilla-office','version':'0.1.0'}}})
                session=self.headers.get('Mcp-Session-Id','')
                if method=='notifications/initialized':return self.reply(202)
                if rid is None:return self.reply(400)
                if not isinstance(rid,(str,int)) or isinstance(rid,bool) or len(str(rid))>40:return self.reply(400)
                if method=='tools/list':result={'tools':TOOLS}
                elif method=='ping':result={}
                elif method=='tools/call':
                    try:
                        value=call_tool(business,session,rid,params.get('name'),params.get('arguments',{}))
                        result={'content':[{'type':'text','text':json.dumps(value,allow_nan=False)}]}
                    except Exception:
                        result={'isError':True,'content':[{'type':'text','text':'Office request rejected or could not finish. Read operation results before retrying.'}]}
                else:return self.reply(200,{'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'Method not found'}})
                return self.reply(200,{'jsonrpc':'2.0','id':rid,'result':result})
            except (ValueError,TypeError):return self.reply(400)
    return ThreadingHTTPServer((host,port),Handler)

def main():
    token=(ROOT/'state/worker-token').read_text().strip()
    print('Scoped office MCP listening on 172.18.0.1:11435; business writes require Gorilla approval.',flush=True)
    make_server('172.18.0.1',11435,GatewayClient(),token).serve_forever()

if __name__=='__main__':main()
