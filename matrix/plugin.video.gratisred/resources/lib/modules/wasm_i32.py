"""Minimal i32 WebAssembly interpreter (no imports, no floats).

Used to run VidSrc's per-window ChaCha-style decrypt wasm in Kodi, where
wasmtime/wasmer are not available. Only the opcodes that module uses are
implemented.
"""

from __future__ import print_function

MASK32 = 0xffffffff


def _leb(buf, i):
    n = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7f) << shift
        if not (b & 0x80):
            return n, i
        shift += 7


def _sleb(buf, i):
    n = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        n |= (b & 0x7f) << shift
        shift += 7
        if not (b & 0x80):
            if b & 0x40 and shift < 32:
                n |= (-1 << shift)
            break
    return n & MASK32, i


def _rotl(v, n):
    n &= 31
    v &= MASK32
    if not n:
        return v
    return ((v << n) | (v >> (32 - n))) & MASK32


def _rotr(v, n):
    n &= 31
    v &= MASK32
    if not n:
        return v
    return ((v >> n) | (v << (32 - n))) & MASK32


class WasmI32(object):
    def __init__(self, blob):
        if not blob or blob[:4] != b'\x00asm':
            raise ValueError('not a wasm module')
        self.mem = bytearray()
        self.globals = []
        self.types = []
        self.func_types = []
        self.funcs = []
        self.exports = {}
        self._parse(blob)

    def call(self, name, *args):
        idx = self.exports.get(name)
        if idx is None:
            raise KeyError(name)
        return self._call(idx, list(args))

    def write(self, ptr, data):
        end = ptr + len(data)
        if end > len(self.mem):
            raise ValueError('wasm write out of bounds')
        self.mem[ptr:end] = data

    def read(self, ptr, n):
        return bytes(self.mem[ptr:ptr + n])

    def _parse(self, blob):
        i = 8
        sections = {}
        while i < len(blob):
            sec = blob[i]
            i += 1
            size, i = _leb(blob, i)
            sections[sec] = blob[i:i + size]
            i += size
        self._types(sections.get(1, b''))
        self._func_sec(sections.get(3, b''))
        self._memory(sections.get(5, b''))
        self._globals(sections.get(6, b''))
        self._exports(sections.get(7, b''))
        self._code(sections.get(10, b''))
        self._data(sections.get(11, b''))

    def _types(self, body):
        n, i = _leb(body, 0) if body else (0, 0)
        for _ in range(n):
            i += 1
            np, i = _leb(body, i)
            i += np
            nr, i = _leb(body, i)
            i += nr
            self.types.append((np, nr))

    def _func_sec(self, body):
        n, i = _leb(body, 0) if body else (0, 0)
        for _ in range(n):
            t, i = _leb(body, i)
            self.func_types.append(t)

    def _memory(self, body):
        n, i = _leb(body, 0)
        if n != 1:
            raise ValueError('expected one memory')
        flags, i = _leb(body, i)
        initial, i = _leb(body, i)
        if flags & 1:
            _max, i = _leb(body, i)
        self.mem = bytearray(initial * 65536)

    def _globals(self, body):
        n, i = _leb(body, 0) if body else (0, 0)
        for _ in range(n):
            i += 1
            mut = body[i]
            i += 1
            if body[i] != 0x41:
                raise ValueError('unsupported global init')
            i += 1
            val, i = _sleb(body, i)
            if body[i] != 0x0b:
                raise ValueError('global init missing end')
            i += 1
            self.globals.append([val & MASK32, mut])

    def _exports(self, body):
        n, i = _leb(body, 0) if body else (0, 0)
        for _ in range(n):
            ln, i = _leb(body, i)
            name = body[i:i + ln].decode('utf-8')
            i += ln
            kind = body[i]
            i += 1
            idx, i = _leb(body, i)
            if kind == 0:
                self.exports[name] = idx

    def _code(self, body):
        n, i = _leb(body, 0)
        for _ in range(n):
            size, i = _leb(body, i)
            chunk = body[i:i + size]
            i += size
            self.funcs.append(self._decode_func(chunk))

    def _decode_func(self, chunk):
        nloc, i = _leb(chunk, 0)
        extra = 0
        for _ in range(nloc):
            cnt, i = _leb(chunk, i)
            i += 1
            extra += cnt
        ops = []
        while i < len(chunk):
            op = chunk[i]
            i += 1
            a = b = 0
            if op in (0x0c, 0x0d, 0x10, 0x20, 0x21, 0x22, 0x23, 0x24):
                a, i = _leb(chunk, i)
            elif op == 0x41:
                a, i = _sleb(chunk, i)
            elif op in (0x28, 0x2d, 0x36, 0x3a):
                _align, i = _leb(chunk, i)
                a, i = _leb(chunk, i)
            elif op in (0x02, 0x03, 0x04):
                a = chunk[i]
                i += 1
            elif op in (0x3f, 0x40):
                a, i = _leb(chunk, i)
            ops.append([op, a, b, -1, -1])
        self._fix_labels(ops)
        return extra, ops

    def _fix_labels(self, ops):
        stack = []
        for i, ins in enumerate(ops):
            op = ins[0]
            if op in (0x02, 0x03, 0x04):
                stack.append(i)
            elif op == 0x05:
                blk = stack[-1]
                ops[blk][3] = i
            elif op == 0x0b:
                if not stack:
                    continue
                blk = stack.pop()
                ops[blk][4] = i
                if ops[blk][3] >= 0:
                    ops[ops[blk][3]][4] = i

    def _data(self, body):
        n, i = _leb(body, 0) if body else (0, 0)
        for _ in range(n):
            kind, i = _leb(body, i)
            if kind != 0:
                raise ValueError('unsupported data segment')
            if body[i] != 0x41:
                raise ValueError('data offset')
            i += 1
            off, i = _sleb(body, i)
            if body[i] != 0x0b:
                raise ValueError('data offset end')
            i += 1
            ln, i = _leb(body, i)
            self.mem[off:off + ln] = body[i:i + ln]
            i += ln

    def _call(self, idx, args):
        nparams, nresults = self.types[self.func_types[idx]]
        extra, ops = self.funcs[idx]
        if len(args) != nparams:
            raise TypeError('wasm argc')
        locals_ = [(a & MASK32) for a in args] + [0] * extra
        stack = []
        result = self._exec(ops, locals_, stack)
        if nresults:
            return result if result is not None else (stack[-1] if stack else 0)
        return None

    def _exec(self, ops, locals_, stack):
        mem = self.mem
        globs = self.globals
        pc = 0
        nops = len(ops)
        controls = []
        while pc < nops:
            op, a, b, else_pc, end_pc = ops[pc]
            if op == 0x0b:
                if controls:
                    controls.pop()
                pc += 1
                continue
            if op == 0x02 or op == 0x03:
                controls.append((op, pc + 1, end_pc, len(stack)))
                pc += 1
                continue
            if op == 0x04:
                cond = stack.pop()
                controls.append((op, pc + 1, end_pc, len(stack)))
                if cond:
                    pc += 1
                elif else_pc >= 0:
                    pc = else_pc + 1
                else:
                    pc = end_pc
                continue
            if op == 0x05:
                pc = end_pc
                continue
            if op == 0x0c or op == 0x0d:
                if op == 0x0d:
                    cond = stack.pop()
                    if not cond:
                        pc += 1
                        continue
                ctrl = controls[-(a + 1)]
                kind, start_body, cend, height = ctrl
                del controls[len(controls) - a:]
                if len(stack) > height:
                    del stack[height:]
                if kind == 0x03:
                    pc = start_body
                else:
                    controls.pop()
                    pc = cend + 1
                continue
            if op == 0x10:
                nparams, nresults = self.types[self.func_types[a]]
                args = [stack.pop() for _ in range(nparams)]
                args.reverse()
                ret = self._call(a, args)
                if nresults:
                    stack.append(ret & MASK32)
                pc += 1
                continue
            if op == 0x1a:
                stack.pop()
                pc += 1
                continue
            if op == 0x20:
                stack.append(locals_[a])
            elif op == 0x21:
                locals_[a] = stack.pop() & MASK32
            elif op == 0x23:
                stack.append(globs[a][0])
            elif op == 0x24:
                globs[a][0] = stack.pop() & MASK32
            elif op == 0x28:
                addr = (stack.pop() + a) & MASK32
                stack.append(mem[addr] | (mem[addr + 1] << 8) | (mem[addr + 2] << 16) | (mem[addr + 3] << 24))
            elif op == 0x2d:
                addr = (stack.pop() + a) & MASK32
                stack.append(mem[addr])
            elif op == 0x36:
                val = stack.pop() & MASK32
                addr = (stack.pop() + a) & MASK32
                mem[addr] = val & 0xff
                mem[addr + 1] = (val >> 8) & 0xff
                mem[addr + 2] = (val >> 16) & 0xff
                mem[addr + 3] = (val >> 24) & 0xff
            elif op == 0x3a:
                val = stack.pop() & MASK32
                addr = (stack.pop() + a) & MASK32
                mem[addr] = val & 0xff
            elif op == 0x3f:
                stack.append(len(mem) // 65536)
            elif op == 0x40:
                pages = stack.pop()
                old = len(mem) // 65536
                mem.extend(bytearray(pages * 65536))
                stack.append(old)
            elif op == 0x41:
                stack.append(a)
            elif op == 0x4b:
                r = stack.pop()
                l = stack.pop()
                stack.append(1 if (l & MASK32) > (r & MASK32) else 0)
            elif op == 0x4d:
                r = stack.pop()
                l = stack.pop()
                stack.append(1 if (l & MASK32) <= (r & MASK32) else 0)
            elif op == 0x4f:
                r = stack.pop()
                l = stack.pop()
                stack.append(1 if (l & MASK32) >= (r & MASK32) else 0)
            elif op == 0x6a:
                r = stack.pop()
                l = stack.pop()
                stack.append((l + r) & MASK32)
            elif op == 0x6b:
                r = stack.pop()
                l = stack.pop()
                stack.append((l - r) & MASK32)
            elif op == 0x6c:
                r = stack.pop()
                l = stack.pop()
                stack.append((l * r) & MASK32)
            elif op == 0x6e:
                r = stack.pop() & MASK32
                l = stack.pop() & MASK32
                stack.append((l // r) if r else 0)
            elif op == 0x71:
                r = stack.pop()
                l = stack.pop()
                stack.append((l & r) & MASK32)
            elif op == 0x73:
                r = stack.pop()
                l = stack.pop()
                stack.append((l ^ r) & MASK32)
            elif op == 0x77:
                r = stack.pop()
                l = stack.pop()
                stack.append(_rotl(l, r))
            elif op == 0x78:
                r = stack.pop()
                l = stack.pop()
                stack.append(_rotr(l, r))
            elif op == 0x0f:
                return stack[-1] if stack else 0
            else:
                raise ValueError('unsupported wasm opcode 0x%02x' % op)
            pc += 1
        return stack[-1] if stack else 0


def decrypt_b64(wasm_blob, enc_b64):
    """vsdec.js: alloc ciphertext, decrypt in place, skip 12-byte nonce."""
    import base64
    raw = base64.b64decode(enc_b64)
    mod = WasmI32(wasm_blob)
    ptr = mod.call('alloc', len(raw))
    mod.write(ptr, raw)
    out_len = mod.call('decrypt', ptr, len(raw))
    return mod.read(ptr + 12, out_len).decode('utf-8')
