#!/usr/bin/python
# Calculation.py
# Robert C Fritzen - Dpt. Geographic & Atmospheric Sciences
#
# This class instance handles the parallel calculation routines for dask
#  - Notes on how this implementation is handled is shown here:
#     https://github.com/NCAR/wrf-python/wiki/How-to-add-dask-support

import numpy as np
import numpy.ma as ma
import xarray
import dask.array as da
from dask.array import map_blocks
from wrf import Constants, ConversionFactors
from wrf.constants import default_fill
from ArrayTools import wrapped_unstagger, wrapped_either, wrapped_lat_varname, wrapped_lon_varname
		
"""
	This block contains simple wrappers for basic mathematical operations, this is needed to support
	 basic calculation routines that are not thread-safe in the wrf-python library so dask can
	 properly handle these in large scale computing environments
"""
# Wrapped call for simple addition
def wrapped_add(base, add):
	return base + add	
	
# Wrapped call for simple subtraction
def wrapped_sub(base, sub):
	return base - sub
	
# Wrapped call for simple multiplication
def wrapped_mul(base, prod):
	return base * prod

# Wrapped call for simple division
def wrapped_div(base, div):
	return base / div
	
"""
	This block of code is focused on handling the "gather" routines for specific variables
	
	These are wrapped calls to specific functions with omp support enabled to allow for multiprocessing
	 on the specific function calls.
"""
def slp_wrap(destag_ph, tk, full_p, qvapor, omp_threads=1):
	from wrf.extension import _slp, omp_set_num_threads

	omp_set_num_threads(omp_threads)
	result = _slp(destag_ph, tk, full_p, qvapor)

	return result	

def tk_wrap(full_p, full_t, omp_threads=1):
	from wrf.extension import _tk, omp_set_num_threads

	omp_set_num_threads(omp_threads)
	result = _tk(full_p, full_t)

	return result

def td_wrap(full_p, qvapor, omp_threads=1):
	from wrf.extension import _td, omp_set_num_threads

	omp_set_num_threads(omp_threads)
	result = _td(full_p, qvapor)

	return result		
	
def tv_wrap(temp_k, qvapor, omp_threads=1):
	from wrf.extension import _tv, omp_set_num_threads

	omp_set_num_threads(omp_threads)
	result = _tv(temp_k, qvapor)

	return result		
	
def wetbulb_wrap(full_p, tk, qv, omp_threads=1):
	# NOTE: _wetbulb is potentially not thread-safe, this may require a re-write at some point, but just to be aware.
	from wrf.extension import _wetbulb, omp_set_num_threads

	omp_set_num_threads(omp_threads)
	result = _wetbulb(full_p, tk, qv)

	return result			
	
def dbz_wrap(full_p, tk, qv, qr, qs, qg, sn0, ivarint, iliqskin, omp_threads=1):
	from wrf.extension import _dbz, omp_set_num_threads

	omp_set_num_threads(omp_threads)
	result = _dbz(full_p, tk, qv, qr, qs, qg, sn0, ivarint, iliqskin)

	return result
	
def srh_wrap(u1, v1, z1, ter, lats, top, omp_threads=1):
	from wrf.extension import _srhel, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)
	result = _srhel(u1, v1, z1, ter, lats, top)
	
	return result

def udhel_wrap(zp, mapfct, u, v, wstag, dx, dy, bottom, top, omp_threads=1):
	from wrf.extension import _udhel, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)
	result = _udhel(zp, mapfct, u, v, wstag, dx, dy, bottom, top)
	
	return result
	
def cape_wrap(p_hpa, tk, qv, z, ter, psfc_hpa, missing, i3dflag, ter_follow, omp_threads=1):
	# NOTE: _cape is potentially not thread-safe, this may require a re-write at some point, but just to be aware.
	from wrf.extension import _cape, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)
	result = _cape(p_hpa, tk, qv, z, ter, psfc_hpa, missing, i3dflag, ter_follow)
	
	return result

def omega_wrap(qv, tk, wa, full_p, omp_threads=1):
	from wrf.extension import _omega, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)	
	result = _omega(qv, tk, wa, full_p)
	
	return result
	
def pw_wrap(full_p, tv, qv, ht, omp_threads=1):
	from wrf.extension import _pw, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)	
	result = _pw(full_p, tv, qv, ht)
	
	return result
	
