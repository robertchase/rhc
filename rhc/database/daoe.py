import hashlib

from rhc.database.dao import DAO


class nullcipher(object):
    def encrypt(self, v):
        return v

    def decrypt(self, v):
        return v

CRYPT = nullcipher()


class DAOE(DAO):

    ENCRYPT_FIELDS = ()

    @staticmethod
    def makesha(value):
        return hashlib.sha256(value).digest()

    def on_load(self, kwargs):
        self._sha = {}
        self._crypt = {}
        for n in self.ENCRYPT_FIELDS:
            v = kwargs[n]
            if v is not None:
                self._crypt[n] = v
                clr = CRYPT.decrypt(v)
                self._sha[n] = self.makesha(clr)
                kwargs[n] = clr

    def before_save(self):
        if '_sha' not in self.__dict__:
            self._sha = {}
            self._crypt = {}
        self.__crypt_cache = {}
        for n in self.ENCRYPT_FIELDS:
            v = self.__crypt_cache[n] = getattr(self, n)
            if v is not None:
                if self._sha.get(n) == self.makesha(v):
                    v = self._crypt[n]
                else:
                    v = CRYPT.encrypt(v)
                    self._crypt[n] = v
                    self._sha[n] = self.makesha(v)
                setattr(self, n, v)

    def after_save(self):
        for n in self.ENCRYPT_FIELDS:
            setattr(self, n, self.__crypt_cache[n])
