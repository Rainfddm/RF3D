'''
Compute CSS point

example:
    kappa, smooth = compute_curve_css(c,3)
    css_idx = find_css_point(kappa)
'''
import numpy as np
from scipy.signal import savgol_filter

# A new version without using cv2.getGaussianKernel(M, sigma)
def get_gaussian_kernel(sigma, M):
    '''
    refer to https://cedar.buffalo.edu/~srihari/CSE555/Normal2.pdf
    '''
    if sigma <= 0:
        raise ValueError("Sigma must be greater than 0")
    if M % 2 == 0 or M < 1:
        raise ValueError("M must be an odd and positive integer")

    L = int((M - 1) / 2)
    sigma_sq = sigma ** 2
    sigma_quad = sigma_sq ** 2

    # Generate a range of x values
    x = np.linspace(-L, L, M)

    # Gaussian Kernel
    gaussian = (1 / (np.sqrt(2 * np.pi * sigma_sq))) * np.exp(-x**2 / (2 * sigma_sq))

    # First derivative of Gaussian
    dg = (-x / sigma_sq) * gaussian

    # Second derivative of Gaussian
    d2g = ((x**2 - sigma_sq) / sigma_quad) * gaussian

    # Normalizing the Gaussian Kernel
    gaussian /= np.sum(gaussian)

    return gaussian.reshape((1, M)), dg.reshape((1, M)), d2g.reshape((1, M))


def smooth_curve(curve, sigma, is_open = False):
    '''
    By refer to https://www.sciencedirect.com/science/article/pii/S0031320301000401
    According to the properties of convolution, the derivatives of g(x) * u(x) 
    can be calculated easily computed by g'(x) * u(x)
    '''
    M = round((10.0*sigma+1.0) / 2.0) * 2 - 1;
    assert(M % 2 == 1)
    g, dg, d2g = get_gaussian_kernel(sigma, M)
    X = curve[:,0]
    Y = curve[:,1]
    
    id_list = list(range(M))
    id_list = list(np.array(id_list) - int(M/2))
    id_list.reverse()
    xM = np.zeros( (M, len(X)) )
    yM = np.zeros( (M, len(X)) )
    row = 0
    for i in id_list:
        xM[row] = np.roll(X, i)
        yM[row] = np.roll(Y, i)
        row += 1     
    if(is_open):
        #todo: regulate xM, yM
        i=0
   
        
    gX  = np.vstack((np.sum(g.dot( xM), axis = 0), np.sum(g.dot(yM), axis = 0) ) ) 

    dX  = np.sum(dg.dot(xM), axis = 0)
    dY  = np.sum(dg.dot(yM), axis = 0)
    dXX = np.sum(d2g.dot(xM), axis = 0)
    dYY = np.sum(d2g.dot(yM), axis = 0)
    
    return gX.T, dX, dY, dXX, dYY
def compute_curve_css(curve, sigma, is_open=False):
    '''
    example:
       kappa, smooth = compute_curve_css(c,3)
    '''
   
    smooth, dX, dY, dXX, dYY = smooth_curve(curve, sigma)
    
    kappa = (dX*dYY - dXX*dY) / np.power(dX*dX + dY*dY, 1.5);
 
    return kappa, smooth

    
def find_css_point(kappa):
    idx_list = []
    for i in range(len(kappa)-1):
        if (kappa[i] < 0 and kappa[i+1] > 0) or (kappa[i] > 0 and kappa[i+1] < 0):
            idx_list.append(i)
    return idx_list
    
if __name__ == '__main__':
    
    pass