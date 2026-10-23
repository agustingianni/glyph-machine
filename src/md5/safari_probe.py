#!/usr/bin/env python3
"""Probe Safari's AAT morx arithmetic, distant writes, and glyph insertion."""
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables import otTables as ot

HERE=Path(__file__).resolve().parent


def action(state=0,current=0xffff,mark=0xffff,set_mark=False):
    a=ot.ContextualMorphAction();a.NewState=state;a.CurrentIndex=current
    a.MarkIndex=mark;a.SetMark=set_mark
    return a


def contextual(classes,count):
    table=ot.AATStateTable();table.GlyphClasses=classes
    for state in range(count):
        row=ot.AATState()
        for cls in range(max(classes.values())+1):
            row.Transitions[cls]=action(state if cls in (1,2) else 0)
        table.States.append(row)
    sub=ot.ContextualMorph();sub.StateTable=table
    return sub,table


def build():
    names=['.notdef','a0','a1','b0','b1','gap','targetBack','targetForward','source0','source1','insert','r0','r1','guard']
    cmap={48:'a0',49:'a1',50:'b0',51:'b1',120:'gap',116:'targetBack',122:'targetForward',117:'source0',118:'source1',105:'insert'}
    fb=FontBuilder(1000,isTTF=True);fb.setupGlyphOrder(names);fb.setupCharacterMap(cmap)
    glyphs={}
    for name in names:
        pen=TTGlyphPen(None)
        if name in ('r0','r1'):
            top=200 if name=='r0' else 600
            pen.moveTo((100,100));pen.lineTo((100,top));pen.lineTo((400,top));pen.lineTo((400,100));pen.closePath()
        glyphs[name]=pen.glyph()
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n:(600 if n in ('r0','r1') else 0,getattr(glyphs[n],'xMin',0)) for n in names})
    fb.setupHorizontalHeader(ascent=800,descent=-200)
    fb.setupNameTable({'familyName':'SafariComputeProbe','styleName':'Regular','uniqueFontIdentifier':'SafariComputeProbe','fullName':'SafariComputeProbe','psName':'SafariComputeProbe'})
    fb.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200);fb.setupPost();fb.setupMaxp()
    # The carry occupies the finite machine state, not a backtrack string.
    adder,t=contextual({'a0':4,'a1':5,'b0':6,'b1':7},6)
    t.PerGlyphLookups=[{'b0':'r0','b1':'r0'},{'b0':'r1','b1':'r1'}]
    for state,carry in [(0,0),(1,0),(2,1)]:
        t.States[state].Transitions[4]=action(3+carry)
        t.States[state].Transitions[5]=action(4+carry)
    for partial in range(3):
        for bit in (0,1):
            total=partial+bit
            t.States[3+partial].Transitions[6+bit]=action(2 if total>=2 else 0,current=total&1)
    # Mark an earlier target, skip any amount of intervening tape, then write
    # the source bit back into that marked glyph.
    back,t=contextual({'targetBack':4,'source0':5,'source1':6},3)
    t.PerGlyphLookups=[{'targetBack':'r0'},{'targetBack':'r1'}]
    for state in range(3):t.States[state].Transitions[4]=action(2,set_mark=True)
    for bit in (0,1):t.States[2].Transitions[5+bit]=action(mark=bit)
    # Source before target: retain one bit in state across the gap.
    forward,t=contextual({'targetForward':4,'source0':5,'source1':6},4)
    t.PerGlyphLookups=[{'targetForward':'r0'},{'targetForward':'r1'}]
    for state in range(4):
        for bit in (0,1):t.States[state].Transitions[5+bit]=action(2+bit)
    for bit in (0,1):t.States[2+bit].Transitions[4]=action(current=bit)
    insertion=ot.InsertionMorph();t=ot.AATStateTable();insertion.StateTable=t
    t.GlyphClasses={'insert':4}
    for state in range(2):
        row=ot.AATState()
        for cls in range(5):
            a=ot.InsertionMorphAction()
            if cls==4:a.CurrentInsertionAction=['r1']*16
            row.Transitions[cls]=a
        t.States.append(row)
    morx=newTable('morx');morx.table=ot.morx();morx.table.Version=2;morx.table.Reserved=0
    chain=ot.MorxChain();chain.DefaultFlags=1;chain.MorphFeature=[];chain.MorphSubtable=[]
    for substruct in (adder,back,forward,insertion):
        sub=ot.MorxSubtable();sub.ProcessingOrder='LayoutOrder';sub.TextDirection='Horizontal';sub.Reserved=0;sub.SubFeatureFlags=1;sub.SubStruct=substruct
        chain.MorphSubtable.append(sub)
    morx.table.MorphChain=[chain];fb.font['morx']=morx
    out=HERE/'SafariComputeProbe.ttf';fb.save(out)
    print(f'{out}: {out.stat().st_size} bytes')


if __name__=='__main__':build()
