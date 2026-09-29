"""FixedPlane visual contract on real WebGL, separate from ASE enforcement."""
import base64
import io

import numpy as np
import pytest
from ase import Atoms
from ase.constraints import FixedPlane
from PIL import Image
from playwright.sync_api import sync_playwright
from v_ase.viewer import view, find_free_port


@pytest.mark.parametrize('mode', ['3d', '2d'])
def test_fixedplane_selection_hover_camera_export_and_motion(mode, tmp_path):
    atoms = Atoms('Cu4', positions=[[-4, -3, 0], [4, -3, 0], [-4, 3, 0], [4, 3, 0]])
    normals = [[0, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]]
    atoms.set_constraint([FixedPlane(i, n) for i, n in enumerate(normals)])
    port = find_free_port()
    editor = view(atoms, notebook=True, block=False, port=port, viz_only=False,
                  open_browser=False, close_on_disconnect=False)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1200, 'height': 850})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/?session_id={editor.session_id}')
            page.wait_for_function('window.__ASE_APP__?.renderer?.atomMeshByIndex?.size === 4')
            page.evaluate("""mode => {
                const a=window.__ASE_APP__, r=a.renderer;
                a.applyDesignSettings({display:{...a.state.display, atomDisplayMode:mode,
                    showGrid:false,showAxes:false,showCell:false,showBonds:false,
                    viewportBackground:'white',atomRadiusScale:1,labelRadii:{Cu:0.8}}},{render:true});
                a.setInspectorCollapsed(true, false);
                r.setProjectionMode('orthographic');
                r.camera.position.set(0,-16,22); r.camera.up.set(0,0,1);
                r.controls.target.set(0,0,0);r.camera.lookAt(r.controls.target);
                r.setPixelsPerAngstrom(45);r.controls.update();r.renderNow();
            }""", mode)
            # The visible Orbit tool must start the same real tumble gesture
            # as middle-drag, without consuming atom-selection clicks afterward.
            pose=page.evaluate("""()=>{const r=window.__ASE_APP__.renderer;return {
                position:r.camera.position.toArray(),quaternion:r.camera.quaternion.toArray(),
                target:r.controls.target.toArray()};}""")
            page.locator('#tool-orbit').click()
            box=page.locator('canvas').first.bounding_box()
            page.mouse.move(box['x']+box['width']*.45,box['y']+box['height']*.4)
            page.mouse.down();page.mouse.move(box['x']+box['width']*.6,box['y']+box['height']*.5,steps=8);page.mouse.up()
            assert page.evaluate('window.__ASE_APP__.renderer.camera.position.toArray()') != pose['position']
            assert page.evaluate('window.__ASE_APP__.state.selected.size') == 0
            page.locator('#tool-select').click()
            page.evaluate("""p=>{const r=window.__ASE_APP__.renderer;
                r.camera.position.fromArray(p.position);r.camera.quaternion.fromArray(p.quaternion);
                r.controls.target.fromArray(p.target);r.renderNow();}""",pose)
            def capture(name):
                data = page.evaluate("""() => window.__ASE_APP__.renderer.exportPNG(960,680,{
                    selectionAppearance:'interactive',backgroundColor:'#ffffff',
                    includeGrid:false,includeAxes:false,includeCell:false})""")
                raw = base64.b64decode(data.split(',')[1])
                (tmp_path / f'{mode}-{name}.png').write_bytes(raw)
                return np.asarray(Image.open(io.BytesIO(raw)).convert('RGB')).astype(int)
            def without_face():
                # Preserve atom/selection/edge pixels as a baseline for the
                # translucent face. In front it must blend once; behind it
                # must be fully hidden by the atom, independent of draw order.
                page.evaluate('window.__ASE_APP__.renderer.constraintMaterials.planeFace.visible=false; window.__ASE_APP__.renderer.renderNow()')
                try:
                    raw = page.locator('canvas').first.screenshot()
                    return np.asarray(Image.open(io.BytesIO(raw)).convert('RGB')).astype(int)
                finally:
                    page.evaluate('window.__ASE_APP__.renderer.constraintMaterials.planeFace.visible=true; window.__ASE_APP__.renderer.renderNow()')
            face_color = np.array([145,203,212])
            def blend(under):
                return .30 * face_color + .70 * under
            idle = capture('idle')
            # Selection expands both ring boundaries by the yellow shell radius
            # while keeping the band width and edge thickness. Publication
            # hides selection and restores the ordinary ring geometry.
            for selected_face in [False, True]:
                probe = page.evaluate("""selected=>{const a=window.__ASE_APP__,r=a.renderer;
                    a.applySelectionAction({references:selected?[0]:[],mode:'replace',origin:'semantic',measurement:'bulk'});
                    const center=r.atomMeshByIndex.get(0).position;
                    r.controls.target.copy(center);r.camera.position.copy(center).add(center.clone().set(0,0,25));
                    r.camera.up.set(0,1,0);r.camera.lookAt(center);r.setPixelsPerAngstrom(200);
                    r.controls.update();r.renderNow();const rect=r.domElement.getBoundingClientRect();
                    const offset=selected?.18:0;
                    return [1.08,1.30,1.462+offset,1.013+offset,1.74].map(radius=>{const p=r.projectWorldToClient(center.clone()
                        .add(center.clone().set(radius*r.atomVisualRadius(0),0,0)));
                        return [p.x-rect.left,p.y-rect.top];});}""",selected_face)
                raw=page.locator('canvas').first.screenshot()
                image=np.asarray(Image.open(io.BytesIO(raw)).convert('RGB')).astype(int)
                baseline=without_face()
                for index,(x,y) in enumerate(probe):
                    x,y=round(x),round(y)
                    patch=image[y:y+1,x:x+1] if index>=2 else image[y-1:y+2,x-1:x+2]
                    under=baseline[y-1:y+2,x-1:x+2]
                    if index==4 or (selected_face and index==0):
                        # Outside the largest rim or inside its selected cutout:
                        # no face may tint the background/yellow outline.
                        under=baseline[y:y+1,x:x+1] if index>=2 else under
                        expected=under
                    else:
                        expected=[0,116,129] if index>=2 else blend(under)
                    assert np.abs(patch-expected).max()<=2,(mode,selected_face,index,patch.tolist())
                if selected_face:
                    export_script="""()=>{const r=window.__ASE_APP__.renderer;
                        const size=r.domElement.getBoundingClientRect();
                        return r.exportPNG(Math.round(size.width),Math.round(size.height),{selectionAppearance:'publication',
                            backgroundColor:'#ffffff',includeGrid:false,includeAxes:false,includeCell:false});}"""
                    exported=page.evaluate(export_script)
                    raw=base64.b64decode(exported.split(',')[1]);(tmp_path/f'{mode}-filled-publication.png').write_bytes(raw)
                    exported_image=np.asarray(Image.open(io.BytesIO(raw)).convert('RGB')).astype(int)
                    page.evaluate('window.__ASE_APP__.renderer.constraintMaterials.planeFace.visible=false')
                    try:
                        reference=page.evaluate(export_script)
                        raw_reference=base64.b64decode(reference.split(',')[1])
                        reference_image=np.asarray(Image.open(io.BytesIO(raw_reference)).convert('RGB')).astype(int)
                    finally:
                        page.evaluate('window.__ASE_APP__.renderer.constraintMaterials.planeFace.visible=true')
                    # Publication restores the nonselected face inside the editor
                    # shell, including while that atom remains selected.
                    x,y=map(round,probe[0]);patch=exported_image[y-1:y+2,x-1:x+2]
                    expected=blend(reference_image[y-1:y+2,x-1:x+2])
                    assert np.abs(patch-expected).max()<=2,(mode,'publication',patch.tolist())
            # A real ring must exchange front/back visibility with both its
            # atom and the yellow selection shell. A foreground decal or a
            # front-depth substitution fails these actual-pixel checks.
            page.evaluate("""() => window.__ASE_APP__.applySelectionAction({
                references:[0],mode:'replace',origin:'semantic',measurement:'bulk'})""")
            for eye_sign in [-1, 1]:
                samples = page.evaluate("""sign => {const r=window.__ASE_APP__.renderer;
                    const center=r.atomMeshByIndex.get(0).position;
                    r.controls.target.copy(center);
                    r.camera.position.copy(center).add(center.clone().set(0,sign*16,8));
                    r.camera.up.set(0,0,1);r.camera.lookAt(center);
                    r.setPixelsPerAngstrom(100);r.controls.update();r.renderNow();
                    const rect=r.domElement.getBoundingClientRect();
                    return [-Math.PI/2,Math.PI/2,-Math.PI/4,Math.PI/4].map(angle=>{
                        const v=center.clone().add(center.clone().set(Math.cos(angle),Math.sin(angle),0)
                            .multiplyScalar(1.32*r.atomVisualRadius(0)));
                        const p=r.projectWorldToClient(v);
                        return {x:p.x-rect.left,y:p.y-rect.top,
                            front:Math.sign(Math.sin(angle))===sign,
                            shell:Math.abs(angle)<Math.PI/2};
                    });}""", eye_sign)
                raw = page.locator('canvas').first.screenshot()
                (tmp_path / f'{mode}-depth-{eye_sign}.png').write_bytes(raw)
                image = np.asarray(Image.open(io.BytesIO(raw)).convert('RGB')).astype(int)
                baseline = without_face()
                for sample in samples:
                    x,y=round(sample['x']),round(sample['y'])
                    patch=image[y-1:y+2,x-1:x+2]
                    under=baseline[y-1:y+2,x-1:x+2]
                    expected=blend(under) if sample['front'] else under
                    assert np.abs(patch-expected).max()<=2,(mode,eye_sign,sample,patch.tolist(),expected.tolist())
            # A neighboring atom must also occlude the band when in front,
            # and reveal it when moved behind, independent of object draw order.
            for side in [1, -1]:
                point = page.evaluate("""side=>{const r=window.__ASE_APP__.renderer;
                    const center=r.atomMeshByIndex.get(0).position;
                    const bandPoint=center.clone().add(center.clone().set(1.32*r.atomVisualRadius(0),0,0));
                    const towardCamera=r.camera.position.clone().sub(r.controls.target).normalize();
                    const blocker=bandPoint.clone().addScaledVector(towardCamera,side*3);
                    r.updatePositions([[-4,-3,0],blocker.toArray(),[-4,3,0],[4,3,0]]);
                    // Isolate occlusion by the blocker atom, not its own cyan ring.
                    r.constraintGuideGroup.children.find(g=>g.userData.constraintGuideFor===1).children[0].visible=false;
                    r.renderNow();const p=r.projectWorldToClient(bandPoint);
                    const rect=r.domElement.getBoundingClientRect();
                    return [p.x-rect.left,p.y-rect.top];}""",side)
                raw=page.locator('canvas').first.screenshot()
                (tmp_path/f'{mode}-neighbor-{side}.png').write_bytes(raw)
                im=np.asarray(Image.open(io.BytesIO(raw)).convert('RGB')).astype(int)
                baseline=without_face()
                x,y=map(round,point);patch=im[y-1:y+2,x-1:x+2]
                under=baseline[y-1:y+2,x-1:x+2]
                expected=under if side==1 else blend(under)
                assert np.abs(patch-expected).max()<=2,(mode,side,patch.tolist(),expected.tolist())
            page.evaluate("""()=>{const r=window.__ASE_APP__.renderer;
                r.updatePositions([[-4,-3,0],[4,-3,0],[-4,3,0],[4,3,0]]);
                r.constraintGuideGroup.children.find(g=>g.userData.constraintGuideFor===1).children[0].visible=true;}""")
            page.evaluate("""()=>{const r=window.__ASE_APP__.renderer;
                r.camera.position.set(0,-16,22);r.controls.target.set(0,0,0);
                r.camera.lookAt(r.controls.target);r.setPixelsPerAngstrom(45);
                r.controls.update();r.renderNow();}""")
            # Selecting two atoms reveals their own normals, never a shared plane.
            page.evaluate("""() => {const a=window.__ASE_APP__;
                a.applySelectionAction({references:[0,3],mode:'replace',origin:'semantic',measurement:'bulk'});
                a.renderer.renderNow();} """)
            selected = capture('selected')
            yellow = lambda im: (im[:,:,0]>200)&(im[:,:,1]>140)&(im[:,:,2]<90)
            assert yellow(selected).sum() > yellow(idle).sum() + 100
            state = page.evaluate("""() => window.__ASE_APP__.renderer.constraintGuideGroup.children.map(g=>({
                index:g.userData.constraintGuideFor,
                normal:[0,0,1].map((_,i)=> {const v=g.position.clone().set(0,0,1).applyQuaternion(g.quaternion);return v.getComponent(i)}),
                detail:!!g.children.find(c=>c.userData.fixedPlaneDetail)?.visible,
                surfaces:g.children.filter(c=>['PlaneGeometry','CircleGeometry'].includes(c.geometry?.type)).length
            }))""")
            for i, g in enumerate(state):
                assert g['normal'] == pytest.approx(np.array(normals[i])/np.linalg.norm(normals[i]))
                assert g['detail'] == (i in [0, 3])
                assert g['surfaces'] == 0
            # Real pointer hover, including leaving the canvas before a queued pick.
            point = page.evaluate("""() => {const r=window.__ASE_APP__.renderer;
                return r.projectWorldToClient(r.atomMeshByIndex.get(1).position)}""")
            page.mouse.move(point['x'], point['y'])
            page.wait_for_function('window.__ASE_APP__.state.hoveredIndex === 1')
            hover = capture('hover')
            assert np.count_nonzero(np.any(hover != selected, axis=2)) > 100
            assert page.evaluate('Array.from(window.__ASE_APP__.state.selected)') == [0, 3]
            page.mouse.move(1, 1)
            page.wait_for_function('window.__ASE_APP__.state.hoveredIndex === null')
            assert not page.evaluate("window.__ASE_APP__.renderer.constraintGuideGroup.children[1].children.find(c=>c.userData.fixedPlaneDetail).visible")
            # Radius and position change without leaving a ring at the old pose.
            page.evaluate("""() => {const a=window.__ASE_APP__;
                a.applySelectionAction({references:[0],mode:'replace',origin:'semantic',measurement:'bulk'});
                a.enterTransformMode('MOVE');a.transform.setAxis('X',a.renderer.camera);
                a.transform.buffer='1';a.applyTransformPreview();a.renderer.renderNow();} """)
            move = page.evaluate("""() => {const r=window.__ASE_APP__.renderer;return {
                atom:r.atomMeshByIndex.get(0).position.toArray(),
                ring:r.constraintGuideGroup.children[0].position.toArray(),
                sheets:r.constraintMotionGuideGroup.children.length}}""")
            assert move['atom'] == pytest.approx([-3, -3, 0])
            assert move['ring'] == pytest.approx(move['atom'])
            assert move['sheets'] == 0
            page.evaluate('window.__ASE_APP__.cancelTransform()')
            assert page.evaluate('window.__ASE_APP__.renderer.atomMeshByIndex.get(0).position.toArray()') == pytest.approx([-4,-3,0])
            # Endpoint X strokes face the draw camera, including off-axis exports.
            for eye, up in [([0,0,25],[0,1,0]), ([25,0,0],[0,0,1]), ([13,-20,17],[0,0,1])]:
                page.evaluate("""({eye,up})=>{const r=window.__ASE_APP__.renderer;
                    r.camera.position.fromArray(eye);r.camera.up.fromArray(up);r.camera.lookAt(r.controls.target);
                    r.controls.update();r.renderNow();}""", {'eye':eye,'up':up})
                assert page.evaluate("""()=>{const r=window.__ASE_APP__.renderer;
                    const g=r.constraintGuideGroup.children[0];
                    const x=g.children.find(c=>c.userData.fixedPlaneDetail).children.find(c=>c.userData.fixedPlaneNormalX);
                    return g.quaternion.clone().multiply(x.quaternion).angleTo(r.camera.quaternion)<1e-6;}""")
                capture('angle-'+str(eye[0]))
            page.evaluate("""()=>{const a=window.__ASE_APP__;
                a.applyDesignSettings({display:{...a.state.display,showConstraints:false}},{render:true});} """)
            assert not page.evaluate('window.__ASE_APP__.renderer.constraintGuideGroup.visible')
            assert editor.get_atoms().constraints[0].get_indices().tolist() == [0]
            assert not errors
            browser.close()
    finally:
        editor.close()


