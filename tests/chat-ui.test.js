import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldSend, nearConversationEnd } from '../src/chat-ui.js';

test('Enter sends, while multiline input and IME composition remain editable', () => {
  assert.equal(shouldSend({key:'Enter'}), true);
  assert.equal(shouldSend({key:'Enter',shiftKey:true}), false);
  assert.equal(shouldSend({key:'Enter',isComposing:true}), false);
  assert.equal(shouldSend({key:'Enter',keyCode:229}), false);
  assert.equal(shouldSend({key:'a'}), false);
});

test('only readers near the end follow a newly completed response', () => {
  assert.equal(nearConversationEnd(2000,1200,750), true);
  assert.equal(nearConversationEnd(2000,400,750), false);
});
