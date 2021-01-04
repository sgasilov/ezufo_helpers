BMIT helper scripts for uCT data processing.

1) ezmview separates sequence of images into flats/darks/tomo directories
It is assumed that one CT scan in the sequence is composed as following:
First x images are flats, y images are darks, and z projections plus extra x2 flats in the end.
If there are more than one CT scan in the image sequence it is assumed that tailing flats
are shared between two consecutive scans, e.g. tailing flats of scan1 are treated as
heading flats of scan2

2) ezstitch can be used for several stitching tasks. Input directory must contain
one level of subdirectories each of which must contain tif files which will be processed.

3) ez360_find_overlap helps to find overlap in 360 scans with parallel beam (a.k.a.
half-acquisition mode or offset scan).

4) ez360_multi_stitch is for batch stitching of images acquired in 360 scans.
Input directory is supposed to contain two level of subdirectories. The first level
represents all 360 scan which must be processed and the depth two level are directories
with tif files which will be processed (e.g. z00, z01, z02, ... each of which contains
flats/darks/tomo triplets with camera frames)
