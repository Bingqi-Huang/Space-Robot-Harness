"""Local measured surfaces, without filling the space underneath overhangs.

Missing pixels and discontinuities produce no triangles and remain unobserved;
this mesh is collision evidence, never a certificate that unknown space is free.
"""
import numpy as np


def depth_surface(depth, K, transform, valid, max_edge_m):
    """Triangulate adjacent measured pixels only, retaining the supplied validity mask.

    max_edge_m is the smallest feature the consuming gripper must resolve, from
    its geometry. Longer edges cannot establish a continuous contact surface.
    """
    depth = np.where(valid, depth, 0.0)
    rows, cols = depth.shape
    v, u = np.mgrid[:rows, :cols]
    points = np.stack(((u - K[0, 2]) * depth / K[0, 0],
                       (v - K[1, 2]) * depth / K[1, 1], depth), axis=-1).reshape(-1, 3)
    ids = np.arange(rows * cols).reshape(rows, cols)
    a, b, c, d = ids[:-1, :-1].ravel(), ids[:-1, 1:].ravel(), ids[1:, :-1].ravel(), ids[1:, 1:].ravel()
    faces = np.concatenate((np.stack((a, b, c), axis=1), np.stack((b, d, c), axis=1)))
    faces = faces[np.all(valid.ravel()[faces], axis=1)]
    triangles = points[faces]
    edges = triangles - np.roll(triangles, 1, axis=1)
    faces = faces[np.all(np.linalg.norm(edges, axis=2) <= max_edge_m, axis=1)]
    used, inverse = np.unique(faces, return_inverse=True)
    return points[used] @ transform[:3, :3].T + transform[:3, 3], inverse.reshape(-1, 3)