def rh_wrap(qvapor, full_p, tk, omp_threads=1):
	from wrf.extension import _rh, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)	
	result = _rh(qvapor, full_p, tk)
	
	return result	

def avo_wrap(u, v, msfu, msfv, msfm, cor, dx, dy, omp_threads=1):
	from wrf.extension import _avo, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)	
	result = _avo(u, v, msfu, msfv, msfm, cor, dx, dy)
	
	return result
	
def pvo_wrap(u, v, full_t, full_p, msfu, msfv, msfm, cor, dx, dy, omp_threads=1):
	from wrf.extension import _pvo, omp_set_num_threads
	
	omp_set_num_threads(omp_threads)	
	result = _pvo(u, v, msfu, msfv, msfm, cor, dx, dy)
	
	return result	

"""
	This block of code handles the multiprocessed variable calculation routines.
	 -> These are wrapped calls of the original g_func* methods in the wrf-python library
"""
def get_theta(daskArray, omp_threads=1, num_workers=1):
	t = daskArray["T"].data[0]
	full_t = map_blocks(wrapped_add, t, Constants.T_BASE, omp_threads, dtype=t.dtype)
	
	return full_t.compute(num_workers=num_workers)

def get_tk(daskArray, omp_threads, num_workers=1):
	t = daskArray["T"].data[0]
	p = daskArray["P"].data[0]
	pb = daskArray["PB"].data[0]
	dtype = t.dtype
	
	full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)	
	
	del(t)
	del(p)
	del(pb)
	
	tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
	return tk.compute(num_workers=num_workers)

def get_tv(daskArray, omp_threads=1, num_workers=1):
	t = daskArray["T"].data[0]
	p = daskArray["P"].data[0]
	pb = daskArray["PB"].data[0]
	qv = daskArray["QVAPOR"].data[0]
	dtype = t.dtype

	full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)
	
	del(t)
	del(p)
	del(pb)
	
	tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
	tv = map_blocks(tv_wrap, tk, qv, omp_threads, dtype=dtype)
	return tv.compute(num_workers=num_workers)	
	
def get_tw(daskArray, omp_threads=1, num_workers=1):
	t = daskArray["T"].data[0]
	p = daskArray["P"].data[0]
	pb = daskArray["PB"].data[0]
	qv = daskArray["QVAPOR"].data[0]
	dtype = t.dtype
	
	full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)	
	
	del(t)
	del(p)
	del(pb)
	
	tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
	tw = map_blocks(wetbulb_wrap, tk, qv, omp_threads, dtype=dtype)
	return tw.compute(num_workers=num_workers)
	
def get_cape3d(daskArray, omp_threads=1, num_workers=1):	
    missing = default_fill(np.float64)

    t = daskArray["T"].data[0]
    p = daskArray["P"].data[0]
    pb = daskArray["PB"].data[0]
    qv = daskArray["QVAPOR"].data[0]
    ph = daskArray["PH"].data[0]
    phb = daskArray["PHB"].data[0]
    ter = daskArray["HGT"].data[0]
    psfc = daskArray["PSFC"].data[0]
    dtype = p.dtype

    full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
    full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)
    tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
    
    del(full_t)
    del(t)
    del(p)

    geopt = map_blocks(wrapped_add, ph, phb, dtype=dtype)
    geopt_unstag = wrapped_unstagger(geopt, -3)
    z = map_blocks(wrapped_div, geopt_unstag, Constants.G, dtype=dtype)
    
    del(ph)
    del(phb)
    del(geopt)
    del(geopt_unstag)

    p_hpa = map_blocks(wrapped_mul, full_p, ConversionFactors.PA_TO_HPA, dtype=dtype)
    psfc_hpa = map_blocks(wrapped_mul, psfc, ConversionFactors.PA_TO_HPA, dtype=dtype)
    
    del(full_p)
    del(psfc)

    i3dflag = 1
    ter_follow = 1

    cape_cin = map_blocks(cape_wrap, p_hpa, tk, qv, z, ter, psfc_hpa, missing, i3dflag, ter_follow, omp_threads, dtype=dtype)
    comp = cape_cin.compute(num_workers=num_workers)
    
    return comp
	
