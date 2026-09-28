import { normalizeWater } from './water_geometry.js';
const field=id=>document.getElementById(`water-${id}`);
export function installWaterUI(App){
    const p=App.prototype;
    p.syncWaterControls=function(){
        const c=normalizeWater(this.state.display.waterSurface);
        for(const key of ['enabled','hideMolecules','lighting'])if(field(key))field(key).checked=c[key];
        for(const key of ['color','opacity','roughness','smoothing','level','spacing','ohCutoff','source']){
            if(field(key)&&document.activeElement!==field(key))field(key).value=c[key];
        }
        if(field('selected'))field('selected').hidden=c.source!=='selected';
        if(field('scope'))field('scope').textContent=c.source==='selected'?`${c.indices.length} captured oxygen indices. Selection changes do not retarget the surface.`:'Detect O with exactly two nearest H inside the chemical cutoff.';
        if(field('roughness'))field('roughness').disabled=!c.lighting||this.renderer.atomDisplayMode()==='2d';
    };
    p.ensureWaterUI=function(){
        if(this.waterUIReady)return;this.waterUIReady=true;
        this.renderer.onWaterSurfaceChange=report=>{
            const status=field('status');if(!status)return;
            status.textContent=report.error||(!this.state.display.waterSurface?.enabled?'Water surface is off.':
                `${report.molecules||0} H₂O molecules · ${Math.round(report.triangles||0).toLocaleString()} triangles · ${Number(report.buildMs||0).toFixed(0)} ms. `+
                (!report.molecules?'No H₂O found. Check the source and O–H cutoff. ':!report.triangles?'No envelope at this threshold. Lower it or increase smoothing. ':'')+
                (report.spacing>Number(this.state.display.waterSurface?.spacing||.65)*1.01?`Grid adapted to ${report.spacing.toFixed(2)} Å to stay within the preview budget.`:''));
            status.dataset.error=String(Boolean(report.error));
        };
        const change=(key,value)=>{
            try{
                const next=normalizeWater({...this.state.display.waterSurface,[key]:value});
                if(field('status'))field('status').textContent='Updating water surface…';
                this.state.display.waterSurface=next;
                this.renderer.setDisplayOptions({waterSurface:next});
                this.scheduleVisualHistoryCommit('water-surface');
                this.syncWaterControls();this.renderSceneNavigatorObjects();
            }catch(error){this.toast(error.message,'error');this.syncWaterControls();}
        };
        for(const key of ['enabled','hideMolecules','lighting'])field(key)?.addEventListener('change',()=>change(key,field(key).checked));
        for(const key of ['color','opacity','roughness','smoothing','level','spacing','ohCutoff','source']){
            field(key)?.addEventListener(key==='color'?'input':'change',()=>change(key,['color','source'].includes(key)?field(key).value:Number(field(key).value)));
        }
        field('selected')?.addEventListener('click',()=>{
            const symbols=this.state.atoms?.chemical_symbols||[];
            const indices=this.selectedAtomIndices().filter(i=>symbols[i]==='O');
            if(!indices.length){this.toast('Select at least one water oxygen first.','warning');return;}
            change('indices',indices);
        });
        field('fit')?.addEventListener('click',()=>{this.renderer.refreshWaterSurface();this.renderer.fitCameraToStructure();});
    };
    const update=p.updateUI;
    p.updateUI=function(...args){const result=update.apply(this,args);this.ensureWaterUI();this.syncWaterControls();return result;};
    const reconcile=p.reconcileDesignDisplay;
    p.reconcileDesignDisplay=function(...args){const result=reconcile.apply(this,args);result.waterSurface=normalizeWater(result.waterSurface);return result;};
}
