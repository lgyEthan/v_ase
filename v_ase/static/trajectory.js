const CELL_EPSILON = 1e-12;

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
    if (ArrayBuffer.isView(positions)) return Math.floor(positions.length / 3);
    return Array.isArray(positions) ? positions.length : 0;
}

function positionComponent(positions, index, axis) {
    if (ArrayBuffer.isView(positions)) return Number(positions[index * 3 + axis]) || 0;
    return Number(positions?.[index]?.[axis]) || 0;
}

function normalizedCell(cell) {
    if (
        !Array.isArray(cell)
        || cell.length !== 3
        || cell.some(row => !Array.isArray(row) || row.length !== 3)
    ) {
        return null;
    }
    const normalized = cell.map(row => row.map(Number));
    return normalized.every(row => row.every(Number.isFinite)) ? normalized : null;
}

function determinant3(matrix) {
    return (
        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    );
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

    const t = Math.max(0, Math.min(1, Number(amount) || 0));
    const firstCell = normalizedCell(firstFrame?.cell);
    const secondCell = normalizedCell(secondFrame?.cell);
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
    const positions = new Float64Array(count * 3);

    for (let index = 0; index < count; index++) {
        const first = [0, 1, 2].map(axis => positionComponent(firstPositions, index, axis));
        const second = [0, 1, 2].map(axis => positionComponent(secondPositions, index, axis));
        let interpolated;

        if (micApplied) {
            const firstFractional = multiplyRowVector(first, firstInverse);
            const secondFractional = multiplyRowVector(second, secondInverse);
            const fractional = [0, 1, 2].map(axis => {
                let delta = secondFractional[axis] - firstFractional[axis];
                if (pbc[axis]) delta -= Math.round(delta);
                const value = firstFractional[axis] + delta * t;
                return pbc[axis] ? wrapFractional(value) : value;
            });
            interpolated = multiplyRowVector(fractional, cell);
        } else {
            interpolated = [0, 1, 2].map(
                axis => first[axis] + (second[axis] - first[axis]) * t
            );
        }

        const offset = index * 3;
        positions[offset] = interpolated[0];
        positions[offset + 1] = interpolated[1];
        positions[offset + 2] = interpolated[2];
    }

    return { positions, count, cell, pbc, micApplied };
}
