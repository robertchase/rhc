from rhc.file_util import normalize_path


def test_normalize_path():
    root_parent = normalize_path('relative/path.micro', parent='root/file')
    home_parent = normalize_path('relative/path.micro', parent='home/file')
    absolute = normalize_path('/absolute/path.micro', parent='home/file')

    assert root_parent == 'root/relative/path.micro'
    assert home_parent == 'home/relative/path.micro'
    assert absolute == '/absolute/path.micro'


def test_normalize_path_with_dots():
    path = 'os.path.dirname'
    answer = normalize_path(path)
    print(answer)
    assert answer[-18:] == 'os.py/path/dirname'