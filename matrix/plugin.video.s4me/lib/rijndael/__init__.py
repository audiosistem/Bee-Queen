from rijndael import rijndael
from rijndael_cbc import zeropad, cbc

import base64


def cbc_encrypt(msg, IV, key, size=32):

    r = rijndael(key, size)
    pad = zeropad(size)
    cri = cbc(pad, r, IV)
    encod = cri.encrypt(msg)

    return encod #.encode('hex')


def cbc_decrypt(msg, IV, key, size=32):

    r = rijndael(key, size)
    pad = zeropad(size)
    cri = cbc(pad, r, IV)

    return cri.decrypt(msg)
