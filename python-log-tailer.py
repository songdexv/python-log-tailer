#!/usr/bin/env python
# -*- coding: utf-8 -*-
import locale

from logtailer import LogTailer

if __name__ == '__main__':
    def callback(fname, lines):
        for line in lines:
            print(fname, '--->', line.encode('gbk').decode(locale.getpreferredencoding()))


    tailer = LogTailer(folder=r'C:\Users\songdexv\Downloads', callback=callback,
                       fileNames=['supergw-biz-digest.log'], encoding='GBK', tail_lines=2)
    tailer.loop(interval=1)
