#!/usr/bin/env python3
"""Build the pinned GDL compiler with all 64 supported variable names exposed."""
from pathlib import Path
import os
import subprocess

SOURCE = Path(os.environ.get('GRC_SOURCE', '/tmp/md5-grcompiler'))
COMMIT = '99253db8f45671faef59a4f3d92102c4fddd8e80'


def main():
    if not SOURCE.exists():
        subprocess.run(['git','clone','https://github.com/silnrsi/grcompiler.git',str(SOURCE)],check=True)
        subprocess.run(['git','-C',str(SOURCE),'checkout',COMMIT],check=True)
    actual=subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()
    if actual != COMMIT:
        raise RuntimeError(f'Expected compiler {COMMIT}, found {actual}')
    path=SOURCE/'compiler/GrcSymTable.cpp'
    source=path.read_text()
    marker='\tPreDefineSymbol(GrcStructName("user16"),\tkst, kexptNumber);'
    if 'GrcStructName("user64")' not in source:
        assert marker in source
        extra=''.join(f'\n\tPreDefineSymbol(GrcStructName("user{i}"), kst, kexptNumber);' for i in range(17,65))
        path.write_text(source.replace(marker,marker+extra))
    subprocess.run(['cmake','-S',str(SOURCE),'-B',str(SOURCE/'build'),'-DCMAKE_PREFIX_PATH=/opt/homebrew/opt/icu4c'],check=True)
    subprocess.run(['cmake','--build',str(SOURCE/'build'),'-j','8'],check=True)


if __name__=='__main__':main()
