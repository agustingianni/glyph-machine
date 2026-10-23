#!/usr/bin/env python3
"""Full Safari MD5 font: framed ASCII -> padded tape -> MD5 -> 32 hex glyphs.

The host generates tables and constants only. No message-dependent work is
required outside the font. Safari uses four extra fixed, invisible boundary
glyphs to accommodate CoreText's expansion bound on very short input.
"""
import argparse
import json
from pathlib import Path
import time
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot
from build_md5 import PIXELS
from ref_md5 import INIT,S
from safari_compress import KINDS,glyph,first_sum,copy_rotation,second_sum,feedforward
from safari_probe import action,contextual

HERE=Path(__file__).resolve().parent
CHARS=range(32,127)


def insert_tape():
    """Insert fixed initial registers, empty message/temporaries, and display."""
    tape=[f'q{i}' for i in range(32)]
    for j in range(32):
        for kind in KINDS:
            bit=(INIT[int(kind[1])]>>j)&1 if kind.startswith('x') else 0
            tape.append(glyph(kind,j,bit))
    # Each table inserts immediately after the start boundary. Reverse the
    # chunk order so the resulting tape is in forward order.
    for chunk in reversed([tape[i:i+31] for i in range(0,len(tape),31)]):
        sub=ot.InsertionMorph();t=ot.AATStateTable();sub.StateTable=t
        t.GlyphClasses={'start':4}
        for _ in range(2):
            row=ot.AATState()
            for cls in range(5):
                a=ot.InsertionMorphAction()
                if cls==4:a.CurrentInsertionAction=chunk
                row.Transitions[cls]=a
            t.States.append(row)
        yield sub


def input_bit(byte,bit):
    """Copy an actual ASCII bit or derive a padding/length bit from the count.

    The message slot precedes the source text. Mark it, count characters,
    then write its value upon reaching the selected character or end marker.
    """
    word,j=byte//4,(byte%4)*8+bit
    targets=[glyph(f'm{word}',j,b) for b in (0,1)]
    classes={**{f'c{c:02x}':5+((c>>bit)&1) for c in CHARS},
             targets[0]:4,targets[1]:4,'end':7}
    max_count=min(byte,55) if byte<56 else 55
    done=max_count+3
    sub,t=contextual(classes,done+1)
    t.PerGlyphLookups=[{name:targets[b] for name in targets} for b in (0,1)]
    t.States[0].Transitions[4]=action(2,set_mark=True)
    t.States[1].Transitions[4]=action(2,set_mark=True)
    for count in range(max_count+1):
        state=2+count
        for b in (0,1):
            if byte<56 and count==byte:
                t.States[state].Transitions[5+b]=action(done,mark=b)
            else:
                t.States[state].Transitions[5+b]=action(min(state+1,done))
        if byte<56:
            value=1 if byte==count and bit==7 else 0
        else:
            value=((count*8)>>(8*(byte-56)+bit))&1
        t.States[state].Transitions[7]=action(mark=value)
    for cls in (1,2,5,6):t.States[done].Transitions[cls]=action(done)
    return sub


def output_nibble(n):
    word=n//8;byte=(n%8)//2;first=byte*8+(4 if n%2==0 else 0)
    classes={f'q{n}':4}
    for j in range(first,first+4):
        for b in (0,1):classes[glyph(f'x{word}',j,b)]=5+b
    # A binary trie stores the low 0..3 bits of the nibble in machine state.
    keys=[None,None]+[(depth,value) for depth in range(4) for value in range(1<<depth)]
    index={key:s for s,key in enumerate(keys) if key is not None}
    sub,t=contextual(classes,len(keys))
    t.PerGlyphLookups=[{f'q{n}':f'd{v:x}'} for v in range(16)]
    for s in (0,1):t.States[s].Transitions[4]=action(index[(0,0)],set_mark=True)
    for state,key in enumerate(keys):
        if key is None:continue
        depth,value=key
        for b in (0,1):
            new=value+(b<<depth)
            t.States[state].Transitions[5+b]=action(index[(depth+1,new)]) if depth<3 else action(mark=new)
    return sub


def build(input_only=False):
    begin=time.perf_counter()
    names=['.notdef','start','end','boundaryPad']+[f'c{c:02x}' for c in CHARS]
    names += [f'q{i}' for i in range(32)]
    names += [glyph(kind,j,b) for kind in KINDS for j in range(32) for b in (0,1)]
    names += [f'd{v:x}' for v in range(16)]+['guard']
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(names)
    fb.setupCharacterMap({**{c:f'c{c:02x}' for c in CHARS},0xe000:'start',0xe001:'end',0xe002:'boundaryPad'})
    glyphs={}
    for name in names:
        pen=TTGlyphPen(None)
        if name.startswith('d') and len(name)==2:
            for row,bits in enumerate(PIXELS[int(name[1],16)]):
                for col,b in enumerate(bits):
                    if b=='1':
                        x,y=col*100+10,(6-row)*100+10
                        pen.moveTo((x,y));pen.lineTo((x,y+80));pen.lineTo((x+80,y+80));pen.lineTo((x+80,y));pen.closePath()
        glyphs[name]=pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n:(600 if n.startswith('d') and len(n)==2 else 0,getattr(glyphs[n],'xMin',0)) for n in names})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    family='MD5SafariInput' if input_only else 'MD5Safari'
    fb.setupNameTable({'familyName':family,'styleName':'Regular','uniqueFontIdentifier':family+'-1','fullName':family,'psName':family})
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);fb.setupPost();fb.setupMaxp()
    chain=ot.MorxChain();chain.DefaultFlags=1;chain.MorphFeature=[];chain.MorphSubtable=[]
    def add(body):
        sub=ot.MorxSubtable();sub.ProcessingOrder='LayoutOrder';sub.TextDirection='Horizontal';sub.Reserved=0;sub.SubFeatureFlags=1;sub.SubStruct=body
        chain.MorphSubtable.append(sub)
    for table in insert_tape():add(table)
    for byte in range(56):
        for bit in range(8):add(input_bit(byte,bit))
    # At most 440 bits: only bits 3..8 of the encoded length can be nonzero.
    for bit in range(3,8):add(input_bit(56,bit))
    add(input_bit(57,0))
    input_tables=len(chain.MorphSubtable)
    if not input_only:
        for i in range(64):
            add(first_sum(i))
            for j in range(32):add(copy_rotation((j-S[i])%32,j))
            add(second_sum(i))
        for word in range(4):add(feedforward(word))
        for n in range(32):add(output_nibble(n))
    table=newTable('morx');table.table=ot.morx();table.table.Version=2;table.table.Reserved=0;table.table.MorphChain=[chain];fb.font['morx']=table
    output=HERE/(family+'.ttf');fb.save(output)
    result={'font':output.name,'bytes':output.stat().st_size,'subtables':len(chain.MorphSubtable),'input_subtables':input_tables,'build_seconds':time.perf_counter()-begin,'maximum_input_bytes':55,'scope':'full framed printable-ASCII MD5' if not input_only else 'input assembly only'}
    (HERE/('safari_input_build_results.json' if input_only else 'safari_full_build_results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input-only',action='store_true')
    build(parser.parse_args().input_only)
