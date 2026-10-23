#!/usr/bin/env python3
"""AAT morx feasibility: full MD5 compression on a preassembled bit tape.

This research font does NOT yet accept raw ASCII: its harness assembles the
padded message and initial state. All 64 nonlinear rounds execute in morx.
"""
from pathlib import Path
import json
import time
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot
from ref_md5 import K,S,INIT,pad
from safari_probe import contextual,action

HERE=Path(__file__).resolve().parent
KINDS=['x0','x1','x2','x3']+[f'm{i}' for i in range(16)]+['t','r']


def glyph(kind,j,bit):return f'{kind}_{j}_{bit}'


def value_map(kind,value):
    return {glyph(kind,j,b):glyph(kind,j,value) for j in range(32) for b in (0,1)}


def bool_fn(i,b,c,d):
    if i<16:return (b&c)|((1-b)&d)
    if i<32:return (d&b)|((1-d)&c)
    if i<48:return b^c^d
    return c^(b|(1-d))


def first_sum(i):
    g=i if i<16 else (5*i+1)%16 if i<32 else (3*i+5)%16 if i<48 else 7*i%16
    classes={}
    for j in range(32):
        for b in (0,1):
            for x in range(4):classes[glyph(f'x{x}',j,b)]=4+2*x+b
            classes[glyph(f'm{g}',j,b)]=12+b
            classes[glyph('t',j,b)]=14+((K[i]>>j)&1)
    # Keys: carry plus the register prefix, then partial A+F, then A+F+M.
    keys=[(0,()),(0,()),(1,()),(2,()),(3,())]
    for c in range(4):
        for n in (1,2,3):
            keys += [(c,tuple((v>>k)&1 for k in range(n))) for v in range(1<<n)]
        keys += [(c,('partial',v)) for v in range(3)]
        keys += [(c,('sum',v)) for v in range(4)]
    index={key:n for n,key in enumerate(keys) if n!=1}
    sub,t=contextual(classes,len(keys));t.PerGlyphLookups=[value_map('t',0),value_map('t',1)]
    roles=[(-i+k)%4 for k in range(4)]
    for state,(carry,prefix) in enumerate(keys):
        if not prefix or isinstance(prefix[0],int):
            n=len(prefix)
            for b in (0,1):
                bits=prefix+(b,)
                if n<3:key=(carry,bits)
                else:
                    a,bb,c,d=[bits[r] for r in roles]
                    key=(carry,('partial',a+bool_fn(i,bb,c,d)))
                t.States[state].Transitions[4+2*n+b]=action(index[key])
        elif prefix[0]=='partial':
            for b in (0,1):
                t.States[state].Transitions[12+b]=action(index[(carry,('sum',prefix[1]+b))])
        else:
            for k in (0,1):
                total=carry+prefix[1]+k
                t.States[state].Transitions[14+k]=action(index[(total//2,())],current=total&1)
    return sub


def copy_rotation(source,target):
    # One tiny table per bit. Distance does not occur in the table encoding.
    src=glyph('t',source,0),glyph('t',source,1)
    dst=glyph('r',target,0),glyph('r',target,1)
    sub,t=contextual({src[0]:4,src[1]:5,dst[0]:6,dst[1]:6},4)
    t.PerGlyphLookups=[{name:dst[v] for name in dst} for v in (0,1)]
    if source<target:
        for state in range(4):
            for b in (0,1):t.States[state].Transitions[4+b]=action(2+b)
        for b in (0,1):t.States[2+b].Transitions[6]=action(current=b)
    else:
        for state in range(4):t.States[state].Transitions[6]=action(2,set_mark=True)
        for b in (0,1):t.States[2].Transitions[4+b]=action(mark=b)
    return sub


def second_sum(i):
    a,b=(-i)%4,(1-i)%4
    classes={}
    for j in range(32):
        for bit in (0,1):
            classes[glyph(f'x{a}',j,bit)]=4
            classes[glyph(f'x{b}',j,bit)]=5+bit
            classes[glyph('r',j,bit)]=7+bit
    sub,t=contextual(classes,7);t.PerGlyphLookups=[value_map(f'x{a}',v) for v in (0,1)]
    keys=[(0,None),(0,None),(1,None),(0,0),(0,1),(1,0),(1,1)]
    index={key:n for n,key in enumerate(keys) if n!=1}
    for state,(carry,bvalue) in enumerate(keys):
        t.States[state].Transitions[4]=action(state,set_mark=True)
        for bit in (0,1):t.States[state].Transitions[5+bit]=action(index[(carry,bit)])
        if bvalue is not None:
            for bit in (0,1):
                total=carry+bvalue+bit
                t.States[state].Transitions[7+bit]=action(index[(total//2,None)],mark=total&1)
    return sub


def feedforward(word):
    kind=f'x{word}'
    classes={glyph(kind,j,b):4+2*((INIT[word]>>j)&1)+b for j in range(32) for b in (0,1)}
    sub,t=contextual(classes,3);t.PerGlyphLookups=[value_map(kind,v) for v in (0,1)]
    for state,carry in enumerate((0,0,1)):
        for k in (0,1):
            for bit in (0,1):
                total=carry+k+bit
                t.States[state].Transitions[4+2*k+bit]=action(2 if total>=2 else 0,current=total&1)
    return sub


def build():
    begin=time.perf_counter()
    names=['.notdef']+[glyph(kind,j,b) for kind in KINDS for j in range(32) for b in (0,1)]+['marker','guard']
    cmap={0xe000+i:name for i,name in enumerate(names[1:-1])}
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(names);fb.setupCharacterMap(cmap)
    glyphs={}
    for name in names:
        pen=TTGlyphPen(None);x=None
        if name.startswith('x'):
            kind,j,b=name.split('_')
            if b=='1':x=(int(kind[1])*32+int(j))*100+10
        elif name=='marker':x=12810
        if x is not None:
            pen.moveTo((x,100));pen.lineTo((x,600));pen.lineTo((x+80,600));pen.lineTo((x+80,100));pen.closePath()
        glyphs[name]=pen.glyph()
    fb.setupGlyf(glyphs);fb.setupHorizontalMetrics({n:(0,getattr(glyphs[n],'xMin',0)) for n in names})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    fb.setupNameTable({'familyName':'SafariMD5Compression','styleName':'Regular','uniqueFontIdentifier':'SafariMD5Compression','fullName':'SafariMD5Compression','psName':'SafariMD5Compression'})
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);fb.setupPost();fb.setupMaxp()
    chain=ot.MorxChain();chain.DefaultFlags=1;chain.MorphFeature=[];chain.MorphSubtable=[]
    def add(body):
        sub=ot.MorxSubtable();sub.ProcessingOrder='LayoutOrder';sub.TextDirection='Horizontal';sub.Reserved=0;sub.SubFeatureFlags=1;sub.SubStruct=body
        chain.MorphSubtable.append(sub)
    for i in range(64):
        add(first_sum(i))
        for target in range(32):add(copy_rotation((target-S[i])%32,target))
        add(second_sum(i))
    for word in range(4):add(feedforward(word))
    table=newTable('morx');table.table=ot.morx();table.table.Version=2;table.table.Reserved=0;table.table.MorphChain=[chain];fb.font['morx']=table
    output=HERE/'SafariMD5Compression.ttf';fb.save(output)
    (HERE/'safari_encoding.json').write_text(json.dumps({name:code for code,name in cmap.items()})+'\n')
    result={'font':output.name,'bytes':output.stat().st_size,'subtables':len(chain.MorphSubtable),'build_seconds':time.perf_counter()-begin,'scope':'compression only; harness pads and encodes input'}
    (HERE/'safari_build_results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


def encode(message,encoding):
    block=pad(message)
    if len(block)!=64:raise ValueError('Single block only')
    words=[int.from_bytes(block[i:i+4],'little') for i in range(0,64,4)]
    text=[]
    for j in range(32):
        for kind in KINDS:
            value=INIT[int(kind[1])] if kind.startswith('x') else words[int(kind[1:])] if kind.startswith('m') else 0
            text.append(chr(encoding[glyph(kind,j,(value>>j)&1)]))
    text.append(chr(encoding['marker']));return ''.join(text)


if __name__=='__main__':build()
