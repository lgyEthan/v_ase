const CELL_EPSILON = 1e-12;
const MAX_MIC_ATOM_CANDIDATES = 10000;
const MAX_MIC_FRAME_CANDIDATES = 2000000;

export function normalizeInterpolationMultiplier(value, maximum = 64) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 1;
    return Math.max(1, Math.min(maximum, Math.round(numeric)));
}

export function interpolatedFrameCount(frameCount, multiplier = 1) {
    const count = Math.max(0, Math.floor(Number(frameCount) || 0));
    if (count <= 1) return count;
    const factor = normalizeInterpolationMultiplier(multiplier);
    return (count - 1) * factor + 1;
}

function positionCount(positions) {
    if (ArrayBuffer.isView(positions)) {
        return positions.length % 3 === 0 ? positions.length / 3 : 0;
    }
    return Array.isArray(positions) && positions.every(row => row?.length === 3)
        ? positions.length : 0;
}

function positionComponent(positions, index, axis) {
    const value = ArrayBuffer.isView(positions)
        ? positions[index * 3 + axis] : positions?.[index]?.[axis];
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        throw new Error('Frame interpolation requires finite XYZ positions.');
    }
    return value;
}

function normalizedCell(cell) {
    if (cell == null) return null;
    if (
        !Array.isArray(cell)
        || cell.length !== 3
        || cell.some(row => !Array.isArray(row) || row.length !== 3)
    ) {
        throw new Error('Frame interpolation cell must be a finite 3 x 3 matrix.');
    }
    const normalized = cell.map(row => row.map(Number));
    if (!normalized.every(row => row.every(Number.isFinite))) {
        throw new Error('Frame interpolation cell must be a finite 3 x 3 matrix.');
    }
    return normalized;
}

function determinant3(matrix) {
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    );
}

function normalizedOrigin(origin) {
    if (origin == null) return [0, 0, 0];
    if (!Array.isArray(origin) || origin.length !== 3 || !origin.every(Number.isFinite)) {
        throw new Error('Frame interpolation cell origin must contain finite XYZ values.');
    }
    return origin;
}

function inverse3(matrix) {
    const determinant = determinant3(matrix);
    if (!Number.isFinite(determinant) || Math.abs(determinant) < CELL_EPSILON) return null;
    const inverseDeterminant = 1 / determinant;
    return [
        [
            (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) * inverseDeterminant,
            (matrix[0][2] * matrix[2][1] - matrix[0][1] * matrix[2][2]) * inverseDeterminant,
            (matrix[0][1] * matrix[1][2] - matrix[0][2] * matrix[1][1]) * inverseDeterminant
        ],
        [
            (matrix[1][2] * matrix[2][0] - matrix[1][0] * matrix[2][2]) * inverseDeterminant,
            (matrix[0][0] * matrix[2][2] - matrix[0][2] * matrix[2][0]) * inverseDeterminant,
            (matrix[0][2] * matrix[1][0] - matrix[0][0] * matrix[1][2]) * inverseDeterminant
        ],
        [
            (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0]) * inverseDeterminant,
            (matrix[0][1] * matrix[2][0] - matrix[0][0] * matrix[2][1]) * inverseDeterminant,
            (matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]) * inverseDeterminant
        ]
    ];
}

function multiplyRowVector(vector, matrix) {
    return [
        vector[0] * matrix[0][0] + vector[1] * matrix[1][0] + vector[2] * matrix[2][0],
        vector[0] * matrix[0][1] + vector[1] * matrix[1][1] + vector[2] * matrix[2][1],
        vector[0] * matrix[0][2] + vector[1] * matrix[1][2] + vector[2] * matrix[2][2]
    ];
}

function interpolatedCell(first, second, amount) {
    if (!first || !second) return first || second || null;
    return first.map((row, i) => row.map(
        (value, j) => value + (second[i][j] - value) * amount
    ));
}

function normalizedPbc(first = [], second = []) {
    return [0, 1, 2].map(axis => Boolean(first?.[axis]) && Boolean(second?.[axis]));
}

function wrapFractional(value) {
    let wrapped = value - Math.floor(value);
    if (Math.abs(wrapped) < CELL_EPSILON || Math.abs(1 - wrapped) < CELL_EPSILON) {
        wrapped = 0;
    }
    return wrapped;
}

function dot3(first, second) {
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2];
}