@pytest.mark.parametrize('mode', ['3d', '2d'])
@pytest.mark.parametrize('count', [4, 256])
def test_fixedplane_tracks_moving_property_radius_and_zero(mode, count):
    """Exercise the same radius/position paths used by trajectory video samples."""
    first = Atoms('Cu' * count, positions=np.column_stack((np.arange(count)*6,
                                                         np.zeros(count),np.zeros(count))))
    first.set_constraint(FixedPlane(0, [0,0,1]))
    first.new_array('fraction', np.full(count, .25))
    second = first.copy()
    second.positions[:,0] += 2
    second.arrays['fraction'][:] = 1
    editor = view([first,second], notebook=True, block=False, port=find_free_port(),
                  open_browser=False, close_on_disconnect=False, viz_only=False)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1000,'height':800})
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(editor.url)
            page.wait_for_function('window.__ASE_APP__?.state?.atoms?.metadata?.frame_count === 2')
            result=page.evaluate("""async ({mode,count})=>{
                const a=window.__ASE_APP__,r=a.renderer;
                a.applyDesignSettings({display:{...a.state.display,atomDisplayMode:mode,
                    showBonds:false,atomRadiusScale:1.5,labelRadii:{Cu:.9},atomRadiusScales:{0:.8}}},{render:true});
                a.state.display.atomRadiusMapping={enabled:true,field:'array::fraction::scalar',
                    valueTransform:'identity',rangeMode:'manual',min:0,max:1,minMultiplier:0,
                    maxMultiplier:1,exponent:1,scope:'all',indices:[]};
                await a.updateAtomRadiusMapping();
                const first=await a.videoFrameSnapshot();
                await a.loadFrame(1);
                const second=await a.videoFrameSnapshot();
                a.applySelectionAction({references:Array.from({length:count},(_,i)=>i),
                    mode:'replace',origin:'semantic',measurement:'bulk'});
                const group=r.constraintGuideGroup.children.find(g=>g.userData.constraintGuideFor===0);
                r.renderNow();const meshId=group.uuid,geometryId=group.children[0].geometry.uuid;
                const states=[];
                const snapshot=()=>{
                    const g=r.constraintGuideGroup.children.find(g=>g.userData.constraintGuideFor===0);
                    const outline=r.selectionOutlines.children.find(o=>o.userData.selectionInstances||o.userData.outlineFor===0);
                    const ref=r.atomInstanceRefsByIndex?.[0];
                    return {position:g.position.toArray(),scale:g.scale.x,visible:g.visible,
                        atomScale:r.useInstancedAtoms?ref.matrix[ref.matrixOffset]:r.atomMeshByIndex.get(0).scale.x,
                        selectionScale:outline.userData.selectionInstances?outline.instanceMatrix.array[0]:outline.scale.x,
                        markerWidth:g.children.find(c=>c.userData.fixedPlaneDetail).children
                            .find(c=>c.userData.fixedPlaneNormalX).scale.x*g.scale.x*.28,
                        sameMesh:g.uuid===meshId,sameGeometry:g.children[0].geometry.uuid===geometryId};
                };
                for(const amount of [0,.2,.4,.6,.8,1]){
                    const sample={count,positions:Float64Array.from(first.positions,(x,i)=>x+(second.positions[i]-x)*amount)};
                    a.interpolateVideoRadiusScalars(first,second,amount,sample);
                    r.updatePositionsFlat(sample.positions,0,count);a.applyVideoSampleRadiusFactors(sample);
                    r.renderNow();states.push({amount,...snapshot()});
                }
                const zeros=new Float32Array(count).fill(1);zeros[0]=0;
                r.setAtomRadiusFactors(zeros);r.renderNow();const hidden=snapshot();
                zeros[0]=.0001;r.setAtomRadiusFactors(zeros);r.renderNow();const tiny=snapshot();
                zeros[0]=.75;r.setAtomRadiusFactors(zeros);r.renderNow();const restored=snapshot();
                return {instanced:r.useInstancedAtoms,states,hidden,tiny,restored};
            }""",{'mode':mode,'count':count})
            assert result['instanced'] == (count==256)
            base_radius=1.5*.9*.8
            for state in result['states']:
                radius=base_radius*(.25+.75*state['amount'])
                assert state['position'] == pytest.approx([2*state['amount'],0,0])
                assert state['scale'] == pytest.approx(radius)
                assert state['atomScale'] == pytest.approx(radius)
                assert state['selectionScale'] == pytest.approx(radius*1.18)
                assert state['visible'] and state['sameMesh'] and state['sameGeometry']
                assert state['markerWidth'] < radius
            assert not result['hidden']['visible']
            assert result['hidden']['scale'] == 0
            assert result['tiny']['visible']
            assert result['tiny']['scale'] == pytest.approx(base_radius*.0001)
            assert result['tiny']['markerWidth'] < result['tiny']['scale']
            assert result['restored']['visible']
            assert result['restored']['scale'] == pytest.approx(base_radius*.75)
            assert result['restored']['sameMesh'] and result['restored']['sameGeometry']
            assert not errors
            browser.close()
    finally:
        editor.close()
