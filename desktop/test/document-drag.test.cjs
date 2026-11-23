'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../../v_ase/static/document_drag.js'),'utf8');
const modulePromise = import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

test('vertical navigator reorders by row and detaches across its right boundary', async () => {
    const {documentDropDestination:drop} = await modulePromise;
    const bar={left:0,right:216,top:0,bottom:900};
    const tabs=[{id:'a',left:8,right:208,top:82,bottom:128},{id:'b',left:8,right:208,top:131,bottom:177}];
    const viewport={width:1440,height:900};
    assert.deepEqual(drop({x:100,y:140},bar,tabs,true,viewport),{action:'reorder',id:'b',before:true});
    assert.deepEqual(drop({x:100,y:170},bar,tabs,true,viewport),{action:'reorder',id:'b',before:false});
    assert.deepEqual(drop({x:300,y:120},bar,tabs,true,viewport),{action:'detach'});
    assert.deepEqual(drop({x:100,y:450},bar,tabs,true,viewport),{action:'none'});
});

test('horizontal document strips retain midpoint and below-strip detachment', async () => {
    const {documentDropDestination:drop} = await modulePromise;
    const bar={left:0,right:1440,top:0,bottom:40};
    const tabs=[{id:'a',left:10,right:200,top:4,bottom:36}];
    const viewport={width:1440,height:900};
    assert.deepEqual(drop({x:150,y:20},bar,tabs,false,viewport),{action:'reorder',id:'a',before:false});
    assert.deepEqual(drop({x:150,y:120},bar,tabs,false,viewport),{action:'detach'});
});
