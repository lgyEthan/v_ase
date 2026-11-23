'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');
const { withDeadline } = require('./smoke-support.cjs');

// Only installed by the disposable desktop smoke test. Keep event provenance
// when a visual assertion fails so a retry cannot hide an unexpected edit.
module.exports = async function installSmokeDiagnostics({ js, active, appRef, win, output }) {
    const nativeInputs = [];
    const sentInputs = [];
    const send = win.webContents.sendInputEvent.bind(win.webContents);
    win.webContents.sendInputEvent = input => {
        if(input.type.startsWith('key'))sentInputs.push({at:Date.now(),...input});
        return send(input);
    };
    win.webContents.on('before-input-event', (_event, input) => {
        const safe = /^(Delete|Backspace|Escape|Tab|Enter|Arrow\w+|Space)$/i.test(input.code || input.key || '');
        nativeInputs.push({ at: Date.now(), type: input.type, key: safe ? input.key : '[text]',
            code: safe ? input.code : '[text]', control: input.control, meta: input.meta, isAutoRepeat: input.isAutoRepeat });
        if (nativeInputs.length > 300) nativeInputs.shift();
    });
    await js(`(() => {
        const f=${active}, a=${appRef};
        const trace=window.__smokeDiagnostics={stage:'installed',events:[],mutations:[]};
        const snapshot=()=>({at:Date.now(),stage:trace.stage,focus:f.document.activeElement?.id || f.document.activeElement?.tagName,
            count:a.state.atoms?.positions?.length,selected:[...a.state.selected],
            constraints:a.state.atoms?.constraints,
            guides:a.renderer.constraintGuideGroup.children.map(g=>({kind:g.userData.kind,index:g.userData.constraintGuideFor,visible:g.visible}))});
        for(const type of ['keydown','keyup','click','pointerdown','pointerup']) {
            f.document.addEventListener(type,e=>{
                const safe=/^(Delete|Backspace|Escape|Tab|Enter|Arrow\w+|Space)$/i.test(e.code || e.key || '');
                trace.events.push({...snapshot(),type,key:safe?e.key:'[text]',code:safe?e.code:'[text]',trusted:e.isTrusted,
                    target:e.target?.id || e.target?.tagName,field:e.target?.dataset?.appearanceField,
                    x:e.clientX,y:e.clientY,button:e.button});
                if(trace.events.length>300)trace.events.shift();
            },true);
        }
        for(const [owner,name] of [[a,'deleteSelection'],[a.api,'deleteAtoms']]) {
            const original=owner[name];
            owner[name]=function(...args){
                trace.mutations.push({...snapshot(),method:name,args,stack:new Error().stack});
                return original.apply(this,args);
            };
        }
        trace.snapshot=snapshot;
    })()`);
    let lastSnapshot;
    return {
        async stage(name) {
            lastSnapshot = await js(`(()=>{const t=window.__smokeDiagnostics;t.stage=${JSON.stringify(name)};return t.snapshot();})()`);
        },
        async save(name = 'input-trace.json') {
            const renderer = await withDeadline(js(`(()=>{const t=window.__smokeDiagnostics;return {...t,snapshot:t.snapshot()};})()`),
                'diagnostic state', 3000).catch(error => ({ error: error.message, lastSnapshot }));
            await fs.writeFile(path.join(output, name), JSON.stringify({ sentInputs, nativeInputs, renderer }, null, 2));
        },
    };
};