function periodicImageSearch(cell, pbc) {
    const axes = [0, 1, 2].filter(axis => pbc[axis]);
    const basis = axes.map(axis => cell[axis]);
    const dimension = axes.length;
    const q = [];
    const r = Array.from({length: dimension}, () => new Array(dimension).fill(0));
    let orthogonal = true;
    for (let column = 0; column < dimension; column++) {
        const vector = [...basis[column]];
        // Reorthogonalized modified Gram-Schmidt: columns are the periodic
        // lattice vectors only. Tilted finite rows must never become shifts.
        for (let pass = 0; pass < 2; pass++) {
            for (let row = 0; row < column; row++) {
                const projection = dot3(q[row], vector);
                r[row][column] += projection;
                for (let axis = 0; axis < 3; axis++) vector[axis] -= projection * q[row][axis];
            }
        }
        const length = Math.hypot(...vector);
        if (!Number.isFinite(length) || length <= 32 * Number.EPSILON * Math.hypot(...basis[column])) {
            throw new Error('Trajectory MIC requires independent periodic vectors in the midpoint cell.');
        }
        r[column][column] = length;
        q.push(vector.map(value => value / length));
        for (let row = 0; row < column; row++) {
            if (dot3(basis[row], basis[column]) !== 0) orthogonal = false;
        }
    }
    let frameCandidates = 0;
    const checkedInteger = value => {
        if (!Number.isSafeInteger(value)) {
            throw new Error('Trajectory MIC lattice shifts exceed exact integer precision.');
        }
        return value;
    };
    if (orthogonal) {
        // Independent projections are already the exact closest lattice
        // point. Avoid sphere-search allocations for ordinary orthogonal MD.
        return displacement => {
            const shift = [0, 0, 0];
            for (let index = 0; index < dimension; index++) {
                shift[axes[index]] = checkedInteger(Math.round(
                    dot3(q[index], displacement) / r[index][index]
                ));
            }
            return shift;
        };
    }
    return displacement => {
        const projected = q.map(vector => dot3(vector, displacement));
        if (!projected.every(Number.isFinite)) {
            throw new Error('Trajectory MIC displacement must be finite.');
        }
        const candidate = new Array(dimension).fill(0);
        for (let row = dimension - 1; row >= 0; row--) {
            let residual = projected[row];
            for (let column = row + 1; column < dimension; column++) {
                residual -= r[row][column] * candidate[column];
            }
            candidate[row] = checkedInteger(Math.round(residual / r[row][row]));
        }
        let best = [...candidate];
        let bestSquared = 0;
        for (let row = 0; row < dimension; row++) {
            let residual = projected[row];
            for (let column = row; column < dimension; column++) residual -= r[row][column] * candidate[column];
            bestSquared += residual * residual;
        }
        if (!Number.isFinite(bestSquared)) {
            throw new Error('Trajectory MIC distance exceeds finite numeric precision.');
        }
        let atomCandidates = 0;
        const search = (row, partialSquared) => {
            if (row < 0) {
                if (partialSquared < bestSquared) {
                    bestSquared = partialSquared;
                    best = [...candidate];
                }
                return;
            }
            let residual = projected[row];
            for (let column = row + 1; column < dimension; column++) residual -= r[row][column] * candidate[column];
            const center = residual / r[row][row];
            const nearest = checkedInteger(Math.round(center));
            const radius = Math.sqrt(Math.max(0, bestSquared - partialSquared + 64 * Number.EPSILON * bestSquared)) / r[row][row];
            const slack = 32 * Number.EPSILON * Math.max(1, Math.abs(center), radius);
            const lower = checkedInteger(Math.ceil(center - radius - slack));
            const upper = checkedInteger(Math.floor(center + radius + slack));
            const maximumOffset = Math.max(nearest - lower, upper - nearest);
            // Visit nearest integers first to tighten the sphere quickly. The
            // bound is explicit: difficult unreduced cells fail, never silently
            // fall back to a fixed image neighborhood or component rounding.
            for (let offset = 0; offset <= maximumOffset; offset++) {
                const currentRadius = Math.sqrt(Math.max(0, bestSquared - partialSquared + 64 * Number.EPSILON * bestSquared)) / r[row][row];
                if (offset > currentRadius + Math.abs(nearest - center) + slack) break;
                for (const value of offset === 0 ? [nearest] : [nearest + offset, nearest - offset]) {
                    if (value < lower || value > upper) continue;
                    if (++atomCandidates > MAX_MIC_ATOM_CANDIDATES || ++frameCandidates > MAX_MIC_FRAME_CANDIDATES) {
                        throw new Error('Trajectory MIC search exceeded its safety limit (10000 candidates per atom or 2000000 per frame); reduce the cell basis or disable MIC.');
                    }
                    const error = residual - r[row][row] * value;
                    const squared = partialSquared + error * error;
                    if (squared <= bestSquared + 64 * Number.EPSILON * bestSquared) {
                        candidate[row] = value;
                        search(row - 1, squared);
                    }
                }
            }
        };
        if (bestSquared > 0) search(dimension - 1, 0);
        const shift = [0, 0, 0];
        axes.forEach((axis, index) => { shift[axis] = best[index]; });
        return shift;
    };
}

