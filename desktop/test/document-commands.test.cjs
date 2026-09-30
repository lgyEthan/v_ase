'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../../v_ase/static/editor_commands.js'),'utf8');
const modulePromise = import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const nativeSource = fs.readFileSync(path.join(__dirname,'../main.cjs'),'utf8');
const handler = nativeSource.slice(nativeSource.indexOf('function inputCommand('),nativeSource.indexOf('\nasync function start()'));

test('native and DOM document chords match on every supported platform', async () => {
    const m = await modulePromise;
    for (const platform of ['darwin','win32','linux']) {
        const apple = platform === 'darwin';
        const context = vm.createContext({process:{platform},commands:{...m.EDITOR_COMMANDS,...m.DOCUMENT_COMMANDS}});
        vm.runInContext(handler, context);
        for (const [id, command] of Object.entries(m.DOCUMENT_COMMANDS)) {
            const input = {type:'keyDown',code:command.code,meta:apple,control:!apple,
                shift:false,alt:command.alt,isComposing:false};
            const native = value => {context.input=value;return vm.runInContext('inputCommand(input)',context)||null;};
            const dom = value => m.documentCommandIdForEvent({code:value.code,
                metaKey:value.meta,ctrlKey:value.control,shiftKey:value.shift,
                altKey:value.alt,isComposing:value.isComposing},apple?'mac':'windows');
            assert.equal(native(input),id); assert.equal(dom(input),id);
            for (const wrong of [{...input,meta:!apple,control:apple},
                {...input,meta:true,control:true},{...input,shift:true},
                {...input,alt:!command.alt},{...input,isComposing:true}]) {
                assert.notEqual(native(wrong),id); assert.notEqual(dom(wrong),id);
            }
            assert.equal(native({...input,type:'keyUp'}),null);
            assert.equal(m.viewportNavigationForEvent({code:command.code,
                metaKey:apple,ctrlKey:!apple,altKey:command.alt}),null);
        }
    }
});
