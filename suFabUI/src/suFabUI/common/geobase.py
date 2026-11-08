import numpy as np


def is_left(index1, index2, vertices):
    """
    Determine v(center, index1) is on the left side of v(center, index2) by arctan2(y, x)
    @param index1: index of vertex 1
    @param index2: index of vertex 2
    @param vertices: contour with vertex indexes in order of clockwise
    Note: the default order is clockwise
    """
    center = np.mean(vertices, axis=0)
    point1 = vertices[index1]
    point2 = vertices[index2]
    vector1 = point1 - center
    vector2 = point2 - center
    angle1 = np.arctan2(vector1[1], vector1[0])
    angle2 = np.arctan2(vector2[1], vector2[0])
    # adjust to [0, 2pi]
    angle1 = (angle1 + 2*np.pi) % (2*np.pi)
    angle2 = (angle2 + 2*np.pi) % (2*np.pi)
    angle_diff = (angle2 - angle1 + 2*np.pi) % (2*np.pi)

    return angle_diff > np.pi


def is_left_cross_product(right_idx, left_idx, vertices, clockwise=False, epsilon=1e-9):
    """
    Determine v(center, left_idx) is on the left side of v(center, right_idx) by cross product
    @param right_idx: index of vertex to test
    @param left_idx: index of vertex to test
    @param vertices: contour with vertex indexes in order of clockwise
    Note: the default order is clockwise
    """
    center = np.mean(vertices, axis=0)
    v1 = vertices[right_idx] - center
    v2 = vertices[left_idx] - center
    cross_product = v1[0]*v2[1] - v1[1]*v2[0]

    if abs(cross_product) < epsilon:  # Points are collinear
        raise Exception("Collinear is found")

    if clockwise:
        return cross_product < 0
    else:
        return cross_product > 0


def get_left_index_on_contour(start_idx, idx1, idx2, vertices):
    """
    Compare the position of two points (x1 and x2) relative to a start point in a clockwise contour.

    Args:
    start_start_idx (int): Index of the starting point in the vertices array.
    idx1 (int): Index of the first point to compare.
    idx2 (int): Index of the second point to compare.
    vertices (np.array): Array of vertex coordinates, arranged clockwise.
    return: index of the point on the left of start_idx of the contour.
    """

    n = len(vertices)

    def distance(x1, x2):
        return (x2 - x1 + n) % n

    # If both are on the same side or on the line, compare their distances from start
    dist_x1 = distance(start_idx, idx1)
    dist_x2 = distance(start_idx, idx2)

    if dist_x1 < dist_x2:
        return idx2
    else:
        return idx1


def resample_contour_by_start_end_id(c, start_idx, end_idx):
    """
    @param c: a contour, numpy array of vertices
    @start_idx (int): Index of the starting point in the vertices array.
    @end_idx (int): Index of the ending point in the vertices array.
    """
    if start_idx == end_idx:
        return np.array([c[start_idx]])

    # return a segment
    if start_idx < end_idx:
        return c[start_idx:end_idx + 1]

    # connect two segments
    return np.vstack((c[start_idx:], c[:end_idx + 1]))

