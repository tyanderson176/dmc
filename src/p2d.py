from pyscf import gto, scf
import numpy
import copy
from functools import reduce

class basis_vec():
    def __init__(self, n, l, bv_id, cs, zs, slater_exp = 0):
        self.n = n
        self.l = l
        self.bv_id = bv_id
        self.cs, self.zs = cs, zs
        self.gto_ctrs = self._cgto_list()
        self.slater_exp = slater_exp

    def __repr__(self):
        return "Zetas: " + str(self.zs) + " Coefs: " + str(self.cs)

    def _gto(self, n, l, z, c):
        return lambda r: c*pow(r, l)*numpy.exp(-z*r)

    def _make_ctr_gto(self, n, l):
       gtos = [self._gto(n,l,z,c) for z, c in zip(self.zs, self.cs)]
       ctr_gto = lambda r: sum([gto(r) for gto in gtos])
       return ctr_gto

    def _cgto_list(self):
        clist = []
        clist += [self._make_ctr_gto(self.n, self.l)]
        return clist

class orb_matrix():
    def __init__(self, init_elem, orb_print_method = str):
        self._internal = []
        self.init_elem = init_elem
        self.orb_print_method = orb_print_method

    def __setitem__(self, quant_nums, value):
        max_n = len(self._internal)
        n, l, m = quant_nums
        if n > max_n:
            self._internal += [
                self._make_shell(_n) for _n in range(max_n+1, n+1)]
        self._internal[n-1][l][m] = value

    def __getitem__(self, quant_nums):
        max_n = len(self._internal)
        n, l, m = quant_nums
        if n > max_n:
            return copy.copy(self.init_elem)
        return self._internal[n-1][l][m]

    def _make_shell(self, n):
        return [[copy.copy(self.init_elem) for m in range(2*l+1)] for l in range(n)]

    def __repr__(self):
        ret_str = ""
        for norbs in self._internal:
            ret_str += ' '
            for lorbs in norbs:
                ret_str += ' '
                for morb in lorbs:
                    ret_str += (self.orb_print_method(morb) + ' ')
        return ret_str

class atomic_orb():
    def __init__(self, mol, n, l, m, ia, bvec, mo_coeffs):
        self.mol = mol
        self.n = n
        self.l = l
        self.m = m
        self.quant_nums = n, l, m
        self.ia = ia
        self.atom = self.mol.atom_symbol(ia)
        self.bvec = bvec
        self.mo_coeffs = mo_coeffs
        self.d_key = {0:0, 2:1, -2:2, 1:3, -1:4}
        self.p_key = {1:0, -1:1, 0:2} 

    def slater_exp(self):
        return self.bvec.slater_exp

    def __repr__(self):
        ret = "AO: n=%d l=%d m=%d" % (self.n, self.l, self.m)
        ret += "\tBasis Vec: " + str(self.bvec)
        return ret

    def __lt__(self, other):
        if self.ia != other.ia:
            return self.ia < other.ia
        elif self.l != other.l:
            return self.l < other.l
        elif self.m != other.m:
            if (self.l == 1):
                return self.p_key[self.m] < self.p_key[other.m]
            if (self.l == 2):
                return self.d_key[self.m] < self.d_key[other.m]
            return self.m < other.m
        elif self.n != other.n:
            return self.n < other.n
        else:
            return False

