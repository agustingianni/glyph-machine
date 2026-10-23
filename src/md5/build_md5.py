#!/usr/bin/env python3
"""MD5 in Graphite bytecode. Host code only builds the font's program.

Input is U+E000 + 0..55 printable ASCII bytes + U+E001. The fixed framing
allows the empty message to have a glyph run; framing is not hashed.
"""
from pathlib import Path
import json
import os
import struct
import subprocess
import time

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables.S__i_l_f import assemble, disassemble
from ref_md5 import INIT, K, S

HERE = Path(__file__).resolve().parent
FONT = HERE / 'MD5Graphite.ttf'
# Five-by-seven hexadecimal outlines. Also used to decode browser pixels.
PIXELS = [
    ['01110','10001','10011','10101','11001','10001','01110'],
    ['00100','01100','00100','00100','00100','00100','01110'],
    ['01110','10001','00001','00010','00100','01000','11111'],
    ['11110','00001','00001','01110','00001','00001','11110'],
    ['00010','00110','01010','10010','11111','00010','00010'],
    ['11111','10000','10000','11110','00001','00001','11110'],
    ['01110','10000','10000','11110','10001','10001','01110'],
    ['11111','00001','00010','00100','01000','01000','01000'],
    ['01110','10001','10001','01110','10001','10001','01110'],
    ['01110','10001','10001','01111','00001','00001','01110'],
    ['01110','10001','10001','11111','10001','10001','10001'],
    ['10000','10000','10000','11110','10001','10001','11110'],
    ['00000','00000','01110','10000','10000','10001','01110'],
    ['00001','00001','00001','01111','10001','10001','01111'],
    ['01110','10001','10001','11111','10000','10000','01110'],
    ['01110','10001','10000','11100','10000','10000','10000'],
]


def u(n):
    return f'(user{n} & 65535)'


def xor(a, b):
    return f'(({a} & ~{b}) | (~{a} & {b}))'


def fn(i, half):
    b, c, d = (u(n + half) for n in (35, 37, 39))
    if i < 16: return f'(({b} & {c}) | (~{b} & {d}))'
    if i < 32: return f'(({d} & {b}) | (~{d} & {c}))'
    if i < 48: return xor(xor(b, c), d)
    return xor(c, f'({b} | ~{d})')


def rot(shift, half):
    if shift >= 16:
        half = 1 - half
        shift -= 16
    a, b = u(41 + half), u(42 - half)
    if not shift: return a
    return f'((({a} * {1 << shift}) & 65535) | ({b} / {1 << (16-shift)}))'


def features(names):
    lines = ['Bidi = false;', 'table(glyph)']
    for gid, name in enumerate(names[1:], 1):
        lines.append(f'{name} = glyphid({gid});')
        if name.startswith('c') and len(name) == 3:
            lines.append(f'{name}.byte = {int(name[1:], 16)};')
    lines += ['chars = (' + ','.join(f'c{c:02x}' for c in range(32,127)) + ');',
              'digits = (' + ','.join(f'd{n:x}' for n in range(16)) + ');',
              'slots = (' + ','.join(f'q{n}' for n in range(32)) + ');',
              'endtable;', 'table(substitution)', 'pass(1)']
    # Each length has one rule, not one precomputed hash. Expressions assemble
    # the little-endian half words directly from the matched character slots.
    for length in range(55, -1, -1):
        attrs = []
        for half in range(32):
            parts = []
            for k in range(2):
                pos = half * 2 + k
                if pos < length: part = f'@{pos+2}.byte'
                elif pos == length: part = '128'
                elif pos == 56: part = str(length * 8 & 255)
                elif pos == 57: part = str(length * 8 >> 8)
                else: continue
                parts.append(part if k == 0 else f'({part} * 256)')
            attrs.append(f'user{half+1} = ' + (' + '.join(parts) or '0'))
        for w, initial in enumerate(INIT):
            attrs += [f'user{33+2*w} = {initial & 65535}', f'user{34+2*w} = {initial >> 16}']
        attrs += ['user41 = 0', 'user42 = 0', 'user43 = 0', 'user44 = 0']
        lhs = 'start ' + 'chars ' * length + 'end'
        rhs = 'work:(' + ' '.join(str(i) for i in range(1,length+3)) + ') {' + '; '.join(attrs) + '} ' + '_ ' * (length+1)
        lines.append(f'{lhs} > {rhs};')
    lines += ['endpass;', 'pass(2) {MaxRuleLoop = 150}']
    for i in range(64):
        g = i if i < 16 else (5*i+1)%16 if i < 32 else (3*i+5)%16 if i < 48 else 7*i%16
        lo = f'({u(33)} + ({fn(i,0)} & 65535) + {u(1+2*g)} + {K[i]&65535})'
        hi = f'({u(34)} + ({fn(i,1)} & 65535) + {u(2+2*g)} + {K[i]>>16} + {lo}/65536)'
        lines.append(f'work > @1 {{user41 = {lo} & 65535; user42 = {hi} & 65535; user44 = 1}} / ^ _ {{user43 == {i} && user44 == 0}};')
        rlo, rhi = rot(S[i], 0), rot(S[i], 1)
        blo = f'({u(35)} + {rlo})'
        bhi = f'({u(36)} + {rhi} + {blo}/65536)'
        # Read-before-write ordering also works for interpreters without a
        # snapshot of attributes when updating this single slot.
        attrs = [f'user33 = user39', f'user34 = user40',
                 'user39 = user37', 'user40 = user38',
                 'user37 = user35', 'user38 = user36',
                 f'user36 = {bhi} & 65535', f'user35 = {blo} & 65535',
                 f'user43 = {i+1}', 'user44 = 0']
        lines.append('work > @1 {' + '; '.join(attrs) + f'}} / ^ _ {{user43 == {i} && user44 == 1}};')
    lines += ['endpass;', 'pass(3)']
    attrs=[]
    for w, initial in enumerate(INIT):
        n=33+2*w
        low=f'({u(n)} + {initial & 65535})'
        high=f'({u(n+1)} + {initial >> 16} + {low}/65536)'
        attrs += [f'user{n+1} = {high} & 65535', f'user{n} = {low} & 65535']
    lines.append('work > @1 {' + '; '.join(attrs) + '};')
    lines += ['endpass;', 'pass(4)']
    output=[]
    for j in range(32):
        # Byte order is little endian; nibble order within each byte is high
        # then low. Digest halves live in user33..user40.
        byte=j//2; half=33+byte//2; shift=(byte%2)*8 + (4 if j%2==0 else 0)
        output.append(f'q{j}:1 {{user1 = (@1.user{half} & 65535) / {1<<shift} & 15}}')
    lines.append('work ' + '_ '*31 + '> ' + ' '.join(output) + ';')
    lines += ['endpass;', 'pass(5)']
    for n in range(16): lines.append(f'slots > d{n:x} / _ {{user1 == {n}}};')
    lines += ['endpass;', 'endtable;']
    return '\n'.join(lines)+'\n'


