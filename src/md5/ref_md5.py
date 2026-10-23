#!/usr/bin/env python3
"""MD5 built only from the primitive bit/word ops a GSUB tape can do, so the
font generator has a verified spec to mirror. Checked against hashlib.

Everything is a list of 32 bits, index 0 = least significant. The only
operations used are:
  - XOR, AND, NOT of bit lists (per-bit, trivial in GSUB),
  - ADD32 (ripple carry, the carry travels along the tape),
  - ROTL (a pure renaming of bit positions, free in GSUB),
  - picking a message word's 32 bits and a constant's 32 bits.
"""
import hashlib, struct, sys

S = [7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
     5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
     4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
     6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21]
K = [int(abs(__import__("math").sin(i + 1)) * 2**32) & 0xFFFFFFFF for i in range(64)]
INIT = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476]


def bits(word):           # 32-bit int -> list of 32 bits, LSB first
    return [(word >> i) & 1 for i in range(32)]


def word(bs):             # inverse
    return sum(b << i for i, b in enumerate(bs)) & 0xFFFFFFFF


def XOR(a, b): return [x ^ y for x, y in zip(a, b)]
def AND(a, b): return [x & y for x, y in zip(a, b)]
def NOT(a): return [1 - x for x in a]
def OR(a, b): return [x | y for x, y in zip(a, b)]


def ADD32(a, b):
    out, carry = [], 0
    for x, y in zip(a, b):           # LSB first, carry ripples upward
        s = x + y + carry
        out.append(s & 1)
        carry = s >> 1
    return out


def ROTL(a, n):                       # left rotate: bit i moves to i+n
    n %= 32
    return [a[(i - n) % 32] for i in range(32)]


def pad(msg):
    bitlen = (len(msg) * 8) & 0xFFFFFFFFFFFFFFFF
    msg = msg + b"\x80"
    while len(msg) % 64 != 56:
        msg += b"\x00"
    return msg + struct.pack("<Q", bitlen)


def md5(msg):
    data = pad(msg)
    a0, b0, c0, d0 = (bits(w) for w in INIT)
    for off in range(0, len(data), 64):
        block = data[off:off + 64]
        M = [bits(struct.unpack("<I", block[4 * i:4 * i + 4])[0]) for i in range(16)]
        A, B, C, D = a0, b0, c0, d0
        for i in range(64):
            if i < 16:
                F, g = OR(AND(B, C), AND(NOT(B), D)), i
            elif i < 32:
                F, g = OR(AND(D, B), AND(NOT(D), C)), (5 * i + 1) % 16
            elif i < 48:
                F, g = XOR(XOR(B, C), D), (3 * i + 5) % 16
            else:
                F, g = XOR(C, OR(B, NOT(D))), (7 * i) % 16
            tmp = ADD32(A, F)
            tmp = ADD32(tmp, M[g])
            tmp = ADD32(tmp, bits(K[i]))
            tmp = ROTL(tmp, S[i])
            A, B, C, D = D, ADD32(B, tmp), B, C
        a0, b0, c0, d0 = (ADD32(x, y) for x, y in ((a0, A), (b0, B), (c0, C), (d0, D)))
    return b"".join(struct.pack("<I", word(w)) for w in (a0, b0, c0, d0))


if __name__ == "__main__":
    tests = [b"", b"a", b"abc", b"hello", b"message digest",
             b"The quick brown fox jumps over the lazy dog",
             b"a" * 55, b"a" * 56, b"a" * 120]
    bad = 0
    for m in tests:
        got, want = md5(m).hex(), hashlib.md5(m).hexdigest()
        ok = got == want
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} len={len(m):4} {got} {'' if ok else '!= ' + want} {m[:20]!r}")
    print("all correct" if not bad else f"{bad} wrong")
    sys.exit(1 if bad else 0)
