import {
  BufferAttribute,
  TriangleFanDrawMode,
  TriangleStripDrawMode,
} from "../three/three.module.min.js";

function createSequentialIndex(count) {
  const IndexArray = count > 65535 ? Uint32Array : Uint16Array;
  const index = new IndexArray(count);

  for (let i = 0; i < count; i += 1) {
    index[i] = i;
  }

  return new BufferAttribute(index, 1);
}

function toTrianglesDrawMode(geometry, drawMode) {
  if (!geometry?.isBufferGeometry) {
    return geometry;
  }

  if (drawMode !== TriangleFanDrawMode && drawMode !== TriangleStripDrawMode) {
    return geometry;
  }

  const sourceIndex = geometry.getIndex() || createSequentialIndex(geometry.getAttribute("position")?.count || 0);
  const indexCount = sourceIndex.count;

  if (indexCount < 3) {
    return geometry;
  }

  const triangles = [];

  if (drawMode === TriangleFanDrawMode) {
    const first = sourceIndex.getX(0);

    for (let i = 1; i < indexCount - 1; i += 1) {
      triangles.push(first, sourceIndex.getX(i), sourceIndex.getX(i + 1));
    }
  }

  if (drawMode === TriangleStripDrawMode) {
    for (let i = 0; i < indexCount - 2; i += 1) {
      if (i % 2 === 0) {
        triangles.push(sourceIndex.getX(i), sourceIndex.getX(i + 1), sourceIndex.getX(i + 2));
      } else {
        triangles.push(sourceIndex.getX(i + 2), sourceIndex.getX(i + 1), sourceIndex.getX(i));
      }
    }
  }

  const convertedGeometry = geometry.clone();
  convertedGeometry.setIndex(triangles);
  convertedGeometry.clearGroups();

  return convertedGeometry;
}

export { toTrianglesDrawMode };
