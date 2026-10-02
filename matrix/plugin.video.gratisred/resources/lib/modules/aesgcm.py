"""Minimal pure-Python AES-256-GCM decrypt (no external deps)."""

Sbox = (
0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
)
Rcon = (0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36,0x6c,0xd8,0xab,0x4d)


def _key_expansion(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [Sbox[b] for b in temp]
            temp[0] ^= Rcon[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [Sbox[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    return w, nr


def xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11b
    return a & 0xff


def _mul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi:
            a ^= 0x1b
        b >>= 1
    return p


def _add_round_key(state, w, rnd):
    for c in range(4):
        for r in range(4):
            state[r][c] ^= w[rnd * 4 + c][r]


def _sub_bytes(state):
    for r in range(4):
        for c in range(4):
            state[r][c] = Sbox[state[r][c]]


def _shift_rows(state):
    for r in range(1, 4):
        state[r] = state[r][r:] + state[r][:r]


def _mix_columns(state):
    for c in range(4):
        col = [state[r][c] for r in range(4)]
        state[0][c] = _mul(col[0], 2) ^ _mul(col[1], 3) ^ col[2] ^ col[3]
        state[1][c] = col[0] ^ _mul(col[1], 2) ^ _mul(col[2], 3) ^ col[3]
        state[2][c] = col[0] ^ col[1] ^ _mul(col[2], 2) ^ _mul(col[3], 3)
        state[3][c] = _mul(col[0], 3) ^ col[1] ^ col[2] ^ _mul(col[3], 2)


def _aes_encrypt_block(block16, w, nr):
    state = [[block16[r + 4 * c] for c in range(4)] for r in range(4)]
    _add_round_key(state, w, 0)
    for rnd in range(1, nr):
        _sub_bytes(state)
        _shift_rows(state)
        _mix_columns(state)
        _add_round_key(state, w, rnd)
    _sub_bytes(state)
    _shift_rows(state)
    _add_round_key(state, w, nr)
    return bytes(state[r][c] for c in range(4) for r in range(4))


class AES:
    """AES block cipher (encrypt-only; GCM only ever needs the encrypt
    direction, even for decrypting, since it is a stream cipher built on
    CTR mode)."""

    def __init__(self, key):
        self.w, self.nr = _key_expansion(key)

    def encrypt_block(self, block16):
        return _aes_encrypt_block(block16, self.w, self.nr)


def _gctr(aes, icb, data):
    out = bytearray()
    counter = int.from_bytes(icb, 'big')
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        keystream = aes.encrypt_block(counter.to_bytes(16, 'big'))
        out += bytes(a ^ b for a, b in zip(chunk, keystream))
        counter = (counter + 1) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    return bytes(out)


_R = 0xE1000000000000000000000000000000


def _gf_mult(x, y):
    """Multiply two 128-bit blocks (as ints) in GF(2^128), per NIST SP
    800-38D section 6.3, for GHASH."""
    z = 0
    v = y
    for i in range(128):
        if (x >> (127 - i)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ _R
        else:
            v >>= 1
    return z


def _ghash(h_int, aad, ciphertext):
    def pad_blocks(data):
        blocks = [data[i:i + 16] for i in range(0, len(data), 16)]
        if blocks and len(blocks[-1]) < 16:
            blocks[-1] = blocks[-1] + b'\x00' * (16 - len(blocks[-1]))
        return blocks

    y = 0
    for block in pad_blocks(aad):
        y = _gf_mult(y ^ int.from_bytes(block, 'big'), h_int)
    for block in pad_blocks(ciphertext):
        y = _gf_mult(y ^ int.from_bytes(block, 'big'), h_int)
    len_block = (len(aad) * 8).to_bytes(8, 'big') + (len(ciphertext) * 8).to_bytes(8, 'big')
    y = _gf_mult(y ^ int.from_bytes(len_block, 'big'), h_int)
    return y.to_bytes(16, 'big')


def aes_gcm_decrypt(key, iv, ciphertext_with_tag, aad=b''):
    """Decrypt + authenticate AES-GCM ciphertext (16-byte tag appended,
    WebCrypto style). Raises ValueError if the auth tag does not match,
    so callers never act on tampered/corrupted plaintext."""
    if len(key) not in (16, 24, 32):
        raise ValueError(f'invalid AES-GCM key length: {len(key)}')
    if len(iv) != 12:
        raise ValueError('only 96-bit IVs supported')
    if len(ciphertext_with_tag) < 16:
        raise ValueError('ciphertext too short to contain a GCM tag')

    aes = AES(key)
    ciphertext = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]

    h_int = int.from_bytes(aes.encrypt_block(b'\x00' * 16), 'big')
    j0 = iv + b'\x00\x00\x00\x01'

    expected_tag_block = aes.encrypt_block(j0)
    s = _ghash(h_int, aad, ciphertext)
    expected_tag = bytes(a ^ b for a, b in zip(s, expected_tag_block))
    if expected_tag != tag:
        raise ValueError('AES-GCM authentication tag mismatch')

    counter = int.from_bytes(j0, 'big') + 1
    icb = (counter & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF).to_bytes(16, 'big')
    return _gctr(aes, icb, ciphertext)
