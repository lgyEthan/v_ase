'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const isolate = require('../smoke-input.cjs');

function fixture(options) {
    const contents = new EventEmitter();
    contents.sendInputEvent = () => {};
    const guard = isolate(contents, options);
    const receive = input => {
        const event = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
        contents.emit('before-input-event', event, input);
        return event.defaultPrevented;
    };
    const mouse = input => {
        const event = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
        contents.emit('before-mouse-event', event, input);
        return event.defaultPrevented;
    };
    return { contents, guard, receive, mouse };
}
test('unplanned Delete is blocked, but an explicitly tested Delete reaches the editor', () => {
    const { contents, guard, receive } = fixture();
    const input = { type: 'keyDown', code: 'Delete' };
    assert.equal(receive(input), true);
    contents.sendInputEvent({ type: 'keyDown', keyCode: 'Delete' });
    assert.equal(receive(input), false);
    guard.assertDrained();
    assert.deepEqual(guard.snapshot().received.map(x => x.allowed), [false, true]);
});
test('a lost key or wrong modifier fails instead of being silently skipped', () => {
    const { contents, guard, receive } = fixture();
    contents.sendInputEvent({ type: 'keyDown', keyCode: 'O', modifiers: ['meta'] });
    assert.equal(receive({ type: 'keyDown', code: 'KeyO' }), true);
    assert.throws(guard.assertDrained, /Every test key/);
    assert.equal(receive({ type: 'keyDown', code: 'KeyO', meta: true }), false);
    guard.assertDrained();
});
test('native navigation, digits and key releases retain their full route', () => {
    const { contents, guard, receive } = fixture();
    for (const [keyCode, code] of [['Right', 'ArrowRight'], ['2', 'Digit2'], ['A', 'KeyA'], ['Tab', 'Tab']]) {
        for (const type of ['keyDown', 'keyUp']) {
            contents.sendInputEvent({ type, keyCode });
            assert.equal(receive({ type, code }), false);
        }
    }
    guard.assertDrained();
    assert.equal(guard.snapshot().sent.length, 8);
});
test('unplanned clicks cannot change focus; tested mouse presses and releases remain mandatory', () => {
    const { contents, guard, mouse } = fixture();
    const down = {type:'mouseDown',x:20,y:30,button:'left'};
    const up = {...down,type:'mouseUp'};
    assert.equal(mouse(down),true);
    contents.sendInputEvent(down);
    assert.equal(mouse({...down,x:21}),true);
    assert.throws(guard.assertDrained,/Every test mouse/);
    assert.equal(mouse(down),false);
    contents.sendInputEvent(up);
    assert.equal(mouse(up),false);
    guard.assertDrained();
});
test('coalesced mouse moves do not discard a missing button event', () => {
    const { contents, guard, mouse } = fixture();
    for(const x of [1,2,3])contents.sendInputEvent({type:'mouseMove',x,y:10});
    assert.equal(mouse({type:'mouseMove',x:3,y:10}),false);
    contents.sendInputEvent({type:'mouseDown',x:3,y:10,button:'left'});
    contents.sendInputEvent({type:'mouseUp',x:3,y:10,button:'left'});
    assert.equal(mouse({type:'mouseUp',x:3,y:10,button:'left'}),true);
    assert.throws(guard.assertDrained,/Every test mouse/);
});
test('macOS consumed Command releases never block the next mandatory command', () => {
    const { contents, guard, receive } = fixture({platform:'darwin'});
    for(const keyCode of ['O','O']){
        contents.sendInputEvent({type:'keyDown',keyCode,modifiers:['meta']});
        assert.equal(receive({type:'keyDown',code:'KeyO',meta:true}),false);
        contents.sendInputEvent({type:'keyUp',keyCode,modifiers:['meta']});
    }
    guard.assertDrained();
    assert.equal(receive({type:'keyUp',code:'KeyO',meta:true}),false);
});