def fix_compiler_opcodes(font_path):
    """Correct grcompiler 5.2.1 AND/OR opcodes without reserializing Silf."""
    font = TTFont(font_path)
    raw = bytearray(font.getTableData('Silf'))
    for i,silf in enumerate(font['Silf'].silfs):
        offset=struct.unpack_from('>I',raw,12+4*i)[0]
        for j,p in enumerate(silf.passes):
            for codes,start,end in [(p.actions,p.aCode,silf.oPasses[j+1]),
                                    (p.ruleConstraints,p.rcCode,p.aCode),
                                    ([p.passConstraints],p.pcCode,p.rcCode)]:
                cursor=offset+start
                for code in codes:
                    if not code: continue
                    where=raw.find(code,cursor,offset+end)
                    assert where>=0,(i,j,start)
                    instructions=disassemble(code)
                    fixed=assemble([{'BITAND':'BITOR','BITOR':'BITAND'}.get(op,op) for op in instructions])
                    assert len(fixed)==len(code)
                    raw[where:where+len(code)]=fixed
                    cursor=where+len(code)
    table=DefaultTable('Silf');table.data=bytes(raw);font['Silf']=table
    font.save(font_path)


def build():
    t=time.perf_counter()
    # A final zero-width glyph forces full horizontal metrics for the digits.
    # Graphite2's compressed hmtx reader rejects the last short metric entry.
    names=['.notdef']+[f'c{c:02x}' for c in range(32,127)]+['start','end','work']+[f'q{i}' for i in range(32)]+[f'd{n:x}' for n in range(16)]+['guard']
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(names)
    fb.setupCharacterMap({**{c:f'c{c:02x}' for c in range(32,127)},0xe000:'start',0xe001:'end'})
    glyphs={}
    for name in names:
        pen=TTGlyphPen(None)
        if name.startswith('d') and len(name)==2:
            for row,bits in enumerate(PIXELS[int(name[1],16)]):
                for col,bit in enumerate(bits):
                    if bit=='1':
                        x,y=col*100+10,(6-row)*100+10
                        pen.moveTo((x,y));pen.lineTo((x,y+80));pen.lineTo((x+80,y+80));pen.lineTo((x+80,y));pen.closePath()
        glyphs[name]=pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n:(600 if n.startswith('d') and len(n)==2 else 0,getattr(glyphs[n],'xMin',0)) for n in names})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    fb.setupNameTable({'familyName':'MD5Graphite','styleName':'Regular','uniqueFontIdentifier':'MD5Graphite-1','fullName':'MD5Graphite','psName':'MD5Graphite'})
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
    fb.setupPost();fb.setupMaxp();fb.save(HERE/'MD5Base.ttf')
    (HERE/'MD5Graphite.gdl').write_text(features(names))
    env=dict(os.environ,GDLPP=os.environ.get('GDLPP','/tmp/md5-grcompiler/build/preprocessor/gdlpp'))
    subprocess.run([os.environ.get('GRCOMPILER','/tmp/md5-grcompiler/build/compiler/grcompiler'),'-q','-e',str(HERE/'md5_errors.txt'),str(HERE/'MD5Graphite.gdl'),str(HERE/'MD5Base.ttf'),str(FONT)],check=True,env=env)
    fix_compiler_opcodes(FONT)
    result={'font':FONT.name,'bytes':FONT.stat().st_size,'build_seconds':time.perf_counter()-t,'engine':'Graphite2 / Firefox','maximum_input_bytes':55}
    (HERE/'build_results.json').write_text(json.dumps(result,indent=2)+'\n')
    (HERE/'digit_pixels.json').write_text(json.dumps(PIXELS)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':build()
