"""util.py — tiny IO helpers so file handles always close (ruff SIM115 sweep, 0.8.2).

`load_json(p)` leaks a handle until GC; these one-liners are the package's
 sanctioned way to read files and keep the lint rule honest without scattering `with`.
"""
import json


def read_text(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def read_bytes(path):
    with open(path, 'rb') as f:
        return f.read()


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def dump_json(path, data):
    import os
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
    os.replace(tmp, path)
