import imp
import os


def normalize_path(path, filetype=None):
    ''' Convert dot-separated paths to directory paths '''
    if '.' in path and os.path.sep not in path:  # path is dot separated
        parts = path.split('.')
        extension = ''
        if filetype and parts[-1] == filetype:
            parts = parts[:-1]  # save '.filetype' extension if exists
            extension = '.' + filetype
        if len(parts) > 1:
            sink, path, sink = imp.find_module(parts[0])  # use module-based location
            path = os.path.join(path, *parts[1:]) + extension
    elif not path.startswith(os.path.sep):  # path is relative
        path = os.path.join(os.getcwd(), path)
    return path
