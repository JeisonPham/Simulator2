import open3d.visualization.gui as gui
import time


def Open3DErrorProtect(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            print(str(e))
            gui.Application.instance.quit()

    return wrapper


def timeit(func):
    def wrapper(*args, **kwargs):
        now = time.time()
        result = func(*args, **kwargs)
        print(time.time() - now)
        return result

    return wrapper
