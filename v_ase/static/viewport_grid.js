import * as THREE from 'three';

// An analytic XY work plane. No finite mesh edge, no opaque surface and no
// depth writes: this guide can never cut holes into scientific geometry.
export function createViewportGrid(light = true) {
    const material = new THREE.ShaderMaterial({
        // Draw in the opaque pass before atoms, with explicit alpha blending.
        // A work-plane guide should never paint lines over an atom which lies
        // partly below XY; its alpha is only blended into the background.
        transparent: false, depthWrite: false, depthTest: false,
        blending: THREE.CustomBlending, blendEquation: THREE.AddEquation,
        blendSrc: THREE.SrcAlphaFactor, blendDst: THREE.OneMinusSrcAlphaFactor,
        blendEquationAlpha: THREE.AddEquation,
        blendSrcAlpha: THREE.OneFactor, blendDstAlpha: THREE.OneMinusSrcAlphaFactor,
        uniforms: {
            inverseView: {value: new THREE.Matrix4()},
            inverseProjection: {value: new THREE.Matrix4()},
            perspective: {value: false},
            eye: {value: new THREE.Vector3()},
            spacing: {value: 1}, fadeDistance: {value: 100},
            gridColor: {value: new THREE.Color(light ? '#aeb7b3' : '#56625e')}
        },
        vertexShader: `
            varying vec2 screen;
            void main() { screen = position.xy; gl_Position = vec4(position.xy, 0.0, 1.0); }
        `,
        fragmentShader: `
            uniform mat4 inverseView, inverseProjection;
            uniform bool perspective;
            uniform vec3 eye, gridColor;
            uniform float spacing, fadeDistance;
            varying vec2 screen;
            vec3 unproject(float z) {
                vec4 point = inverseView * inverseProjection * vec4(screen, z, 1.0);
                return point.xyz / point.w;
            }
            float lines(vec2 point, float stepSize) {
                vec2 coord = point / stepSize;
                vec2 derivative = max(fwidth(coord), vec2(0.00001));
                vec2 distanceToLine = abs(fract(coord - 0.5) - 0.5) / derivative;
                float antialias = 1.0 - min(min(distanceToLine.x, distanceToLine.y), 1.0);
                return antialias * (1.0 - smoothstep(0.2, 1.0, max(derivative.x, derivative.y)));
            }
            void main() {
                vec3 start = perspective ? eye : unproject(-1.0), finish = unproject(1.0);
                vec3 ray = finish - start;
                if (abs(ray.z) < 0.000001) discard;
                float t = -start.z / ray.z;
                if (perspective && t < 0.0) discard;
                vec3 point = start + t * ray;
                float fade = 1.0 - smoothstep(fadeDistance * 0.35, fadeDistance, length(point - eye));
                float alpha = max(lines(point.xy, spacing) * 0.16, lines(point.xy, spacing * 10.0) * 0.30);
                // Suppress dense stripes near an edge-on view of the work
                // plane, where even major lines converge below pixel spacing.
                float facing = abs(ray.z) / max(length(ray), 0.000001);
                alpha *= fade * smoothstep(0.04, 0.30, facing);
                if (alpha < 0.002) discard;
                gl_FragColor = vec4(gridColor, alpha);
            }
        `
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), material);
    mesh.name = 'v_ase_infinite_grid';
    mesh.frustumCulled = false;
    mesh.renderOrder = -10;
    mesh.onBeforeRender = (renderer, scene, camera) => {
        const u = material.uniforms;
        u.inverseView.value.copy(camera.matrixWorld);
        u.inverseProjection.value.copy(camera.projectionMatrixInverse);
        u.perspective.value = Boolean(camera.isPerspectiveCamera);
        u.eye.value.copy(camera.position);
        const span = camera.isOrthographicCamera
            ? Math.abs(camera.top - camera.bottom) / camera.zoom
            : Math.max(1, Math.abs(camera.position.z)) * 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) / camera.zoom;
        const desired = Math.max(0.001, span / 25);
        const unit = 10 ** Math.floor(Math.log10(desired));
        const ratio = desired / unit;
        u.spacing.value = unit * (ratio <= 2 ? 2 : ratio <= 5 ? 5 : 10);
        u.fadeDistance.value = Math.max(100, span * 30, Math.abs(camera.position.z) * 10);
    };
    return mesh;
}
