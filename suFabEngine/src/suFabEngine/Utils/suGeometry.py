import numpy as np
import scipy.spatial.distance as scid
import pyclipper



def ccw(contour):
    """
    check a contour is (counter clockwise)CCW or CW
    return CCW: True   CW: False
    refer to https://stackoverflow.com/questions/1165647/how-to-determine-if-a-list-of-polygon-points-are-in-clockwise-order
    Here we use openCV image coordinate, like HTML5 canvas
    """
    l = np.asarray(contour)
    ls = np.roll(l, -1, axis=0)
    
    a = np.sum( (ls[:,0] - l[:,0])*(ls[:,1] + l[:,1]) )
    if a<0:
        return False
    return True

def area(p):
    """
    Calculate the area of a polygon defined by a list of points.

    Parameters:
    - p: A list of tuples/lists where each tuple/list represents a point (x, y) in the polygon.

    Returns:
    - The area of the polygon.
    """
    p = list(p)
    return 0.5 * abs(sum(x0*y1 - x1*y0 for ((x0, y0), (x1, y1)) in segments(p)))

def segments(p):
    """
    Generate segments from a list of polygon points by pairing each point with the next,
    closing the polygon by pairing the last point with the first.

    Parameters:
    - p: A list of tuples/lists representing the points of a polygon.

    Returns:
    - An iterator of tuples, where each tuple contains two points (each a tuple/list of x, y coordinates)
      representing a segment of the polygon.
    """
    return zip(p, p[1:] + [p[0]])

def compute_region_area(r):
    """
    Compute the total area of a region consisting of multiple contours. Contours can be either
    clockwise or counterclockwise, influencing the addition or subtraction of their areas.

    Parameters:
    - r: A list of contours, where each contour is a list of points defining a polygon.

    Returns:
    - The total area of the region defined by the contours.
    """
    a = 0
    for contour in r:
        if ccw(contour):
            a -= area(contour)  # Subtract area if contour is counterclockwise
        else:
            a += area(contour)  # Add area if contour is clockwise
    return a

def get_offset_contour(cs, offset):
    """
    Apply an offset to a list of contours to either expand or contract them.

    Parameters:
    - cs: A list of contours, where each contour is a list of points [(x, y), ...].
    - offset: The offset distance. Positive values expand the contour; negative values contract it.

    Returns:
    - A list of offset contours. Returns an empty list if an exception occurs.
    """
    try:
        pco = pyclipper.PyclipperOffset()
        pco.AddPaths(cs, pyclipper.JT_ROUND, pyclipper.ET_CLOSEDPOLYGON)
        ncs = pco.Execute(offset)
    except Exception as e:
        # Optionally log the exception for debugging purposes.
        return []
    return ncs

def intersect_area(r1, r2):
    """
    Calculate the contours of the intersection area between two regions using the Pyclipper library.

    Parameters:
    - r1: List of tuples/lists representing the contours of a region in layer i. Each contour is a list of (x, y) points.
    - r2: List of tuples/lists representing the contours of a region in layer i + 1. Each contour is a list of (x, y) points.

    Returns:
    - A list of contours representing the intersection area between r1 and r2. Each contour is a list of (x, y) points.
    - Returns None if an exception occurs during the operation, which could indicate invalid inputs or other errors.

    Note:
    - The function assumes `r1` and `r2` are valid contours that can be processed by Pyclipper. If one of the regions is a line
      or if the contours cannot be processed due to their format or values, an exception may be caught, and None is returned.
    - This function uses the Pyclipper library, which requires contours to be formatted as lists of points, where each point is
      a tuple or list of two integers (x, y). Pyclipper performs integer arithmetic, so input contours should be scaled appropriately
      if they contain floating-point coordinates.
    """
    try:
        pc = pyclipper.Pyclipper()
        # Add r1 as the clipping path and r2 as the subject path for intersection
        pc.AddPaths(pyclipper.scale_to_clipper(r1), pyclipper.PT_CLIP, True)
        pc.AddPaths(pyclipper.scale_to_clipper(r2), pyclipper.PT_SUBJECT, True)

        # Execute the intersection operation
        solution = pc.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD)

        # Scale back the solution to original coordinates if necessary
        return pyclipper.scale_from_clipper(solution)
    except Exception as e:
        # Optionally log the exception e for debugging purposes
        return None


def get_min_dist(b1, b2):
    """
    Calculate the minimum Euclidean distance between two contours.

    @param b1: List of arrays, each array is a contour of the 1st boundary.
    @param b2: List of arrays, each array is a contour of the 2nd boundary.
    @return: Tuple containing the index of the point in the first contour closest to the second contour,
             the index of the closest point in the second contour, and the minimum distance between these points.

    The function first combines all sub-contours within each main contour into a single array. Then, it calculates
    the pairwise Euclidean distances between all points in the first and second combined contours and finds the
    minimum distance. The indices of the points in both contours that are closest to each other, along with the
    minimum distance, are returned.
    """

    def combine_contour(b):
        """
        Combine multiple sub-contours into a single contour.

        @param b: List of arrays, where each array is a sub-contour.
        @return: A single array containing all points from the sub-contours.
        """
        cs = np.array([]).reshape(0, b[0].shape[1])  # Initialize an empty array with correct shape
        for idx in range(len(b)):
            cs = np.vstack((cs, b[idx]))  # Correctly stack the contours
        return cs

    # Combine the contours for both boundaries
    b1 = combine_contour(b1)
    b2 = combine_contour(b2)

    # Compute the pairwise Euclidean distance between all points in the two contours
    dist = scid.cdist(b1, b2, 'euclidean')

    # Find the minimum distance
    min_dist = np.min(dist)

    # Find the indices of the points in b1 and b2 that are closest to each other
    gId = np.argmin(dist)  # Global index of the minimum value in the distance matrix
    pid_c1 = int(gId / dist.shape[1])  # Calculate row index in b1
    pid_c2 = gId % dist.shape[1]  # Calculate column index in b2, corrected to use modulo for column calculation

    return pid_c1, pid_c2, min_dist
