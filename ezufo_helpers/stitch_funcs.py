'''
Last modified on Dec 2, 2020

@author: sergei gasilov
'''
import glob
import os
import argparse
import sys
import numpy as np
import tifffile
from ezufo_helpers.util import read_image
import time
import multiprocessing as mp
from functools import partial
import re
import warnings
import time


def prepare(args):
    hmin, hmax = 0.0, 0.0
    if args.gray256:
        if args.hmin==args.hmax:
            raise ValueError('Define hmin and hmax correctly in order to convert to 8bit')
        else:
            hmin, hmax = args.hmin, args.hmax
    start, stop, step = [int(value) for value in args.slices.split(',')]
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    Vsteps = sorted(os.listdir(args.input))
    #determine input data type
    tmp = os.path.join(args.input, Vsteps[0], args.typ, '*.tif')
    tmp = sorted(glob.glob(tmp))[0]
    indtype = type(read_image(tmp)[0][0])

    if args.ort:
        for vstep in Vsteps:
            in_name = os.path.join(args.input, vstep, args.typ)
            out_name = os.path.join(args.tmpdir, vstep, args.typ, 'sli-%04i.tif')
            cmd = 'tofu sinos --projections {} --output {}'\
                    .format(in_name, out_name)
            cmd += " --y {} --height {} --y-step {}"\
                    .format(start, stop-start, step)
            cmd += " --output-bytes-per-file 0"
            os.system(cmd)
            time.sleep(10)
        indir = args.tmpdir
    else:
        indir = args.input
    return indir, hmin, hmax, start, stop, step, indtype


def exec_sti_mp(start, step, N,Nnew, Vsteps, indir, dx,M, args, ramp, hmin, hmax, indtype, j):
    index=start+j*step
    Large = np.empty(( Nnew*len(Vsteps)+dx,M), dtype=np.float32)
    for i, vstep in enumerate(Vsteps[:-1]):
        tmp = os.path.join(indir,Vsteps[i], args.typ, '*.tif')
        tmp1 = os.path.join(indir,Vsteps[i+1], args.typ,'*.tif')
        if args.ort:
            tmp = sorted(glob.glob(tmp))[j]
            tmp1 = sorted(glob.glob(tmp1))[j]
        else:
            tmp = sorted(glob.glob(tmp))[index]
            tmp1 = sorted(glob.glob(tmp1))[index]
        first=read_image(tmp)
        second=read_image(tmp1)
        if args.flip: #sample moved downwards
            first, second = np.flipud(first), np.flipud(second)

        k = np.mean(first[N - dx:, :]) / np.mean(second[:dx, :])
        second = second * k

        a, b, c = i*Nnew, (i+1)*Nnew, (i+2)*Nnew
        Large[a:b,:] = first[:N-dx,:]
        Large[b:b+dx,:] = np.transpose(np.transpose(first[N-dx:,:]) * (1 - ramp) + np.transpose(second[:dx,:]) * ramp)
        Large[b+dx:c+dx,:] = second[dx:,:]

    pout = os.path.join(args.output, args.typ+'-sti-{:>04}.tif'.format(index))
    if not args.gray256:
        tifffile.imsave(pout, Large.astype(indtype))
    else:
        Large =  255.0/(hmax-hmin) * (np.clip(Large, hmin, hmax) - hmin)
        tifffile.imsave(pout, Large.astype(np.uint8))

def main_sti_mp(args):
    if args.ort:
        print "Creating orthogonal sections"
    indir, hmin, hmax, start, stop, step, indtype = prepare(args)
    dx=int(args.reprows)
    #second: stitch them
    Vsteps=sorted( os.listdir( indir ))
    tmp=glob.glob(os.path.join(indir,Vsteps[0],args.typ, '*.tif'))[0]
    first=read_image(tmp)
    N,M=first.shape
    Nnew=N-dx
    ramp = np.linspace(0, 1, dx)

    J=range(int((stop-start)/step))
    pool = mp.Pool(processes=mp.cpu_count())
    exec_func = partial(exec_sti_mp, start, step, N, Nnew, \
            Vsteps, indir, dx,M, args, ramp, hmin, hmax, indtype)
    print "Adjusting and stitching"
    #start = time.time()
    pool.map(exec_func, J)
    print "========== Done =========="

def make_buf(tmp,l,a,b):
    first=read_image(tmp)
    N,M=first[a:b,:].shape
    return np.empty((N*l,M),dtype=first.dtype), N, first.dtype

