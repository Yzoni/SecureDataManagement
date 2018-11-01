"""
A Type-and-Identity-Based Proxy Re-encryptionScheme and Its Application in Healthcare

| From: Luan Ibraimi, Qiang Tang, Pieter Hartel, and Willem Jonker

Based on:
Identity-Based Proxy Re-Encryption

https://github.com/nikosft/IB-PRE/blob/master/pre_mg07a.py

| From: "M. Green, G. Ateniese Identity-Based Proxy Re-Encryption", Section 4.1.
| Published in: Applied Cryptography and Network Security. Springer Berlin/Heidelberg, 2007
| Available from: http://link.springer.com/chapter/10.1007%2F978-3-540-72738-5_19

* type:           proxy encryption (identity-based)
* setting:        bilinear groups (symmetric)

:Authors:    N. Fotiou
:Date:       7/2016
"""

from charm.toolbox.pairinggroup import pc_element, ZR, G1, G2, GT, pair
from charm.toolbox.hash_module import Hash
from charm.adapters.pkenc_adapt_hybrid import HybridEnc

debug = False


class TIPRE:

    def __init__(self, groupObj, pkencObj=None):
        global group, h, pkenc
        group = groupObj
        h = Hash(group)
        if pkencObj is not None:
            pkenc = HybridEnc(pkencObj, msg_len=20)

    def setup(self):
        s = group.random(ZR)
        g = group.random(G1)
        msk = {'s': s}
        params = {'g': g, 'g_s': g ** s}
        return msk, params

    def keyGen(self, msk, ID):
        k = group.hash(ID, G1) ** msk['s']  # H1(ID) ^ s
        return {'skid': k}

    def encrypt(self, params, ID, m, skid, t):
        r = h.group.random(ZR)
        C1 = params['g'] ** r
        C2 = m * (pair(params['g_s'], group.hash(ID, G1)) ** (r * h.hashToZr(skid['skid'], t)))
        C3 = t
        return {'C1': C1, 'C2': C2, 'C3': C3}

    def encrypt1(self, params, m, ID):
        r = h.group.random(ZR)
        C1 = params['g'] ** r
        C2 = m * pair(group.hash(ID, G1), params['g_s']) ** r
        return {'C1': C1, 'C2': C2}

    def decrypt1(self, params, skid, c):
        return c['C2'] / pair(skid['skid'], c['C1'])

    def decrypt(self, params, skid, cid):
        if len(cid) == 3:
            m = cid['C2'] / (pair(cid['C1'], skid['skid']) ** h.hashToZr(skid['skid'], cid['C3']))
        if len(cid) == 4:
            x = self.decrypt1(params, skid, cid['C3'])
            m = cid['C2'] / pair(cid['C1'], group.hash(x, G1))
        return m

    def rkGen(self, params, skid_i, id_j, t):
        x = group.random(GT)
        return {
            'R1': t,
            'R2': skid_i['skid'] ** (-h.hashToZr(skid_i['skid'], t)) * group.hash(x, G1),  # sk ^(-h1(sk||t)) * h2(x)
            'R3': self.encrypt1(params, x, id_j)  # Encrypt2(x, idj)
        }

    def reEncrypt(self, params, rk, ciphertext):
        return {
            'C1': ciphertext['C1'],  # g^ r
            'C2': ciphertext['C2'] * pair(ciphertext['C1'], rk['R2']),
            'C3': rk['R3'],
            'Reencrypted': True
        }


if __name__ == '__main__':
    from charm.toolbox.pairinggroup import PairingGroup, GT, extract_key
    from charm.toolbox.symcrypto import SymmetricCryptoAbstraction

    group = PairingGroup('SS512', secparam=1024)
    pre = TIPRE(group)
    ID1 = "Alice"
    ID2 = "Bob"
    msg = b'Message to encrypt'
    type_attribute = group.random(ZR)
    symcrypto_key = group.random(GT)

    symcrypto = SymmetricCryptoAbstraction(extract_key(symcrypto_key))
    bytest_text = symcrypto.encrypt(msg)

    (master_secret_key, params) = pre.setup()

    # Run by trusted party, someone needs to handle the master secret key
    id1_secret_key = pre.keyGen(master_secret_key, ID1)
    id2_secret_key = pre.keyGen(master_secret_key, ID2)

    # Run by delegator (id_name_1), encrypt the sym key
    ciphertext = pre.encrypt(params, ID1, symcrypto_key, id1_secret_key, type_attribute)

    # Directly decrypt ciphertext by the same party
    plain = pre.decrypt(params, id1_secret_key, ciphertext)
    print('Symmetric key directly decrypted by party 1: {}\n'.format(plain))

    # # Run by delegator (id_name_1) create reencryption key for ID2, used by the proxy
    re_encryption_key = pre.rkGen(params, id1_secret_key, ID2, type_attribute)

    # Run by the proxy, uses the re encryption key generated by ID1
    ciphertext2 = pre.reEncrypt(params, re_encryption_key, ciphertext)

    # Run by the delegatee (id_name_2), retrieve the secrey key
    symcrypto_key_decrypted = pre.decrypt(params, id2_secret_key, ciphertext2)
    print('Symmetric key decrypted by party 2: {}'.format(symcrypto_key_decrypted))

    # Use the secrey key to decrypt a msg
    symcrypto = SymmetricCryptoAbstraction(extract_key(symcrypto_key_decrypted))
    decrypted_ct = symcrypto.decrypt(bytest_text)

    print('Decrypted: {}'.format(decrypted_ct))
