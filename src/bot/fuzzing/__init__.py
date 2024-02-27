
"""Fuzzing module."""

PUBLIC_ENGINES = [
    'libFuzzer']
   # 'afl',
   # 'honggfuzz',
   # 'googlefuzztest',
#)

PRIVATE_ENGINES = () #('syzkaller',)

ENGINES = PUBLIC_ENGINES #+ PRIVATE_ENGINES
