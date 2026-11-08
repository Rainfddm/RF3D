import os,sys,time
import logging
import psutil
import numpy as np
import serial
from pathlib import Path
##############修改部分################
import glob
class suErrorWithDetails(Exception):
    def __init__(self, filename, message):
        self.filename = filename
        self.message = message
        super().__init__(self.message)
######################################

def unimplemented(func):
    '''
    A decorator function for print the current running function's name
    Just for the debug process.
    '''
    def wrap_func(*args, **kwargs):
        logging.info('{}({}) is not implemented.'.format(func.__name__, args))
        func(*args, **kwargs)
    return wrap_func


def get_abs_file_name(filename):
    # Check if the filename is an absolute path
    # return absolute path
    # @filename absolute path or relative path
    if os.path.isabs(filename):
        # If it's an absolute path, return as is
        return filename
    else:
        # If it's a relative path, convert to an absolute path
        current_dir = os.getcwd()
        # Combine the current directory with the relative path
        filename = os.path.join(current_dir, filename)
        return filename


def find_stl_file(stl_filename, parent_levels):
    """
    Find the specified .stl file in the parent's ... parent's 'Models' directory,
    navigating up a given number of parent directories.

    Parameters:
    - stl_filename: The name of the .stl file to find (e.g., 'Banshou-bigbig.stl').
    - parent_levels: The number of parent levels to navigate up.

    Raises:
    - ShuErrorWithDetails: If the file not exist.
    Returns:
    The full path to the .stl file if found, otherwise a message indicating it does not exist.
    """
    # Step 1: Get the directory of the current script
    #script_dir = Path(__file__).parent
    current_dir = Path(os.getcwd())

    # Step 2: Navigate up the specified number of directories
    target_dir = current_dir
    for _ in range(parent_levels):
        target_dir = target_dir.parent

    # Step 3: Search within the 'Models' directory for the .stl file
    models_dir = target_dir / 'Models'
    stl_file_path = models_dir / stl_filename
    print(stl_file_path)

    # Step 4: Check if the .stl file exists and return its path
    if stl_file_path.exists():
        return str(stl_file_path)
    else:
        raise suErrorWithDetails(stl_filename, f"The specified .stl file ({stl_filename}) does not exist.")


def generate_RGB_list(N):
    """
    Generate N color list
    """
    import colorsys
    HSV_tuples = [(x * 1.0 / N, 0.8, 0.9) for x in range(N)]
    RGB_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), HSV_tuples)
    rgb_list = tuple(RGB_tuples)
    return np.array(rgb_list) * 255


def show_memory_info(hint):
    '''
    Show memory used by current 
    '''
    pid = os.getpid()
    p = psutil.Process(pid)

    info = p.memory_full_info()
    memory = info.uss / 1024. / 1024
    logging.info('{} memory used: {} MB'.format(hint, memory))


def list_serial_ports(baudrate=250000):
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(10)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port, baudrate, timeout=10)
            time.sleep(2)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result


def progress_callback(value, algo_name="", bar_length=40):
    """
    Display a text-based progress bar.

    :param progress: Current progress as a percentage.
    :param bar_length: Length of the progress bar in characters.
    """
    filled_length = int(round(bar_length * value / 100))
    bar = '#' * filled_length + '-' * (bar_length - filled_length)

    # \r is used to move the cursor back to the start of the line
    print(f'\r {algo_name}: |{bar}| {value:.2f}%', end='')

    # Print a new line when progress is complete
    if value == 100:
        print()


def analyze_structure(obj, level=0):
    indent = ' ' * 4 * level
    if isinstance(obj, dict):
        print(f"{indent}Dictionary: {len(obj)} items")
        for key, value in obj.items():
            print(f"{indent} Key: {key}, Value type:")
            analyze_structure(value, level + 1)
    elif isinstance(obj, (list, tuple)):
        container_type = "List" if isinstance(obj, list) else "Tuple"
        print(f"{indent}{container_type}: {len(obj)} items")
        for i, item in enumerate(obj):
            print(f"{indent} Item {i}, Type:")
            analyze_structure(item, level + 1)
    elif isinstance(obj, np.ndarray):
        print(f"{indent}NumPy Array: Shape {obj.shape}, Dtype {obj.dtype}")
    else:
        print(f"{indent}Type: {type(obj).__name__}")


def inspect_data(data, name="data", max_items=5, max_depth=3, current_depth=0):
    """
    Inspect and print information about the given data structure.

    :param data: The data structure to inspect
    :param name: Name of the data structure (for printing purposes)
    :param max_items: Maximum number of items to print for sequences
    :param max_depth: Maximum depth to traverse for nested structures
    :param current_depth: Current depth in the nested structure (used internally)
    """
    print(f"\n{'  ' * current_depth}Inspecting: {name}")
    print(f"{'  ' * current_depth}Type: {type(data)}")
    print(f"{'  ' * current_depth}Memory Size: {sys.getsizeof(data)} bytes")

    if current_depth >= max_depth:
        print(f"{'  ' * current_depth}Max depth reached. Stopping further inspection.")
        return

    if isinstance(data, np.ndarray):
        print(f"{'  ' * current_depth}Shape: {data.shape}")
        print(f"{'  ' * current_depth}Dtype: {data.dtype}")
        print(f"{'  ' * current_depth}Dimensions: {data.ndim}")
        print(f"{'  ' * current_depth}First {max_items} elements:")
        print(data.flatten()[:max_items])

    elif isinstance(data, (list, tuple)):
        print(f"{'  ' * current_depth}Length: {len(data)}")
        print(f"{'  ' * current_depth}First {min(max_items, len(data))} elements:")
        for i, item in enumerate(data[:max_items]):
            if isinstance(item, (list, tuple, dict, np.ndarray)):
                inspect_data(item, f"{name}[{i}]", max_items, max_depth, current_depth + 1)
            else:
                print(f"{'  ' * (current_depth + 1)}{item}")

    elif isinstance(data, dict):
        print(f"{'  ' * current_depth}Number of keys: {len(data)}")
        print(f"{'  ' * current_depth}Keys: {', '.join(str(k) for k in list(data.keys())[:max_items])}")
        print(f"{'  ' * current_depth}First {min(max_items, len(data))} items:")
        for i, (key, value) in enumerate(list(data.items())[:max_items]):
            if isinstance(value, (list, tuple, dict, np.ndarray)):
                inspect_data(value, f"{name}[{key}]", max_items, max_depth, current_depth + 1)
            else:
                print(f"{'  ' * (current_depth + 1)}{key}: {value}")

    else:
        print(f"{'  ' * current_depth}Value: {data}")


if __name__ == '__main__':
    print("Begine...")
    # set stream to file
    # logging.basicConfig(level=logging.DEBUG,
    #                     format='%(asctime)s %(message)s',
    #                     datefmt='%a, %d %b %Y %H:%M:%S',
    #                     filename='/domain-result.log',
    #                     filemode='w')
    # set stream to screen
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(message)s',
                        datefmt='%a, %d %b %Y %H:%M:%S',
                        stream=sys.stdout)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    show_memory_info('After generated list_1')
    logging.info(generate_RGB_list(4))

    logging.info(list_serial_ports())

    logging.info(get_abs_file_name('./common.py'))
