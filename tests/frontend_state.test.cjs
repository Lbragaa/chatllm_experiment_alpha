// Exercise the actual App event handlers with deterministic deferred requests.
// Browser rendering is deliberately not simulated by this small hook harness.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function appHarness(overrides = {}) {
  const source = fs.readFileSync(path.join(__dirname, '../frontend/src/App.jsx'), 'utf8');
  const start = source.indexOf('function App() {');
  const end = source.indexOf('  if (authLoading)', start);
  assert.ok(start >= 0 && end > start);
  const slots = [];
  let index = 0;
  const context = {
    AbortController,
    createMessageId: (() => { let id = 0; return () => ++id; })(),
    useState(initial) {
      const i = index++;
      if (!(i in slots)) slots[i] = initial;
      return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }];
    },
    useRef(initial) {
      const i = index++;
      if (!(i in slots)) slots[i] = { current: initial };
      return slots[i];
    },
    useMemo: fn => fn(),
    useEffect: () => {},
    localStorage: { removeItem() {} },
    createSession: async () => ({ id: 1 }),
    listSessions: async () => [],
    deleteSession: async () => {},
    logoutUser: async () => {},
    sendMessageStream: async () => {},
    ...overrides,
  };
  vm.createContext(context);
  vm.runInContext(source.slice(start, end) + `
    return { onSubmit, onStop, handleNewSession, handleSelectSession, handleLogout,
      handleAuth, setText, busy, submitting, token, activeSessionId, messages, error };
  }`, context);
  const render = () => { index = 0; return context.App(); };
  render().handleAuth('test-token', 'test@example.com');
  render().setText('Primeira mensagem');
  return render;
}

test('double submit while session creation is pending creates only one conversation', async () => {
  const creating = deferred();
  let calls = 0;
  const render = appHarness({ createSession: () => { calls++; return creating.promise; } });
  const app = render();
  const first = app.onSubmit({ preventDefault() {} });
  await app.onSubmit({ preventDefault() {} }); // same closure, before React can render
  await render().handleNewSession();
  assert.equal(calls, 1);
  assert.equal(render().busy, true);
  creating.resolve({ id: 8 });
  await first;
  assert.equal(render().busy, false);
});

test('creating/selecting another conversation is blocked until streaming completes', async () => {
  const streaming = deferred();
  let creates = 0;
  const render = appHarness({
    createSession: async () => { creates++; return { id: 3 }; },
    sendMessageStream: () => streaming.promise,
  });
  const pending = render().onSubmit({ preventDefault() {} });
  await new Promise(setImmediate);
  await render().handleNewSession();
  render().handleSelectSession(99);
  assert.equal(creates, 1);
  assert.equal(render().activeSessionId, 3);
  streaming.resolve();
  await pending;
  render().handleSelectSession(99);
  assert.equal(render().activeSessionId, 99);
});

test('cancelled request cannot clear busy state of a newer request', async () => {
  const first = deferred(), second = deferred();
  let calls = 0;
  const render = appHarness({ sendMessageStream: () => ++calls === 1 ? first.promise : second.promise });
  const pending1 = render().onSubmit({ preventDefault() {} });
  await new Promise(setImmediate);
  render().onStop();
  render().setText('Outra mensagem');
  const pending2 = render().onSubmit({ preventDefault() {} });
  first.resolve();
  await pending1;
  assert.equal(render().busy, true);
  second.resolve();
  await pending2;
  assert.equal(render().busy, false);
});

test('logout cancels streaming and ignores late deltas', async () => {
  const streaming = deferred();
  let streamArgs;
  const render = appHarness({ sendMessageStream: args => { streamArgs = args; return streaming.promise; } });
  const pending = render().onSubmit({ preventDefault() {} });
  await new Promise(setImmediate);
  await render().handleLogout();
  assert.equal(streamArgs.signal.aborted, true);
  streamArgs.onDelta('Late message');
  streaming.resolve();
  await pending;
  assert.equal(render().token, null);
  assert.equal(render().messages.length, 0);
});

test('failed server logout keeps authentication and reports failure', async () => {
  const render = appHarness({ logoutUser: async () => { throw new Error('Network unavailable'); } });
  await render().handleLogout();
  assert.equal(render().token, 'test-token');
  assert.equal(render().error, 'Network unavailable');
});

function apiHarness(body) {
  const source = fs.readFileSync(path.join(__dirname, '../frontend/src/api.js'), 'utf8');
  let request;
  const context = { window: { location: { origin: 'http://test' } }, TextDecoder,
    fetch: async (url, options) => { request = options; return new Response(body); } };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { context, request: () => request };
}

test('stream API sends Bearer token and requires the final persistence acknowledgement', async () => {
  const good = apiHarness('data: {"delta":"Hi"}\n\ndata: {"done":true,"session_id":1}\n\n');
  const deltas = [];
  await good.context.sendMessageStream({ token: 'abc', message: 'Hi', onDelta: d => deltas.push(d) });
  assert.equal(good.request().headers.Authorization, 'Bearer abc');
  assert.deepEqual(deltas, ['Hi']);
  const broken = apiHarness('data: {"delta":"Partial"}\n\n');
  await assert.rejects(broken.context.sendMessageStream({ onDelta() {} }), /salvamento/);
});
