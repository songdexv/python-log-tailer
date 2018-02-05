#!/usr/bin/env python
# -*- coding: utf-8 -*-
import errno
import stat

import os
import time


class LogTailer(object):
    """Looks for changes in all files of a directory.
    This is useful for watching log file changes in real-time.
    It also supports files rotation.

    Example:

    >>> def callback(filename, lines):
    ...     print(filename, lines)
    ...
    >>> lw = LogTailer("/var/log/", callback)
    >>> lw.loop()
    """

    def __init__(self, folder, callback, fileNames=[], encoding="UTF-8", tail_lines=0, sizehint=1048576):
        """Arguments:

        (str) @folder:
            the folder to watch

        (callable) @callback:
            a function which is called every time one of the file being
            watched is updated;
            this is called with "filename" and "lines" arguments.

        (list) @fileNames:
            only watch files in fileNames
            
        (str) @encoding:
            encoding of files , default UTF-8

        (int) @tail_lines:
            read last N lines from files being watched before starting

        (int) @sizehint: passed to file.readlines(), represents an
            approximation of the maximum number of bytes to read from
            a file on every ieration (as opposed to load the entire
            file in memory until EOF is reached). Defaults to 1MB.
        """
        self.folder = os.path.realpath(folder)
        self.fileNames = fileNames
        self.encoding = encoding
        self._files_map = {}
        self._callback = callback
        self._sizehint = sizehint
        assert os.path.isdir(self.folder), self.folder
        assert callable(callback), repr(callback)

        self.update_files()
        for id, file in self._files_map.items():
            file.seek(os.path.getsize(file.name))  # EOF
            if tail_lines:
                try:
                    lines = self.tail(file.name, self.encoding, tail_lines)
                except IOError as err:
                    if err.errno != errno.ENOENT:
                        raise
                else:
                    if lines:
                        self._callback(file.name, lines)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()

    def loop(self, interval=0.1, blocking=True):
        """Start a busy loop checking for file changes every *interval*
        seconds. If *blocking* is False make one loop then return.
        """
        while True:
            self.update_files()
            for fid, file in list(self._files_map.items()):
                self.readLines(file)
            if not blocking:
                return
            time.sleep(interval)

    def log(self, line):
        """Log when a file is un/watched"""
        print(line)

    def listdir(self):
        ls = os.listdir(self.folder)
        if self.fileNames:
            return [x for x in ls if os.path.split(x)[1] in self.fileNames]
        else:
            return ls

    @classmethod
    def open(cls, file, encoding):
        return open(file, 'r', encoding=encoding, errors='ignore')

    @classmethod
    def tail(cls, fname, encoding, window):
        """Read last N lines from file fname. e.g tail -n 100 f"""
        if window < 0:
            raise ValueError('invalid window value %r' % window)  # %r 采用repr()的显示
        with cls.open(fname, encoding) as f:
            BUFSIZ = 1024
            CR = '\n'
            data = ''
            f.seek(0, os.SEEK_END)
            fsize = f.tell()
            block = -1
            exit = False
            print('fsize:', fsize)
            while not exit:
                f.seek(0, os.SEEK_SET)
                step = (block * BUFSIZ)
                if abs(step) >= fsize:
                    f.seek(0, os.SEEK_SET)
                    newdata = f.read(BUFSIZ - (abs(step) - fsize))
                    exit = True
                else:
                    f.seek(fsize + step, os.SEEK_SET)
                    # print('positon:', f.tell())
                    newdata = f.read(BUFSIZ)
                    # print('newdata:', newdata)
                data = newdata + data
                if data.count(CR) >= window:
                    break
                else:
                    block -= 1
            return data.splitlines()[-window:]

    def update_files(self):
        ls = []
        for name in self.listdir():
            absname = os.path.realpath(os.path.join(self.folder, name))
            try:
                st = os.stat(absname)
            except EnvironmentError as err:
                if err.errno != errno.ENOENT:
                    raise
            else:
                if not stat.S_ISREG(st.st_mode):
                    continue
                fid = self.get_file_id(st)
                ls.append((fid, absname))

        # check existent files
        for fid, file in list(self._files_map.items()):
            try:
                st = os.stat(file.name)
            except EnvironmentError as err:
                if err.errno == errno.ENOENT:
                    self.unwatch(file, fid)
                else:
                    raise
            else:
                if fid != self.get_file_id(st):
                    # same name but different file (rotation); reload it.
                    self.unwatch(file, fid)
                    self.watch(file.name)

        # add new ones
        for fid, fname in ls:
            if fid not in self._files_map:
                self.watch(fname)

    def readLines(self, file):
        """Read file lines since last access until EOF is reached and
        invoke callback.
        """
        while True:
            lines = file.readlines(self._sizehint)
            if not lines:
                break
            self._callback(file.name, lines)

    def watch(self, fname):
        try:
            file = self.open(fname, self.encoding)
            fid = self.get_file_id(os.stat(fname))
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        else:
            self.log('watching logfile %s' % fname)
            self._files_map[fid] = file

    def unwatch(self, file, fid):
        # File no longer exists. If it has been renamed try to read it
        # for the last time in case we're dealing with a rotating log
        # file.
        self.log('un-watching logfile %s' % file.name)
        del self._files_map[fid]
        with file:
            self.readLines(file)

    @staticmethod
    def get_file_id(st):
        if os.name == 'posix':
            return '%xg%x' % (st.st_dev, st.st_ino)
        else:
            return '%f' % st.st_ctime

    def close(self):
        for id, file in self._files_map.items():
            file.close()
        self._files_map.clear()
