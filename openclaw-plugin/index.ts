// No package installation: loaded as a local plugin by the existing OpenClaw runtime.
export default {
  id: 'sandbox-gorilla',
  name: 'Sandbox Gorilla',
  register(api: any) {
    const base = api.pluginConfig?.gatewayUrl || 'http://host.openshell.internal:8091';
    const token = process.env.GORILLA_WORKER_TOKEN;
    if (!token) throw new Error('GORILLA_WORKER_TOKEN must be supplied to the worker runtime');
    const request = async (path: string, body?: unknown) => {
      const response = await fetch(base + path, {
        method: body ? 'POST' : 'GET',
        headers: body ? {'Content-Type':'application/json', Authorization:'Bearer ' + token} : {},
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(25000),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Guarded inbox request failed');
      return {content:[{type:'text',text:JSON.stringify(result)}]};
    };
    api.registerTool({
      name: 'gorilla_inbox_read',
      description: 'Read the assigned local inbox or archive. Returned business metadata is authoritative.',
      parameters: {type:'object',properties:{folder:{type:'string',enum:['inbox','archive']}},required:['folder'],additionalProperties:false},
      execute: async (_id: string, args: {folder:string}) => request('/api/messages?folder=' + encodeURIComponent(args.folder)),
    });
    api.registerTool({
      name: 'gorilla_inbox_act',
      description: 'Request an inbox operation for finance-001. Supply candidate choices DELETE, ARCHIVE, KEEP, FLAG. The business gateway selects and executes the permitted action and returns the actual receipt. You cannot override its selection.',
      parameters: {type:'object',properties:{message_id:{type:'string',enum:['finance-001']},proposed_choices:{type:'array',items:{type:'string',enum:['DELETE','ARCHIVE','KEEP','FLAG']},minItems:1,maxItems:4}},required:['message_id','proposed_choices'],additionalProperties:false},
      execute: async (id: string, args: {message_id:string,proposed_choices:string[]}) => request('/api/act', {
        request_id: 'openclaw-' + id,
        message_id: args.message_id,
        proposed_choices: args.proposed_choices,
        agent_activity: {agent:'OpenClaw',tool_call_id:id,tool:'gorilla_inbox_act'},
      }),
    });
    api.on('before_tool_call', (event: any) => {
      if (!['gorilla_inbox_read','gorilla_inbox_act','session_status'].includes(event.toolName)) {
        return {block:true,blockReason:'This email slice permits only scoped reads and guarded inbox actions.'};
      }
    });
  },
};
