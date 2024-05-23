#!/usr/bin/env python3
# -*- coding: utf-8; fill-column: 88 -*-

import sys


def main():
    seq = "0123456789"
    seq_len = len(seq)
    seq_cnt = 0
    for arg in sys.argv[1:]:
        count = int(arg)
        str_list = []
        for _ in range(count):
            str_list.append(seq[seq_cnt])
            seq_cnt += 1
            if seq_cnt == seq_len:
                seq_cnt = 0
        print("".join(str_list))


if __name__ == "__main__":
    sys.exit(main())
