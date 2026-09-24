'use strict';

const { contextBridge, ipcRenderer, webUtils } = require('electron');

// Only the trusted top-level workspace receives IPC capabilities. Child editors
// use its same-origin adapter; no Electron or generic filesystem API is exposed.
if (process.isMainFrame) contextBridge.exposeInMainWorld('vaseDesktop', Object.freeze({
    platform: process.platform,
    newWindow: payload => ipcRenderer.invoke('vase:new-window', payload),
    closeWindow: () => ipcRenderer.invoke('vase:close-window'),
    chooseOpen: () => ipcRenderer.invoke('vase:open-dialog'),
    // webUtils accepts a real OS-backed File, not a renderer-supplied path.
    openDropped: file => {
        const filename = webUtils.getPathForFile(file);
        return filename ? ipcRenderer.invoke('vase:open-dropped-file', filename) : null;
    },
    chooseSave: options => ipcRenderer.invoke('vase:save-dialog', options),
    stat: token => ipcRenderer.invoke('vase:file-stat', token),
    read: (token, offset) => ipcRenderer.invoke('vase:file-read', token, offset),
    same: (a, b) => ipcRenderer.invoke('vase:file-same', a, b),
    begin: token => ipcRenderer.invoke('vase:file-begin', token),
    chunk: (id, bytes) => ipcRenderer.invoke('vase:file-chunk', id, bytes),
    finish: id => ipcRenderer.invoke('vase:file-finish', id),
    abort: id => ipcRenderer.invoke('vase:file-abort', id),
    onCommand: callback => {
        ipcRenderer.on('vase:command', (_event, command) => callback(command));
    },
    onOpen: callback => {
        ipcRenderer.on('vase:open-file', (_event, file) => callback(file));
    },
}));
