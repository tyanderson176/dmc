import copy
import numpy
import bisect

tol = 1e-15

class Vec:
    '''
    Represents a vector in Hilbert space, written in terms of Slater 
    determinants.  Initialized using a dict whose keys are Slater 
    determinants.
    '''
    def __init__(self, det_dict={}):
        self.dets = {key: det_dict[key] for key in det_dict 
                if abs(det_dict[key]) > tol}

    def norm(self):
        if (not self.dets): 
            return 0.
        coeffs = numpy.array([self.dets[det] for det in self.dets])
        return numpy.sqrt(numpy.dot(coeffs, coeffs))

    def dot(self, other):
        scalar_product = 0
        for det, coef in self.dets.items():
            if det in other.dets:
                scalar_product += coef*other.dets[det]
        return scalar_product

    @staticmethod
    def zero():
        return Vec({})

    def __repr__(self):
        if len(self.dets) == 0:
            return '0'
        vec_str = ' + '.join([self._coeff_str(self.dets[det]) + str(det) 
                             for det in self.dets])
        return vec_str

    def _coeff_str(self, coeff):
        return '' if coeff == 1 else "%14.4e"%coeff

    def __iadd__(self, other):
        for det in other.dets:
            if det in self.dets:
                self.dets[det] += other.dets[det]
                if (abs(self.dets[det]) < tol): 
                    del self.dets[det]
            else:
                self.dets[det] = other.dets[det]
        return self

    def __add__(self, other):
        sum_dets = copy.deepcopy(self.dets)
        for det in other.dets:
            if det in sum_dets:
                sum_dets[det] += other.dets[det]
            else:
                sum_dets[det] = other.dets[det]
        return Vec(sum_dets)

    def __sub__(self, other):
        return self + (-1)*other

    def __rmul__(self, scalar):
        mul_dict = {}
        for det in self.dets:
            mul_dict[det] = scalar*self.dets[det]
        return Vec(mul_dict)

    def __truediv__(self, scalar):
        return (1./scalar)*self

    def __eq__(self, other):
        return self.dets == other.dets

class Det:
    def __init__(self, up_occ, dn_occ):
        self.up_occ = sorted(up_occ)
        self.dn_occ = sorted(dn_occ)
        self.my_hash = self._get_hash()

    def get_Sz(self):
        return (len(self.up_occ) - len(self.dn_occ))/2

#    @property
#    def parity(self):
#        if not self._parity:
#            self._parity = self._compute_parity()
#        return self._parity

    def qmc_str(self):
        qmc_str = ['%4d' % orb for orb in self.up_occ]
        qmc_str += '     '
        qmc_str += ['%4d' % orb for orb in self.dn_occ]
        return "".join(qmc_str)

    def __mul__(self, other):
        if isinstance(other, (int, float, numpy.int64, numpy.float64)):
            return Vec({self: other})
        raise Exception("Unknown type \'" + str(type(other)) +
                "\' in Det.__mul__")

    __rmul__ = __mul__

#    def _parity_rel(self, occ1, occ2):
#        #Computes relative parity of occ1 and occ2
#        occ1, occ2 = copy.deepcopy(occ1), copy.deepcopy(occ2)
#        num_perms = 0
#        for n, orb in enumerate(occ1):
#            index = occ2.index(orb)
#            if index == -1:
#                raise Exception(
#                        "Occupation strings not permutations in _parity")
#            if index != n:
#                occ2[index], occ2[n] = occ2[n], occ2[index]
#                num_perms += 1
#        return (-2)*num_perms%2 + 1 
#
#    def _compute_parity(self):
#        #computes parity relative to ordering s.t. up/down spins for the same
#        #spacial orbital are adjacent
#        up_occ, dn_occ = self.up_occ, self.dn_occ
#        if len(up_occ) == 0 or len(dn_occ) == 0:
#            return 1
#        up_ptr, dn_ptr = len(up_occ)-1, len(dn_occ)-1
#        alt_sum, count = 0, 0
#        while -1 < dn_ptr:
#            dn = dn_occ[dn_ptr]
#            if up_ptr != -1 and up_occ[up_ptr] > dn:
#                count += 1
#                up_ptr += -1
#            else:
#                alt_sum = count - alt_sum 
#                dn_ptr += -1
#        assert(alt_sum > -1)
#        return (1 if alt_sum%2 == 0 else -1)

    def __hash__(self):
        return self.my_hash

    def _get_hash(self):
        return hash(self.__repr__())
        # return hash((tuple(self.up_occs), tuple(self.dn_occs)))

    def __eq__(self, other):
        return (self.up_occ == other.up_occ 
                and self.dn_occ == other.dn_occ)

    def __repr__(self):
        return self._get_repr()

    def _get_repr(self):
        det_str = '|'
        det_str += ' '.join([str(orb) for orb in self.up_occ])
        det_str += '; '
        det_str += ' '.join([str(orb) for orb in self.dn_occ])
        det_str += ')'
        return det_str

class Config:
    #Data structure for orbital configuration.
    #Gives occupation of each spacial orbital (0, 1 or 2)
    def __init__(self, det):
        self.occs = {}
        for up_orb in det.up_occ:
            self.occs[up_orb] = 1
        for dn_orb in det.dn_occ:
            self.occs[dn_orb] = 1 if dn_orb not in self.occs else 2
        self.num_open = \
            sum([1 if self.occs[orb] == 1 else 0 for orb in self.occs])
        self.config_str = self.make_config_str()

    @classmethod
    def fromorbs(cls, up_orbs, dn_orbs):
        return cls(Det(up_orbs, dn_orbs))

    def make_config_str(self):
        orbs = sorted([orb for orb in self.occs])
        return '_'.join([str(orb)+'S'+str(self.occs[orb]) for orb in orbs])

    def __hash__(self):
        return hash(self.__repr__())

    def __repr__(self):
        return self.config_str

    def __eq__(self, other):
        return self.occs == other.occs 

    def __lt__(self, other):
        return self.config_str < other.config_str
