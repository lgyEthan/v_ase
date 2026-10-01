'use strict';
// Run in both development and sealed platform binaries. State assertions alone
// cannot catch a driver, clipping, visibility or DPI regression.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const waitForVisualFrame = require('./visual-frame.cjs');
module.exports = async function visualSmoke({js, active, appRef, win, output, wait}) {
    const prior = await js(`({settings:${appRef}.designSettingsSnapshot(),vizOnly:${appRef}.state.vizOnly})`);
    await js(`(async()=>{const a=${appRef};await a.aiApply({mode:'edit'});
        a.setAtomsData(await a.api.updateConstraints([0],{fix_atoms:true}));
        a.setAtomsData(await a.api.updateConstraints([1],{directional_kind:'fixed_line',vector:[0,1,0]}));
        a.setAtomsData(await a.api.updateConstraints([2],{directional_kind:'fixed_plane',vector:[0,0,1]}));
        a.applyDesignSettings({display:{showOverlays:false,showConstraints:true,showCell:false,showAxes:false,showGrid:false}});
        a.applyCameraSettings({position:[0,0,10],target:[0,0,0],up:[0,1,0],projection:'orthographic',ortho_scale:4});
        a.clearAtomSelection();a.updateSelectionVisuals();a.updateUI();})()`);
    const captureImage=async name=>{
        await js(`new Promise(r=>${active}.requestAnimationFrame(()=>${active}.requestAnimationFrame(r)))`);
        const rect=await js(`(()=>{const w=window.__V_ASE_WORKSPACE__,tab=w.tabs.get(w.activeSessionId),r=${appRef}.renderer.domElement.getBoundingClientRect(),p=tab.pane.getBoundingClientRect();return {x:Math.round(r.x+p.x),y:Math.round(r.y+p.y),width:Math.floor(r.width),height:Math.floor(r.height)};})()`);
        const image=await win.webContents.capturePage(rect);
        await fs.writeFile(path.join(output,name+'.png'),image.toPNG());
        return image;
    };
    const capture=async name=>(await captureImage(name)).toBitmap();
    const yellow=buffer=>{let count=0;for(let i=0;i<buffer.length;i+=4){const b=buffer[i],g=buffer[i+1],r=buffer[i+2];if(r>160&&g>100&&b<90&&r-b>90)count++;}return count;};
    const planeRing=async()=>js(`(()=>{const r=${appRef}.renderer;
        const g=r.constraintGuideGroup.children.find(g=>g.userData.kind==='fixed_plane'&&g.userData.constraintGuideFor===2);
        const mesh=g?.children.find(c=>c.userData.fixedPlanePerimeter);if(!mesh)return null;
        const a=mesh.geometry.attributes.position;let inner=Infinity,outer=0;
        for(let i=0;i<a.count;i++){const radius=Math.hypot(a.getX(i),a.getY(i));inner=Math.min(inner,radius);outer=Math.max(outer,radius);}
        return {inner,outer,opacity:r.constraintMaterials.planeFace.opacity,visible:g.visible};})()`);
    const expectRing=(ring,selected)=>{
        assert.ok(ring?.visible, 'FixedPlane ring is missing');
        assert.ok(Math.abs(ring.inner-(selected?1.18:1))<1e-5,JSON.stringify(ring));
        assert.ok(Math.abs(ring.outer-(selected?1.66:1.48))<1e-5,JSON.stringify(ring));
        assert.ok(Math.abs(ring.opacity-.3)<1e-8,JSON.stringify(ring));
    };
    const pixelChecks=[];
    for(const mode of ['3d','2d']) {
        await js(`(()=>{const a=${appRef};a.applyDesignSettings({display:{atomDisplayMode:'${mode}',showConstraints:true}});a.clearAtomSelection();a.updateSelectionVisuals();})()`);
        const before=await capture(`selection-${mode}-before`);
        const unselectedRing=await planeRing();expectRing(unselectedRing,false);
        const bounds=await js(`(()=>{const w=window.__V_ASE_WORKSPACE__,p=w.tabs.get(w.activeSessionId).pane.getBoundingClientRect(),r=${appRef}.renderer;
            const v=[...r.atomMeshByIndex.values()].map(a=>r.projectWorldToClient(a.position));return {x1:Math.round(p.x+Math.min(...v.map(v=>v.x))-28),x2:Math.round(p.x+Math.max(...v.map(v=>v.x))+28),y1:Math.round(p.y+Math.min(...v.map(v=>v.y))-28),y2:Math.round(p.y+Math.max(...v.map(v=>v.y))+28)};})()`);
        win.show();win.focus();win.webContents.focus();
        win.webContents.sendInputEvent({type:'mouseDown',x:bounds.x1,y:bounds.y1,button:'left',clickCount:1});
        for(let i=1;i<=8;i++)win.webContents.sendInputEvent({type:'mouseMove',x:Math.round(bounds.x1+(bounds.x2-bounds.x1)*i/8),y:Math.round(bounds.y1+(bounds.y2-bounds.y1)*i/8),button:'left',buttons:['left']});
        win.webContents.sendInputEvent({type:'mouseUp',x:bounds.x2,y:bounds.y2,button:'left',clickCount:1});
        await wait(`${appRef}.state.selected.size===3`);
        const selected=await waitForVisualFrame(
            () => capture(`selection-${mode}-drag`),
            bitmap => yellow(bitmap)-yellow(before)>100);
        const selectedRing=await planeRing();expectRing(selectedRing,true);
        const outlinePixels=yellow(selected)-yellow(before);
        assert.ok(outlinePixels>100,`Invisible ${mode} drag selection: ${outlinePixels} yellow pixels`);
        await js(`(()=>{const a=${appRef};a.clearAtomSelection();a.updateSelectionVisuals();a.updateUI();a.openEditorRoute('appearance');const b=${active}.document.querySelector('[data-appearance-field="select"][data-atom-label="H"]');b.click();})()`);
        await wait(`${appRef}.state.selected.size===2`);
        const panelSelected=await waitForVisualFrame(
            () => capture(`selection-${mode}-panel`),
            bitmap => yellow(bitmap)-yellow(before)>50);
        assert.ok(yellow(panelSelected)-yellow(before)>50,`Invisible ${mode} panel selection`);
        await js(`(()=>{const a=${appRef};a.clearAtomSelection();a.updateSelectionVisuals();a.updateUI();})()`);
        const constraints=await capture(`constraints-${mode}-visible`);
        expectRing(await planeRing(),false);
        await js(`(()=>{const a=${appRef};a.applyDesignSettings({display:{showConstraints:false}});})()`);
        const hidden=await capture(`constraints-${mode}-hidden`);
        let changed=0;for(let i=0;i<constraints.length;i+=4)if(Math.abs(constraints[i]-hidden[i])+Math.abs(constraints[i+1]-hidden[i+1])+Math.abs(constraints[i+2]-hidden[i+2])>20)changed++;
        assert.ok(changed>100,`Invisible ${mode} constraints: ${changed} changed pixels`);
        pixelChecks.push({mode,outlinePixels,constraintPixels:changed,unselectedRing,selectedRing});
    }
    const axisChecks=[];
    for(const mode of ['3d','2d']) {
        const state=await js(`(()=>{const a=${appRef},r=a.renderer;
            a.applyDesignSettings({display:{atomDisplayMode:'${mode}',showAxes:true,showGrid:false,
                showConstraints:false,viewportBackground:'white'}});
            a.setInspectorCollapsed(true);a.clearAtomSelection();a.updateSelectionVisuals();
            a.applyCameraSettings({position:[0,-6.4696504838,29.2940885268],target:[0,0,0],
                up:[0,.9764696176,.2156550161],projection:'orthographic',ortho_scale:40,near:1,far:1000});
            const point=r.camera.position.clone().set(0,0,60),p=r.projectWorldToClient(point),rect=r.domElement.getBoundingClientRect();
            return {camera:a.currentCameraForExport(),x:p.x-rect.left,y:p.y-rect.top,
                width:rect.width,height:rect.height};})()`);
        const shown=await captureImage(`canvas-axis-${mode}-visible`);
        const scale=shown.getSize().width/state.width;
        const crop={x:Math.round((state.x-2)*scale),y:Math.round((state.y-2)*scale),
            width:Math.max(5,Math.round(5*scale)),height:Math.max(5,Math.round(5*scale))};
        const visible=shown.crop(crop).toBitmap();
        await js(`(()=>{const r=${appRef}.renderer;r.axesHelper.children[2].visible=false;r.renderNow();})()`);
        const hidden=await waitForVisualFrame(
            ()=>captureImage(`canvas-axis-${mode}-hidden`),
            image=>!image.crop(crop).toBitmap().equals(visible));
        const absent=hidden.crop(crop).toBitmap();
        let bluePixels=0;
        for(let i=0;i<visible.length;i+=4)
            if(visible[i]>visible[i+2]+20&&visible[i]-absent[i]>15)bluePixels++;
        assert.ok(bluePixels>=3,`Clipped ${mode} canvas Z shaft: ${bluePixels} blue pixels`);
        assert.deepEqual(await js(`${appRef}.currentCameraForExport()`),state.camera,
            'Canvas axis rendering must preserve stored camera settings');
        await js(`(()=>{const r=${appRef}.renderer;r.axesHelper.children[2].visible=true;r.renderNow();})()`);
        axisChecks.push({mode,bluePixels,captureScale:scale,cameraPreserved:true});
    }
    const layoutChecks=[];
    for(const [width,height,zoom] of [[1280,720,1],[1024,600,1.25],[1024,768,1.5]]) {
        win.setContentSize(width,height);win.webContents.setZoomFactor(zoom);
        await js(`new Promise(r=>${active}.requestAnimationFrame(()=>${active}.requestAnimationFrame(r)))`);
        const result=await js(`(async()=>{const a=${appRef},d=${active}.document;a.openEditorRoute('add-atoms');d.getElementById('add-atoms-tab-batch').click();d.getElementById('add-atoms-content-molecules').click();
          // Route navigation queues its own scroll. Let it finish before scrolling the action.
          await new Promise(r=>${active}.requestAnimationFrame(()=>${active}.requestAnimationFrame(r)));
          const el=d.getElementById('btn-add-atoms-scatter');el.scrollIntoView({block:'center'});
          await new Promise(r=>${active}.requestAnimationFrame(()=>${active}.requestAnimationFrame(r)));
          const scroll=[];for(let p=el.parentElement;p;p=p.parentElement)if(/auto|scroll/.test(${active}.getComputedStyle(p).overflowY)&&p.scrollHeight>p.clientHeight+1)scroll.push(p.id||p.className);
          const r=el.getBoundingClientRect(),hit=d.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
          return {scroll,reachable:hit===el||el.contains(hit),hit:hit?.id||hit?.className,windowSize:[${active}.innerWidth,${active}.innerHeight],buttonRect:{x:r.x,y:r.y,width:r.width,height:r.height},relaxHost:d.getElementById('add-atoms-relax-host').contains(d.getElementById('btn-relax'))};})()`);
        assert.deepEqual(result.scroll,['inspector-content']);assert.ok(result.reachable&&result.relaxHost,JSON.stringify(result));
        await fs.writeFile(path.join(output,`placement-${width}-${zoom}.png`),(await win.webContents.capturePage()).toPNG());
        layoutChecks.push({width,height,zoom,...result});
    }
    win.webContents.setZoomFactor(1);win.setContentSize(1440,960);
    await js(`(async()=>{const a=${appRef};a.setAtomsData(await a.api.updateConstraints([0,1,2],{fix_atoms:false,directional_kind:'none'}));
        a.applyDesignSettings(${JSON.stringify(prior.settings)});await a.aiApply({mode:${JSON.stringify(prior.vizOnly?'view':'edit')}});a.clearAtomSelection();a.updateSelectionVisuals();a.updateUI();})()`);
    const result={pixelChecks,axisChecks,layoutChecks};await fs.writeFile(path.join(output,'visual-parity.json'),JSON.stringify(result,null,2));
    return result;
};