def get_dbz(daskArray, use_varint=False, use_liqskin=False, omp_threads=1, num_workers=1):
    t = daskArray["T"].data[0]
    p = daskArray["P"].data[0]
    pb = daskArray["PB"].data[0]
    qv = daskArray["QVAPOR"].data[0]
    qr = daskArray["QRAIN"].data[0]

    dtype = t.dtype
    
    try:
        qs = daskArray["QSNOW"].data[0]
    except KeyError:
        qs = da.zeros(qv.shape, qv.dtype)

    try:
        qgraup = daskArray["QGRAUP"].data[0]
    except KeyError:
        qgraup = da.zeros(qv.shape, qv.dtype)

    full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=t.dtype)
    full_p = map_blocks(wrapped_add, p, pb, dtype=p.dtype)
    tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=p.dtype)

    sn0 = 1 if qs.any() else 0
    ivarint = 1 if use_varint else 0
    iliqskin = 1 if use_liqskin else 0
    
    del(t)
    del(p)
    del(pb)

    dbz = map_blocks(dbz_wrap, full_p, tk, qv, qr, qs, qgraup, sn0, ivarint, iliqskin, omp_threads, dtype=dtype)
    return dbz.compute(num_workers=num_workers)

def get_dewpoint(daskArray, omp_threads=1, num_workers=1):
	p = daskArray["P"].data[0]
	pb = daskArray["PB"].data[0]
	qvapor = daskArray["QVAPOR"][0]	
	dtype = p.dtype
	
	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)
	full_p_div = map_blocks(wrapped_mul, full_p, 0.01, dtype=dtype)
	
	del(p)
	del(pb)
	del(full_p)
	
	qvapor = qvapor.where(qvapor >= 0, 0)
	
	td = map_blocks(td_wrap, full_p_div, qvapor.data, omp_threads, dtype=dtype)
	return td.compute(num_workers=num_workers)
	
def get_geoht(daskArray, height=True, msl=True, omp_threads=1, num_workers=1):
	varname = wrapped_either(daskArray, ("PH", "GHT"))
	if varname == "PH":
		ph = daskArray["PH"].data[0]
		phb = daskArray["PHB"].data[0]
		hgt = daskArray["HGT"].data[0]
		dtype = ph.dtype
		geopt = map_blocks(wrapped_add, ph, phb, dtype=dtype)
		geopt_f = wrapped_unstagger(geopt, -3)
	else:
		geopt = daskArray["GHT"].data[0]
		hgt = daskArray["HGT_M"].data[0]
		dtype = geopt.dtype
		geopt_f = map_blocks(wrapped_mul, geopt, Constants.G, dtype=dtype)

	if height:
		if msl:
			mslh = map_blocks(wrapped_div, geopt_f, Constants.G, dtype=dtype)
			return mslh.compute(num_workers=num_workers)
		else:
			# Due to broadcasting with multifile/multitime, the 2D terrain
			# array needs to be reshaped to a 3D array so the right dims
			# line up
			new_dims = list(hgt.shape)
			new_dims.insert(-2, 1)
			hgt = hgt.reshape(new_dims)

			mslh = map_blocks(wrapped_div, geopt_f, Constants.G, dtype=dtype)
			mslh_f = map_blocks(wrapped_sub, mslh, hgt, dtype=dtype)
			return mslh_f.compute(num_workers=num_workers)
	else:
		return geopt_f.compute(num_workers=num_workers)	

def get_height(daskArray, msl=True, omp_threads=1, num_workers=1):
	return get_geoht(daskArray, height=True, msl=msl, omp_threads=omp_threads, num_workers=num_workers)
	
def get_height_agl(daskArray, omp_threads=1, num_workers=1):
	return get_geoht(daskArray, height=True, msl=False, omp_threads=omp_threads, num_workers=num_workers)
	
