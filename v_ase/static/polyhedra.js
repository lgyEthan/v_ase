// GUI and typed tools share the same explicit coordination rules.
const clone = value => JSON.parse(JSON.stringify(value));
const styleFields = new Set(['name','color','opacity','showFaces','showEdges','edgeColor','edgeRadius']);
const geometryRules = rules => (rules || []).map(rule => Object.fromEntries(Object.entries(rule).filter(([key])=>!styleFields.has(key))));
const signature = app => JSON.stringify([app.polyhedraRuntime.generation,geometryRules(app.state.display.polyhedraRules),app.renderer.atomsData?.symbols]);
const input = id => document.getElementById(`poly-${id}`);
const parsedNumbers = text => text.trim().split(/[\s,]+/).filter(Boolean).map(value => {
    if (!/^\d+$/.test(value)) throw new Error('Atom indices must be nonnegative integers separated by commas.');
    return Number(value);
});
function selector(kind,value) {
    if (value.trim()==='*') return {};
    return {[kind]:kind==='indices' ? parsedNumbers(value) : value.split(',').map(x=>x.trim()).filter(Boolean)};
}
function selectorText(value={}) {
    const entries=Object.entries(value);
    return entries.length ? [entries[0][0],entries[0][1].join(', ')] : ['elements','*'];
}
export function installPolyhedra(App) {
    const proto=App.prototype;
    proto.ensurePolyhedra = function () {
        if (this.polyhedraRuntime) return;
        this.polyhedraRuntime={generation:0,key:null,data:null,pending:null,timer:null,error:null,wasEnabled:false};
        this.renderer.onPolyhedraChange=kind=>{
            if (kind!=='display') {
                this.polyhedraRuntime.generation++;
                this.polyhedraRuntime.preview=kind==='preview';
                if(this.renderer.polyhedraSelectionGroup)this.renderer.polyhedraSelectionGroup.visible=false;
                this.renderer.polyhedraDataValid=false;
                this.renderer.polyhedraRendered=[];
            }
            this.schedulePolyhedra();
        };
        this.renderer.preparePolyhedraCapture=async()=>{
            for(let retry=0;retry<4;retry++) {
                await this.refreshPolyhedra();
                if(!this.state.display.showPolyhedra || this.polyhedraRuntime.key===signature(this))return;
            }
            throw new Error('The geometry keeps changing. Pause playback or finish the edit before rendering.');
        };
        for(const id of ['inherit','color','opacity','faces','edges','edge-color','edge-radius']) {
            input(id)?.addEventListener('change',()=>{
                if(id==='color')input('inherit').checked=false;
                const i=(this.state.display.polyhedraRules||[]).findIndex(r=>r.id===this.polyhedraDraft?.id);
                if(i<0)return;
                const opacity=Number(input('opacity').value),radius=Number(input('edge-radius').value);
                if(!Number.isFinite(opacity)||opacity<0||opacity>1||!Number.isFinite(radius)||radius<.001||radius>.3)return;
                const style={color:input('inherit').checked?null:input('color').value,opacity,
                    showFaces:input('faces').checked,showEdges:input('edges').checked,
                    edgeColor:input('edge-color').value,edgeRadius:radius};
                try {this.stylePolyhedra({ruleIds:[this.polyhedraDraft.id],...style},{syncEditor:false});}
                catch(error){this.toast(error.message,'error');this.syncPolyhedraControls(true);}
            });
        }
        input('fit')?.addEventListener('click',async()=>{
            try {await this.renderer.preparePolyhedraCapture();this.renderer.fitCameraToStructure();}
            catch(error){this.toast(error.message,'error');}
        });
        input('add')?.addEventListener('click',()=>{
            const ids=new Set((this.state.display.polyhedraRules||[]).map(r=>r.id));
            let n=1;while(ids.has(`coordination-${n}`))n++;
            this.polyhedraDraft={id:`coordination-${n}`,name:`Coordination ${n}`,centers:{elements:[]},
                ligands:{elements:['O']},maxDistance:2.5};
            this.syncPolyhedraControls(true);
        });
        input('rule')?.addEventListener('change',()=>{
            this.polyhedraDraft=clone((this.state.display.polyhedraRules||[]).find(r=>r.id===input('rule').value)||{});
            this.syncPolyhedraControls(true);
        });
        input('selected')?.addEventListener('click',()=>{
            const indices=this.selectedAtomIndices();
            if (!indices.length) {this.toast('Select the intended center atoms first.','warning');return;}
            input('center-kind').value='indices';input('centers').value=indices.join(', ');
        });
        input('apply')?.addEventListener('click',async()=>{
            try {
                const draft=this.polyhedraDraft || {};
                if (!draft.id) throw new Error('Choose Add rule first.');
                if (!input('centers').value.trim()) throw new Error('Enter a center element, label or index, or use selected atoms.');
                const rule={id:draft.id,name:input('name').value.trim(),enabled:input('rule-enabled').checked,
                    centers:selector(input('center-kind').value,input('centers').value),
                    ligands:selector(input('ligand-kind').value,input('ligands').value),
                    minDistance:Number(input('min').value),maxDistance:Number(input('max').value),
                    minCoordination:Number(input('cn-min').value),maxCoordination:Number(input('cn-max').value),
                    periodic:input('periodic').checked,planar:input('planar').checked,
                    showFaces:input('faces').checked,showEdges:input('edges').checked,
                    color:input('inherit').checked ? null : input('color').value,
                    opacity:Number(input('opacity').value),edgeColor:input('edge-color').value,
                    edgeRadius:Number(input('edge-radius').value)};
                const exact=input('exact').value.trim();
                if (exact) {
                    if (rule.centers.indices?.length!==1) throw new Error('Exact vertices require one center chosen by atom index.');
                    const vertices=exact.split('\n').filter(x=>x.trim()).map(line=>{
                        const values=line.trim().split(/[\s,]+/);
                        if (![1,4].includes(values.length)||values.some(x=>! /^-?\d+$/.test(x))) throw new Error('Each exact vertex line is: atom_index shift_x shift_y shift_z.');
                        return {index:Number(values[0]),cellOffset:values.length===4 ? values.slice(1).map(Number) : [0,0,0]};
                    });
                    rule.explicit=[{center:rule.centers.indices[0],vertices}];
                }
                const rules=clone(this.state.display.polyhedraRules||[]);
                const i=rules.findIndex(r=>r.id===rule.id);if(i<0)rules.push(rule);else rules[i]=rule;
                await this.configurePolyhedra({rules,enabled:true});
                this.polyhedraDraft=clone(rule);this.syncPolyhedraControls(true);
            } catch(error) {this.toast(error.message,'error');}
        });
        input('remove')?.addEventListener('click',async()=>{
            const id=this.polyhedraDraft?.id;
            if(!id)return;
            try {await this.configurePolyhedra({rules:(this.state.display.polyhedraRules||[]).filter(r=>r.id!==id)});
                this.polyhedraDraft=null;this.syncPolyhedraControls(true);
            } catch(error){this.toast(error.message,'error');}
        });
        for (const [name,key] of [['enabled','enabled'],['atom-mode','atomMode'],['respect','respectVisibility']]) {
            input(name)?.addEventListener('change',async()=>{
                try {await this.configurePolyhedra({[key]:name==='atom-mode'?input(name).value:input(name).checked});}
                catch(error){this.toast(error.message,'error');this.syncPolyhedraControls(true);}
            });
        }
        this.schedulePolyhedra();
    };
    proto.syncPolyhedraControls = function (force=false) {
        if (!input('rule')) return;
        const d=this.state.display;
        input('enabled').checked=Boolean(d.showPolyhedra);
        input('atom-mode').value=d.polyhedraAtomMode||'all';
        input('respect').checked=d.polyhedraRespectVisibility!==false;
        if (!force && document.activeElement?.closest('[data-panel="polyhedra"]')) return;
        const rules=d.polyhedraRules||[];
        const draft=this.polyhedraDraft || rules[0] || null;
        this.polyhedraDraft=draft ? clone(draft):null;
        const listed=[...rules];if(draft&&!listed.some(r=>r.id===draft.id))listed.push(draft);
        input('rule').replaceChildren(...listed.map(r=>new Option(r.name||r.id,r.id)));
        if(draft) input('rule').value=draft.id;
        input('editor').hidden=!draft;
        if(!draft)return;
        input('name').value=draft.name||draft.id;
        const center=selectorText(draft.centers), ligand=selectorText(draft.ligands);
        input('center-kind').value=center[0];input('centers').value=center[1];
        input('ligand-kind').value=ligand[0];input('ligands').value=ligand[1];
        for(const [id,key,fallback] of [['min','minDistance',0],['max','maxDistance',2.5],['cn-min','minCoordination',3],['cn-max','maxCoordination',32],['opacity','opacity',.28],['edge-radius','edgeRadius',.025]])input(id).value=draft[key]??fallback;
        for(const [id,key] of [['periodic','periodic'],['planar','planar'],['faces','showFaces'],['edges','showEdges'],['rule-enabled','enabled']])input(id).checked=draft[key]!==false;
        input('inherit').checked=!draft.color;input('color').value=draft.color||'#4f8bbc';
        input('edge-color').value=draft.edgeColor||'#374151';
        input('exact').value=draft.explicit?.length===1 ? draft.explicit[0].vertices.map(v=>[v.index,...(v.cellOffset||[0,0,0])].join(' ')).join('\n'):'';
        // Preserve complex MCP-authored selectors/explicit groups when viewing.
        const complex=Object.keys(draft.centers||{}).length>1||Object.keys(draft.ligands||{}).length>1||(draft.explicit?.length||0)>1;
        input('apply').disabled=complex;
        input('complex').hidden=!complex;
    };
    proto.schedulePolyhedra = function () {
        const runtime=this.polyhedraRuntime;
        if(!runtime)return;
        if(!this.state.display.showPolyhedra){
            clearTimeout(runtime.timer);runtime.timer=null;
            if(this.renderer.polyhedraGroup)this.renderer.polyhedraGroup.visible=false;
            if(runtime.wasEnabled)this.renderer.applyAtomVisibility();
            runtime.wasEnabled=false;return;
        }
        runtime.wasEnabled=true;
        if(runtime.key===signature(this)&&runtime.data){
            this.renderer.setPolyhedraData(runtime.data);return;
        }
        if(this.renderer.polyhedraGroup)this.renderer.polyhedraGroup.visible=false;
        if(runtime.timer || runtime.pending)return;
        runtime.timer=setTimeout(()=>{
            runtime.timer=null;
            this.refreshPolyhedra().catch(error=>{if(input('status'))input('status').textContent=error.message;});
        },45);
    };
    proto.refreshPolyhedra = async function () {
        this.ensurePolyhedra();
        const runtime=this.polyhedraRuntime;
        clearTimeout(runtime.timer);runtime.timer=null;
        if(!this.state.display.showPolyhedra)return null;
        if(runtime.pending){await runtime.pending;return this.refreshPolyhedra();}
        const key=signature(this);
        if(runtime.key===key&&runtime.data){this.renderer.setPolyhedraData(runtime.data);return runtime.data;}
        const atoms=this.renderer.atomsData;
        if(!atoms)return null;
        runtime.error=null;
        if(input('status'))input('status').textContent='Calculating coordination geometry…';
        const pending=this.api.jsonPost('/api/analysis/polyhedra/{session_id}',{
            frame_index:Number(this.state.atoms?.metadata?.current_frame||0),
            positions:runtime.preview ? atoms.positions.map((_,i)=>this.renderer.getAtomPosition(i).toArray()) : atoms.positions,
            cell:atoms.cell,pbc:atoms.pbc,labels:atoms.symbols,rules:this.state.display.polyhedraRules||[]
        });
        runtime.pending=pending;
        try {
            const data=await pending;
            if(key===signature(this)&&this.state.display.showPolyhedra){
                runtime.data=data;runtime.key=key;this.renderer.setPolyhedraData(data);
                this.state.polyhedraSummary={polyhedronCount:data.polyhedronCount,centerCount:data.centerCount,
                    vertexCount:data.vertexCount,frame:data.frame,fingerprint:data.fingerprint,
                    diagnostics:data.diagnostics.slice(0,40)};
                if(input('status'))input('status').textContent=`${data.polyhedronCount} polyhedra · ${data.centerCount} centers · ${data.diagnostics.length} omitted. ${data.diagnostics[0]?.status||''}`;
            }
            return data;
        } catch(error){runtime.error=error.message;throw error;}
        finally{runtime.pending=null;if(key!==signature(this))this.schedulePolyhedra();}
    };
    proto.stylePolyhedra = function (options={}, {syncEditor=true}={}) {
        this.ensurePolyhedra();
        const ids=new Set(options.ruleIds || []);
        const rules=this.state.display.polyhedraRules || [];
        if(!ids.size || [...ids].some(id=>!rules.some(r=>r.id===id)))throw new Error('Choose existing polyhedra rule IDs.');
        const patch=Object.fromEntries(Object.entries(options).filter(([key,value])=>styleFields.has(key) && key!=='name' && value!==undefined));
        const nextRules=rules.map(rule=>ids.has(rule.id)?{...rule,...patch}:rule);
        this.renderer.validatePolyhedraDisplay(this.renderer.polyhedraData,{...this.state.display,polyhedraRules:nextRules});
        this.state.display.polyhedraRules=nextRules;
        if(ids.has(this.polyhedraDraft?.id))Object.assign(this.polyhedraDraft,patch);
        this.renderer.setDisplayOptions(this.state.display);
        this.scheduleVisualHistoryCommit('polyhedra-appearance');if(syncEditor)this.syncPolyhedraControls(true);
    };
    proto.configurePolyhedra = async function (options={}) {
        this.ensurePolyhedra();
        const d=this.state.display;
        if(options.enabled===false && options.rules===undefined) {
            d.showPolyhedra=false;this.polyhedraRuntime.error=null;
            this.renderer.setDisplayOptions(d);this.renderer.applyAtomVisibility();
            this.scheduleVisualHistoryCommit('configure-polyhedra');this.syncPolyhedraControls(true);return null;
        }
        const next={...d};
        if(options.rules!==undefined)next.polyhedraRules=clone(options.rules);
        if(options.enabled!==undefined)next.showPolyhedra=options.enabled;
        if(options.atomMode!==undefined)next.polyhedraAtomMode=options.atomMode;
        if(options.respectVisibility!==undefined)next.polyhedraRespectVisibility=options.respectVisibility;
        const generation=this.polyhedraRuntime.generation;
        const result=await this.api.jsonPost('/api/analysis/polyhedra/{session_id}',{
            frame_index:Number(this.state.atoms?.metadata?.current_frame||0),
            positions:this.renderer.atomsData.positions,cell:this.renderer.atomsData.cell,pbc:this.renderer.atomsData.pbc,
            labels:this.renderer.atomsData.symbols,rules:next.polyhedraRules||[]
        });
        if(generation!==this.polyhedraRuntime.generation)throw new Error('The structure changed during polyhedra setup. Apply again to the current frame.');
        this.renderer.validatePolyhedraDisplay(result,next);
        Object.assign(d,next);
        if(options.rules!==undefined)this.polyhedraDraft=clone(next.polyhedraRules.find(r=>r.id===this.polyhedraDraft?.id)||next.polyhedraRules[0]||null);
        this.polyhedraRuntime.data=result;this.polyhedraRuntime.key=signature(this);this.polyhedraRuntime.error=null;
        this.renderer.setDisplayOptions(d);this.renderer.setPolyhedraData(result);
        this.state.polyhedraSummary={polyhedronCount:result.polyhedronCount,centerCount:result.centerCount,
            vertexCount:result.vertexCount,frame:result.frame,fingerprint:result.fingerprint,diagnostics:result.diagnostics.slice(0,40)};
        this.scheduleVisualHistoryCommit('configure-polyhedra');
        this.syncPolyhedraControls(true);
        if(input('status'))input('status').textContent=`${result.polyhedronCount} polyhedra · ${result.diagnostics.length} omitted. ${result.diagnostics[0]?.status||''}`;
        return result;
    };
    const ui=proto.updateUI;
    proto.updateUI=function(...args){const result=ui.apply(this,args);this.ensurePolyhedra();this.syncPolyhedraControls();return result;};
    const frame=proto.completeTrajectoryFrameUpdate;
    proto.completeTrajectoryFrameUpdate=async function(...args) {
        const result=await frame.apply(this,args);
        if(this.state.display.showPolyhedra)await this.refreshPolyhedra();
        return result;
    };
    const preview=proto.applyTransformPreview;
    proto.applyTransformPreview=function(...args) {
        const result=preview.apply(this,args);
        if(this.state.display.showPolyhedra && (!this.state.transformSubject || this.state.transformSubject==='atoms')) {
            this.renderer.onPolyhedraChange?.('preview');
        }
        return result;
    };
}
