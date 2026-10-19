import test from 'node:test';
import assert from 'node:assert/strict';

test('database restore wins over browser cache; saves use server revisions and surface conflicts', async () => {
  const events = [];
  globalThis.location = {search:''};
  globalThis.window = {dispatchEvent:event => events.push(event)};
  globalThis.CustomEvent = class {constructor(type,options){this.type=type;this.detail=options.detail;}};
  globalThis.document = {addEventListener(){}};
  let cache = JSON.stringify({flow:{opening:999}});
  globalThis.localStorage = {getItem:()=>cache,setItem:(_,value)=>{cache=value;}};
  const requests = [];
  let conflict = false;
  globalThis.fetch = async (_,options) => {
    if (options) requests.push(JSON.parse(options.body));
    return {ok:!conflict,json:async()=>conflict ? {detail:'Workspace updated in another browser.'} : {
      revision:options ? 8 : 7, workspace:{flow:{opening:128000}},
      financial:{version:2,opening:128000},business:{company:{name:'StarSail Exports'}},
    }};
  };
  const storage=await import('../src/storage.js');
  assert.equal((await storage.loadWorkspace()).flow.opening,128000);
  assert.equal(storage.storedBusinessRecords().company.name,'StarSail Exports');
  storage.saveWorkspace({flow:{opening:128000},state:{lang:'en'}});
  await storage.flushWorkspace();
  assert.equal(requests[0].revision,7);
  assert.equal(events.at(-1).detail.status,'saved');
  assert.equal(JSON.parse(cache).state.lang,'en');
  conflict=true;
  storage.saveWorkspace({flow:{opening:128000},state:{lang:'zh'}});
  await storage.flushWorkspace();
  assert.equal(requests[1].revision,8);
  assert.equal(events.at(-1).detail.status,'error');
  assert.match(events.at(-1).detail.detail,/another browser/);
});