def get_srh(daskArray, top=3000.0, omp_threads=1, num_workers=1):
    lat_VN = wrapped_lat_varname(daskArray, stagger=None)
    lats = daskArray[lat_VN].data[0]

    hgt = daskArray["HGT"].data[0]
    ph = daskArray["PH"].data[0]
    phb = daskArray["PHB"].data[0]
    dtype = ph.dtype

    varname = wrapped_either(daskArray, ("U", "UU"))
    uS = daskArray[varname].data[0]
    u = wrapped_unstagger(uS, -1)

    varname = wrapped_either(daskArray, ("V", "VV"))
    vS = daskArray[varname].data[0]
    v = wrapped_unstagger(vS, -2)

    geopt = map_blocks(wrapped_add, ph, phb, dtype=dtype)
    geopt_f = wrapped_unstagger(geopt, -3, num_workers)
    z = map_blocks(wrapped_div, geopt_f, Constants.G, dtype=dtype)

    del(ph)
    del(phb)
    del(geopt)
    del(geopt_f)

    u1 = np.ascontiguousarray(u[..., ::-1, :, :])
    v1 = np.ascontiguousarray(v[..., ::-1, :, :])
    z1 = np.ascontiguousarray(z[..., ::-1, :, :])

    del(u)
    del(v)
    del(z)

    srh = map_blocks(srh_wrap, u1, v1, z1, hgt, lats, top, omp_threads, dtype=dtype)
    return srh.compute(num_workers=num_workers)
	
def get_udhel(daskArray, bottom=2000.0, top=5000.0, omp_threads=1, num_workers=1):
	wstag = daskArray["W"].data[0]
	ph = daskArray["PH"].data[0]
	phb = daskArray["PHB"].data[0]
	dtype = ph.dtype
	
	mapfct = daskArray["MAPFAC_M"].data[0]
	dx = daskArray.DX
	dy = daskArray.DY

	varname = wrapped_either(daskArray, ("U", "UU"))
	uS = daskArray[varname].data[0]
	u = wrapped_unstagger(uS, -1)

	varname = wrapped_either(daskArray, ("V", "VV"))
	vS = daskArray[varname].data[0]
	v = wrapped_unstagger(vS, -2)	
	
	del(uS)
	del(vS)

	geopt = map_blocks(wrapped_add, ph, phb, dtype=dtype)
	geopt_f = wrapped_unstagger(geopt, -3)	
	zp = map_blocks(wrapped_div, geopt_f, Constants.G, dtype=dtype)	

	del(ph)
	del(phb)
	del(geopt)
	del(geopt_f)
	
	udhel = map_blocks(udhel_wrap, zp, mapfct, u, v, wstag, dx, dy, bottom, top, omp_threads, dtype=dtype)
	return udhel.compute(num_workers=num_workers)
	
def get_omega(daskArray, omp_threads=1, num_workers=1):
	t = daskArray["T"].data[0]
	p = daskArray["P"].data[0]
	w = daskArray["W"].data[0]
	pb = daskArray["PB"].data[0]
	qv = daskArray["QVAPOR"].data[0]
	
	dtype = t.dtype

	wa = wrapped_unstagger(w, -3)
	full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)	
	tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
	
	del(t)
	del(p)
	del(pb)
	del(full_t)

	omega = map_blocks(omega_wrap, qv, tk, wa, full_p, omp_threads, dtype=dtype)
	return omega.compute(num_workers=num_workers)
	
def get_accum_precip(daskArray, omp_threads=1, num_workers=1):
	rainc = daskArray["RAINC"].data[0]
	rainnc = daskArray["RAINNC"].data[0]	
	rainsum = map_blocks(wrapped_add, rainc, rainnc, dtype=rainc.dtype)
	return rainsum.compute(num_workers=num_workers)
	
def get_pw(daskArray, omp_threads=1, num_workers=1):
	t = daskArray["T"].data[0]
	p = daskArray["P"].data[0]
	pb = daskArray["PB"].data[0]
	ph = daskArray["PH"].data[0]
	phb = daskArray["PHB"].data[0]
	qv = daskArray["QVAPOR"].data[0]
	
	dtype = t.dtype

	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)
	full_ph = map_blocks(wrapped_add, ph, pb, dtype=dtype)
	ht = map_blocks(wrapped_div, full_ph, Constants.G, dtype=dtype)
	full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
	
	del(p)
	del(pb)
	del(ph)

	tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
	tv = map_blocks(tv_wrap, tk, qv, omp_threads, dtype=dtype)
	
	del(full_t)
	del(tk)

	pw = map_blocks(pw_wrap, full_p, tv, qv, ht, omp_threads, dtype=dtype)
	return pw.compute(num_workers=num_workers)
	