def mol2aos(mol, mf, basis = None):
    assert(not mol.cart)
    p_lz = [1, -1, 0] #m for orbitals in p shell (X, Y, Z = 1, -1, 0)
    bv_ids, aos = {}, []
    orb_id = 0
    count = numpy.zeros((mol.natm, 9), dtype=int)
    for ib in range(mol.nbas):
        ia = mol.bas_atom(ib)
        l = mol.bas_angular(ib)
        nc = mol.bas_nctr(ib)
        atom = mol.atom_symbol(ia)
        bv_coeffs, bv_exps = mol.bas_ctr_coeff(ib), mol.bas_exp(ib)
        sto = basis.find(atom.upper(), l, bv_coeffs, bv_exps) if basis else None
        if ia not in bv_ids:
            bv_ids[ia] = 0
        nelec_ecp = mol.atom_nelec_core(ia)
        if nelec_ecp == 0 or l > 3:
            shl_start = count[ia,l]+l+1
        else:
            coreshl = ecp.core_configuration(nelec_ecp)
            shl_start = coreshl[l]+count[ia,l]+l+1
        count[ia,l] += nc
        ns = range(shl_start, shl_start+nc)
        for i, n in enumerate(ns):
            '''
            The 'ns' computed by Pyscf simply enumerate the basis functions
            as they appear in the input basis file - they may have little
            to do with the 'actual' ns cooresponding to energy level.
            Because of this, I have redefined n below. If n was
            provided in some external basis, we use n = sto.get_n(). Otherwise,
            we use the numerical QMC convention that n = l+1 (i.e. all shells 
            with a fixed angular momentum l are placed in the same 'bucket')
            '''
            n = sto.get_n() if sto else l+1
            slater_exp = sto.get_slater_exponent() if sto else 0
            cs, zs = bv_coeffs[:,i], bv_exps 
            bvec = basis_vec(n, l, bv_ids[ia], cs, zs, slater_exp)
            bv_ids[ia] += 1
            for m in range(-l, l+1):
                mo_coeffs = mf.mo_coeff[orb_id]
                lz = m if l != 1 else p_lz[m+1]
                aos.append(atomic_orb(mol, n, l, lz, ia, bvec, mo_coeffs))
                orb_id += 1
    assert(len(aos) == len(mol.ao_labels()))
    return sorted(aos)

def get_atom_aos(aos, atom):
    atom_rep = None
    atom_aos = []
    for ao in aos:
        if atom_rep == None and ao.atom == atom:
            atom_rep = ao.ia
        if atom_rep == ao.ia:
            atom_aos += [ao]
    if not atom_aos:
        raise Exception("Atom type '"+str(atom)+
            "' not found in set of basis vectors.")
    return atom_aos

def aos2atom_bvecs(aos, atom):
    bvecs, bv_labels = [], {}
    atom_aos = get_atom_aos(aos, atom)
    for ao in atom_aos:
        bvec = ao.bvec
        if bvec.bv_id not in bv_labels:
            bv_labels[bvec.bv_id] = True
            bvecs += [bvec]
    return sorted(bvecs, key=lambda bvec : bvec.bv_id)

def count_orbs(atom_aos, num_shells = 6):
    ''' Rewrite without the extra orb_matrix infrastructure? '''
    occ_count = orb_matrix(0)
    occ_count[num_shells-1, 0, 0] = 0;
    for ao in atom_aos:
        n, l, m = ao.quant_nums
        occ_count[n, l, m] += 1
#        if numerical:
#            occ_count[l+1, l, m] += 1
#        else:
#            occ_count[n, l, m] += 1
    return occ_count

def occ_orbs_str(aos, atom_type, num_shells = 6):
    atom_aos = get_atom_aos(aos, atom_type)
    if not atom_aos:
        raise Exception("Atom type '"+str(atom_type)+
            "' not found in set of basis vectors.")
    else:
        orb_count = count_orbs(atom_aos, num_shells)
        return str(orb_count) 

def bf_str(aos, atom_type, gto_type = 'numerical'):
    atom_aos = get_atom_aos(aos, atom_type)
    if not atom_aos:
        raise Exception("Atom type '"+str(atom_type)+
            "' not found in set of basis vectors.")
    return ' '.join([str(ao.bvec.bv_id+1) for ao in atom_aos])

def bf_str_all(aos, gto_type = 'numerical'):
    return ' '.join([str(ao.bvec.bv_id+1) for ao in aos])

def radial_bf_vals(aos, atom_type, grid):
    atom_bvecs = aos2atom_bvecs(aos, atom_type)
    vals = []
    if not atom_bvecs:
        raise Exception("Atom type '"+str(atom_type)+
            "' not found in set of basis vectors.")
    else:
        for bv in atom_bvecs:
            for cgto in bv.gto_ctrs:
                vals += [[cgto(r) for r in grid]]
    return numpy.array(vals)

def radial_grid(start, end, num_pts, x):
    r0 = (end - start)/(x**(num_pts-1) - 1)
    return [r0*(pow(x, i) - 1)+start for i in range(0, num_pts)]

def aos2mo_coeffs(aos):
    '''
    Prints the mo_coeffs.
    Each column corresponds to an atomic orbital. Columns are printed in the 
    same order as the atomic orbitals.
    '''
    return numpy.column_stack(tuple(ao.mo_coeffs for ao in aos))