export function interpolateTrajectoryFrames(
    firstFrame,
    secondFrame,
    amount,
    { useMic = false } = {}
) {
    const firstPositions = firstFrame?.positions;
    const secondPositions = secondFrame?.positions;
    const count = positionCount(firstPositions);
    if (!count || count !== positionCount(secondPositions)) {
        throw new Error('Frame interpolation requires the same atom count in adjacent frames.');
    }

    const numericAmount = Number(amount);
    if (!Number.isFinite(numericAmount)) throw new Error('Frame interpolation amount must be finite.');
    const t = Math.max(0, Math.min(1, numericAmount));
    const firstCell = normalizedCell(firstFrame?.cell);
    const secondCell = normalizedCell(secondFrame?.cell);
    const firstOrigin = normalizedOrigin(firstFrame?.cell_origin);
    const secondOrigin = normalizedOrigin(secondFrame?.cell_origin);
    const cellOrigin = firstOrigin.map((value, axis) => (1 - t) * value + t * secondOrigin[axis]);
    const hasOrigin = firstOrigin.some(value => value !== 0) || secondOrigin.some(value => value !== 0);
    const cell = interpolatedCell(firstCell, secondCell, t);
    const pbc = normalizedPbc(firstFrame?.pbc, secondFrame?.pbc);
    const firstInverse = firstCell ? inverse3(firstCell) : null;
    const secondInverse = secondCell ? inverse3(secondCell) : null;
    const micApplied = Boolean(
        useMic
        && pbc.some(Boolean)
        && firstInverse
        && secondInverse
        && cell
    );
    // One metric per frame interval keeps image choice independent of t.
    // Endpoint fractional positions still use their own cells, preserving
    // affine cell interpolation. Singular endpoints retain Cartesian fallback.
    const referenceCell = micApplied ? interpolatedCell(firstCell, secondCell, 0.5) : null;
    const closestImage = micApplied ? periodicImageSearch(referenceCell, pbc) : null;
    const positions = new Float64Array(count * 3);

    for (let index = 0; index < count; index++) {
        const first = [0, 1, 2].map(axis => positionComponent(firstPositions, index, axis));
        const second = [0, 1, 2].map(axis => positionComponent(secondPositions, index, axis));
        let interpolated;

        if (micApplied) {
            const firstFractional = multiplyRowVector(hasOrigin ? first.map((value, axis) => value - firstOrigin[axis]) : first, firstInverse);
            const secondFractional = multiplyRowVector(hasOrigin ? second.map((value, axis) => value - secondOrigin[axis]) : second, secondInverse);
            const delta = secondFractional.map((value, axis) => value - firstFractional[axis]);
            const shift = closestImage(multiplyRowVector(delta, referenceCell));
            const fractional = [0, 1, 2].map(axis => {
                const value = firstFractional[axis] + (delta[axis] - shift[axis]) * t;
                return pbc[axis] ? wrapFractional(value) : value;
            });
            interpolated = multiplyRowVector(fractional, cell);
            if (hasOrigin) interpolated = interpolated.map((value, axis) => value + cellOrigin[axis]);
        } else {
            interpolated = [0, 1, 2].map(
                axis => first[axis] + (second[axis] - first[axis]) * t
            );
        }

        if (!interpolated.every(Number.isFinite)) {
            throw new Error('Frame interpolation produced nonfinite XYZ positions.');
        }

        const offset = index * 3;
        positions[offset] = interpolated[0];
        positions[offset + 1] = interpolated[1];
        positions[offset + 2] = interpolated[2];
    }

    return { positions, count, cell, pbc, cell_origin: cellOrigin, micApplied };
}