def exec_conc_mp(start, step, example_im, l, args, zfold, indir, j):
    index=start+j*step
    Large, N, dtype = make_buf( example_im, l, args.r1, args.r2)
    for i, vert in enumerate(zfold):
        tmp = os.path.join(indir,vert,args.typ, '*.tif')
        if args.ort:
            fname=sorted(glob.glob(tmp))[j]
        else:
            fname=sorted(glob.glob(tmp))[index]
        frame=read_image(fname)[args.r1:args.r2,:]
        if args.flip: #sample moved downwards
            Large[i*N:N*(i+1),:]=np.flipud(frame)
        else:
            Large[i*N:N*(i+1),:]=frame

    pout = os.path.join(args.output, args.typ+'-sti-{:>04}.tif'.format(index))
    #print "input data type {:}".format(dtype)
    tifffile.imsave(pout, Large)

def main_conc_mp(args):
    if args.ort:
        print "Creating orthogonal sections"
    #start = time.time()
    indir, hmin, hmax, start, stop, step, indtype = prepare(args)
    #if args.ort:
    #    print "Orthogonal sections created in {:.01f} sec".format(time.time()-start)
    subdirs = [dI for dI in os.listdir(args.input) \
            if os.path.isdir(os.path.join(args.input,dI))]
    zfold=sorted(subdirs)
    l=len(zfold)
    tmp=glob.glob(os.path.join(indir,zfold[0], args.typ, '*.tif'))
    J=range(int((stop-start)/step))
    pool = mp.Pool(processes=mp.cpu_count())
    exec_func = partial(exec_conc_mp, start, step, tmp[0], l, args, zfold, indir )
    print "Concatenating"
    #start = time.time()
    pool.map(exec_func, J)
    #print "Images stitched in {:.01f} sec".format(time.time()-start)
    print "========== Done =========="


############################## HALF ACQ ##############################
def stitch(first, second, axis, crop):
    h, w = first.shape
    if axis > w / 2:
        dx = int(2 * (w - axis) + 0.5)
    else:
        dx = int(2 * axis + 0.5)
        tmp = np.copy(first)
        first = second
        second = tmp
    result = np.empty((h, 2 * w - dx), dtype=first.dtype)
    ramp = np.linspace(0, 1, dx)

    # Mean values of the overlapping regions must match, which corrects flat-field inconsistency
    # between the two projections
    k = np.mean(first[:, w - dx:]) / np.mean(second[:, :dx])
    second = second * k

    result[:, :w - dx] = first[:, :w - dx]
    result[:, w - dx:w] = first[:, w - dx:] * (1 - ramp) + second[:, :dx] * ramp
    result[:, w:] = second[:, dx:]

    return result[:,slice(int(crop),int(2*(w - axis) - crop),1)]

def st_mp_idx(offst, ax, crop, in_fmt, out_fmt, idx):
    #we pass index and formats as argument
    first = read_image(in_fmt.format(idx))
    second = read_image(in_fmt.format(idx+offst))[:, ::-1]
    stitched = stitch(first, second, ax, crop)
    tifffile.imsave(out_fmt.format(idx), stitched)

def main_360_mp_depth1(args):
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    #subdirs=sorted(os.listdir(args.input))
    subdirs = [dI for dI in os.listdir(args.input) \
            if os.path.isdir(os.path.join(args.input,dI))]
    for i, sdir in enumerate(subdirs):
        names = sorted(glob.glob(os.path.join(args.input,sdir, '*.tif')))
        num_projs = len(names)
        if num_projs<2:
            warnings.warn("Warning: less than 2 files")
        print '{} files in {}'.format(num_projs, sdir)

        os.makedirs(os.path.join(args.output,sdir))
        out_fmt = os.path.join(args.output, sdir, 'sti-{:>04}.tif')

        # extraxt input file format
        firstfname = names[0]
        firstnum = re.match('.*?([0-9]+)$', firstfname[:-4]).group(1)
        n_dgts = len(firstnum) #number of significant digits
        idx0 = int(firstnum)
        trnc_len = n_dgts + 4 #format + .tif
        in_fmt = firstfname[:-trnc_len] + '{:0'+str(n_dgts)+'}.tif'

        pool = mp.Pool(processes=mp.cpu_count())
        #exec_func = partial(st_mp, num_projs,args.ax, out_fmt)
        offst = int(num_projs / 2)
        exec_func = partial(st_mp_idx, offst, args.ax, 0, in_fmt, out_fmt)
        idxs = range(idx0, idx0+offst)
        # double check if names correspond - to remove later
        for nmi in idxs:
            #print(names[nmi-idx0], in_fmt.format(nmi))
            if names[nmi-idx0] != in_fmt.format(nmi):
                print('somthing wrong with file name format')
                continue
        #pool.map(exec_func, names[0:num_projs/2])
        pool.map(exec_func, idxs)

    print "========== Done =========="


