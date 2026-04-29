import base64
import zlib
try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Util import Counter
except:
    try:
        from Crypto.Cipher import AES
        from Crypto.Util import Counter
    except:
        pass

uilsdfusdfziuilsdzf = "MlHd7hx3BA0vnS14xNAsMUqQ/9wQdHzVq7IIqS8VAbM="
dfgzuhdfzguilhjzgdfzg = "dTUhv8pDS/+K5itYw3aQpw=="

def ufghjxcgfzxc(i):
    uilhzszsfduhilsd = base64.b64decode(i[1:])
    sdfiojsdiofjiasd = bytes(b ^ 39 for b in base64.b64decode(uilsdfusdfziuilsdzf))
    iopdfgfikldzioqw = bytes(b ^ 79 for b in base64.b64decode(dfgzuhdfzguilhjzgdfzg))
    rtudz8yghuilgz89 = Counter.new(128, initial_value=int.from_bytes(iopdfgfikldzioqw, "big"))
    uileszszfluihzsd = AES.new(sdfiojsdiofjiasd, AES.MODE_CTR, counter=rtudz8yghuilgz89)
    return uileszszfluihzsd.decrypt(uilhzszsfduhilsd).decode("utf-8")

def dfzxujsdfzio(i):
    sdfiojsdiofjiasd = bytes(b ^ 39 for b in base64.b64decode(uilsdfusdfziuilsdzf))
    iopdfgfikldzioqw = bytes(b ^ 79 for b in base64.b64decode(dfgzuhdfzguilhjzgdfzg))
    rtudz8yghuilgz89 = Counter.new(128, initial_value=int.from_bytes(iopdfgfikldzioqw, "big"))
    uileszszfluihzsd = AES.new(sdfiojsdiofjiasd, AES.MODE_CTR, counter=rtudz8yghuilgz89)
    return zlib.decompress(uileszszfluihzsd.decrypt(i[1:]))