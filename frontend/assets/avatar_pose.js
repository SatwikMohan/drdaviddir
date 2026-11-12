import {Quaternion, Vector3, MathUtils} from 'three';

// Reject structurally invalid exports, without changing the source asset.
export function disableInvalidMorphTargets(root) {
  const rejected = [];
  root.traverse(mesh => {
    if (!mesh.isMesh) return;
    const geometry = mesh.geometry;
    const count = geometry.attributes.position?.count;
    const invalid = Object.entries(geometry.morphAttributes).flatMap(([semantic, targets]) =>
      targets.flatMap((target, index) => target.count === count ? [] :
        [{mesh: mesh.name, semantic, index, expected: count, actual: target.count}]));
    if (!invalid.length) return;
    rejected.push(...invalid);
    // Disable the entire set: incomplete target indexing must never be guessed.
    geometry.morphAttributes = {};
    geometry.boundingBox = null;
    geometry.boundingSphere = null;
    mesh.morphTargetInfluences = [];
    mesh.morphTargetDictionary = {};
  });
  if (rejected.length) console.warn('Invalid avatar morph targets disabled', rejected);
  return rejected;
}

// Explicit profile for the inspected body rig. No guessed bone names or bind-pose edits.
export function applyAPose(root, degrees = 45) {
  if (!Number.isFinite(degrees) || degrees < 0 || degrees > 60) {
    throw new RangeError('Arm lowering angle must be between 0 and 60 degrees');
  }
  const pairs = [['LeftArm', 'LeftForeArm'], ['RightArm', 'RightForeArm']];
  const bindings = pairs.map(([armName, elbowName]) => {
    const arm = root.getObjectByName(armName), elbow = root.getObjectByName(elbowName);
    return {arm, elbow};
  });
  if (bindings.some(({arm, elbow}) => !arm?.isBone || !elbow?.isBone || elbow.parent !== arm)) {
    return {applied: false, reason: 'Expected arm bones are unavailable', restore() {}};
  }
  root.updateMatrixWorld(true);
  const rootRotation = root.getWorldQuaternion(new Quaternion());
  const inverseRoot = rootRotation.clone().invert();
  const angle = MathUtils.degToRad(degrees);
  const rest = bindings.map(({arm}) => arm.quaternion.clone());
  for (const {arm, elbow} of bindings) {
    const direction = elbow.getWorldPosition(new Vector3()).sub(arm.getWorldPosition(new Vector3())).normalize();
    const modelDirection = direction.clone().applyQuaternion(inverseRoot);
    const target = new Vector3(Math.sign(modelDirection.x) * Math.cos(angle), -Math.sin(angle), 0)
      .applyQuaternion(rootRotation);
    const worldRotation = arm.getWorldQuaternion(new Quaternion());
    const parentInverse = arm.parent.getWorldQuaternion(new Quaternion()).invert();
    arm.quaternion.copy(parentInverse.multiply(new Quaternion().setFromUnitVectors(direction, target))
      .multiply(worldRotation));
    root.updateMatrixWorld(true);
  }
  // Three.js caches skinned bounds: refresh after a pose change.
  const refreshBounds = () => root.traverse(mesh => {
    if (mesh.isSkinnedMesh) { mesh.computeBoundingBox(); mesh.computeBoundingSphere(); }
  });
  refreshBounds();
  return {applied: true, degrees, restore() {
    bindings.forEach(({arm}, index) => arm.quaternion.copy(rest[index]));
    root.updateMatrixWorld(true);
    refreshBounds();
  }};
}
