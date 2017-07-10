import imp
import os


def normalize_path(path, filetype=None, parent=None):
    ''' Convert dot-separated paths to directory paths

    Paths are relative to the parent file or the cwd if
    no parent is available.
    '''
    if not isinstance(path, str):
        return path
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
        if parent:
            parent_dir = os.path.dirname(parent)
        else:
            parent_dir = os.getcwd()
        path = os.path.join(parent_dir, path)
    return path