def main_360_mp_depth2(args):
    subdirs = [dI for dI in os.listdir(args.input) \
               if os.path.isdir(os.path.join(args.input, dI))]
    print
    subdirs

    if len(glob.glob(os.path.join(args.input, 'z??'))) > 0:

        num_slices = len(glob.glob(os.path.join(args.input, 'z??')))
        axis_incr = float((args.ax2 - args.ax1) / float(num_slices - 1))

        print
        str(num_slices) + " slices detected. stitching all slices..."

        for j in range(0, num_slices):
            if not os.path.exists(args.output):
                os.makedirs(os.path.join(args.output, "z" + str(j).zfill(2)))
            out_dir = os.path.join(args.output, "z" + str(j).zfill(2))

            curr_ax = args.ax1 + j * axis_incr

            if args.crop == True:
                if axis_incr < 0:
                    crop_amt = abs(args.ax1 - round(curr_ax))
                else:
                    crop_amt = abs(args.ax2 - round(curr_ax))
            else:
                crop_amt = 0
            # subdirs=sorted(os.listdir(args.input))

            subdirs = [dI for dI in os.listdir(os.path.join(args.input, "z" + str(j).zfill(2))) \
                       if os.path.isdir(os.path.join(args.input, "z" + str(j).zfill(2), dI))]

            print
            "processing slice: z" + str(j).zfill(2) + " using axis: " + str(
                round(curr_ax)) + " and cropping by: " + str(crop_amt)
            print
            "axis_incr = " + str(axis_incr)
            print
            "curr_ax = " + str(curr_ax)

            for i, sdir in enumerate(subdirs):
                names = sorted(glob.glob(os.path.join(args.input, "z" + str(j).zfill(2), sdir, '*.tif')))
                num_projs = len(names)
                if num_projs < 2:
                    warnings.warn("Warning: less than 2 files")
                print
                '{} files in {}'.format(num_projs, sdir)

                os.makedirs(os.path.join(out_dir, sdir))
                out_fmt = os.path.join(out_dir, sdir, 'sti-{:>04}.tif')

                # extract input file format
                firstfname = names[0]
                firstnum = re.match('.*?([0-9]+)$', firstfname[:-4]).group(1)
                n_dgts = len(firstnum)  # number of significant digits
                idx0 = int(firstnum)
                trnc_len = n_dgts + 4  # format + .tif
                in_fmt = firstfname[:-trnc_len] + '{:0' + str(n_dgts) + '}.tif'

                pool = mp.Pool(processes=mp.cpu_count())
                # exec_func = partial(st_mp, num_projs,args.ax, out_fmt)
                offst = int(num_projs / 2)
                exec_func = partial(st_mp_idx, offst, round(curr_ax), round(crop_amt), in_fmt, out_fmt)
                idxs = range(idx0, idx0 + offst)
                # double check if names correspond - to remove later
                for nmi in idxs:
                    # print(names[nmi-idx0], in_fmt.format(nmi))
                    if names[nmi - idx0] != in_fmt.format(nmi):
                        print('somthing wrong with file name format')
                        continue
                # pool.map(exec_func, names[0:num_projs/2])
                pool.map(exec_func, idxs)

            print
            "========== Done =========="



    else:
        if not os.path.exists(args.output):
            os.makedirs(args.output)
        # subdirs=sorted(os.listdir(args.input))

        for i, sdir in enumerate(subdirs):
            names = sorted(glob.glob(os.path.join(args.input, sdir, '*.tif')))
            num_projs = len(names)
            if num_projs < 2:
                warnings.warn("Warning: less than 2 files")
            print
            '{} files in {}'.format(num_projs, sdir)

            os.makedirs(os.path.join(args.output, sdir))
            out_fmt = os.path.join(args.output, sdir, 'sti-{:>04}.tif')

            # extract input file format
            firstfname = names[0]
            firstnum = re.match('.*?([0-9]+)$', firstfname[:-4]).group(1)
            n_dgts = len(firstnum)  # number of significant digits
            idx0 = int(firstnum)
            trnc_len = n_dgts + 4  # format + .tif
            in_fmt = firstfname[:-trnc_len] + '{:0' + str(n_dgts) + '}.tif'

            pool = mp.Pool(processes=mp.cpu_count())
            # exec_func = partial(st_mp, num_projs,args.ax, out_fmt)
            offst = int(num_projs / 2)
            exec_func = partial(st_mp_idx, offst, args.ax, in_fmt, out_fmt)
            idxs = range(idx0, idx0 + offst)
            # double check if names correspond - to remove later
            for nmi in idxs:
                # print(names[nmi-idx0], in_fmt.format(nmi))
                if names[nmi - idx0] != in_fmt.format(nmi):
                    print('somthing wrong with file name format')
                    continue
            # pool.map(exec_func, names[0:num_projs/2])
            pool.map(exec_func, idxs)

        print
        "========== Done =========="