def get_rh(daskArray, omp_threads=1, num_workers=1):
	t = daskArray["T"].data[0]
	p = daskArray["P"].data[0]
	pb = daskArray["PB"].data[0]
	qvapor = daskArray["QVAPOR"]
	dtype = t.dtype

	full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)
	
	del(t)
	del(p)
	del(pb)

	qvapor = qvapor.where(qvapor >= 0, 0)

	tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
	del(full_t)
	
	rh = map_blocks(rh_wrap, qvapor.data, full_p, tk, omp_threads, dtype=dtype)
	return rh.compute(num_workers=num_workers)
	
def get_slp(daskArray, omp_threads=1, num_workers=1):
    t = daskArray["T"].data[0]
    p = daskArray["P"].data[0]
    pb = daskArray["PB"].data[0]
    qvapor = daskArray["QVAPOR"][0]
    ph = daskArray["PH"].data[0]
    phb = daskArray["PHB"].data[0]
    dtype = p.dtype

    full_t = map_blocks(wrapped_add, t, Constants.T_BASE, dtype=dtype)
    full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)
    qvapor = qvapor.where(qvapor >= 0, 0)
    
    del(t)
    del(p)
    del(pb)

    pre_full_ph = map_blocks(wrapped_add, ph, phb, dtype=dtype)
    full_ph = map_blocks(wrapped_div, pre_full_ph, Constants.G, dtype=dtype)
    destag_ph = wrapped_unstagger(full_ph, -3) 
    
    del(full_ph)
    del(ph)
    del(phb)

    tk = map_blocks(tk_wrap, full_p, full_t, omp_threads, dtype=dtype)
    slp = map_blocks(slp_wrap, destag_ph, tk, full_p, qvapor.data, omp_threads, dtype=dtype)
    slp_calc = slp.compute(num_workers=num_workers)
    
    return slp_calc
	
def get_avo(daskArray, omp_threads=1, num_workers=1):
	u = daskArray["U"].data[0]
	v = daskArray["V"].data[0]
	msfu = daskArray["MAPFAC_U"].data[0]
	msfv = daskArray["MAPFAC_V"].data[0]
	msfm = daskArray["MAPFAC_M"].data[0]
	cor = daskArray["F"].data[0]

	dx = daskArray.DX
	dy = daskArray.DY
	
	dtype = u.dtype

	avo = map_blocks(avo_wrap, u, v, msfu, msfv, msfm, cor, dx, dy, omp_threads, dtype=dtype)
	return avo.compute(num_workers=num_workers)
	
def get_rvor(daskArray, omp_threads=1, num_workers=1):
	u = daskArray["U"].data[0]
	v = daskArray["V"].data[0]
	msfu = daskArray["MAPFAC_U"].data[0]
	msfv = daskArray["MAPFAC_V"].data[0]
	msfm = daskArray["MAPFAC_M"].data[0]
	cor = daskArray["F"].data[0]

	dx = daskArray.DX
	dy = daskArray.DY

	dtype = u.dtype

	avo = map_blocks(avo_wrap, u, v, msfu, msfv, msfm, cor, dx, dy, omp_threads, dtype=dtype)
	rvor = map_blocks(wrapped_sub, avo, cor, dtype=dtype)

	return rvor.compute(num_workers=num_workers)
	
def get_pvo(daskArray, omp_threads=1, num_workers=1):
	u = daskArray["U"].data[0]
	v = daskArray["V"].data[0]
	t = daskArray["T"].data[0]
	p = daskArray["P"].data[0]
	pb = daskArray["PB"].data[0]
	msfu = daskArray["MAPFAC_U"].data[0]
	msfv = daskArray["MAPFAC_V"].data[0]
	msfm = daskArray["MAPFAC_M"].data[0]
	cor = daskArray["F"].data[0]

	dx = daskArray.DX
	dy = daskArray.DY
	
	dtype=u.dtype

	full_t = map_blocks(wrapped_add, t, 300, dtype=dtype)
	full_p = map_blocks(wrapped_add, p, pb, dtype=dtype)
	
	del(t)
	del(p)
	del(pb)

	pvo = map_blocks(pvo_wrap, u, v, full_t, full_p, msfu, msfv, msfm, cor, dx, dy, omp_threads, dtype=dtype)
	return pvo.compute(num_workers=num_workers)