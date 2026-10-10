# /// script
# requires-python = ">=3.12"
# dependencies = ["cryptography==46.0.2"]
# ///
import hashlib
import secrets

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

# Curve constants from RFC 8032 section 5.1
P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, -1, P) % P
B = (
    15112221349535400772501151409588531511454012693041857206046113283949847762202,
    46316835694926478169428394003475163141307993866256225615783033603165251855960,
)


def add(p1, p2):
    (x1, y1), (x2, y2) = p1, p2
    t = D * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * pow(1 + t, -1, P) % P
    y3 = (y1 * y2 + x1 * x2) * pow(1 - t, -1, P) % P
    return x3, y3


def mul(k, point):
    result = (0, 1)
    while k:
        if k & 1:
            result = add(result, point)
        point = add(point, point)
        k >>= 1
    return result


def encode(point):
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def b58(data):
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = alphabet[rem] + out
    return "1" * (len(data) - len(data.lstrip(b"\0"))) + out


def h(*parts):
    return int.from_bytes(hashlib.sha512(b"".join(parts)).digest(), "little")


# The owner's 32-byte seed, what a keypair file or a derived wallet key holds
seed = secrets.token_bytes(32)
owner = Ed25519PrivateKey.from_private_bytes(seed)
address = owner.public_key().public_bytes_raw()
print("address (base58):", b58(address))

# RFC 8032 5.1.5: hash the seed, clamp the low half into the scalar s
digest = bytearray(hashlib.sha512(seed).digest())
digest[0] &= 248
digest[31] &= 127
digest[31] |= 64
s = int.from_bytes(digest[:32], "little")
print("s * B equals the address:", encode(mul(s, B)) == address)

# The attacker has s from breaking the curve, and has never seen the seed
message = b"transfer everything to the attacker"
r = secrets.randbelow(L)
R = encode(mul(r, B))
k = h(R, address, message) % L
signature = R + ((r + k * s) % L).to_bytes(32, "little")

Ed25519PublicKey.from_public_bytes(address).verify(signature, message)
print("forged signature verifies: True")
