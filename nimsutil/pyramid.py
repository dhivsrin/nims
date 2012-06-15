#!/usr/bin/env python
#
# @author:  Bob Dougherty
#           Gunnar Schaefer

"""
The CNI pyramid viewer uses PanoJS for the front-end.
See: http://www.dimin.net/software/panojs/
"""

from __future__ import print_function

import os
import argparse

import math
import Image
import numpy
import nibabel


class ImagePyramidError(Exception):
    pass


class ImagePyramid(object):

    """
    Generate a panojs-style image pyramid of a 2D montage of slices from a >=3D dataset (usually a NIfTI file).

    Example:
        import pyramid
        pyr = pyramid.ImagePyramid('t1.nii.gz')
        pyr.generate()
    """

    def __init__(self, filename, tile_size=256, log=None):
        self.data = nibabel.load(filename).get_data()
        self.tile_size = tile_size
        self.log = log

    def generate(self, outdir, panojs_url='https://cni.stanford.edu/js/panojs/'):
        """
        Generate a multi-resolution image pyramid, using generate_pyramid(), and the corresponding
        viewer HTML file, using generate_viewer().
        """
        self.generate_montage()
        self.generate_pyramid(outdir)
        self.generate_viewer(os.path.join(outdir, 'index.html'), panojs_url)

    def generate_pyramid(self, outdir):
        """
        Slice up a NIfTI file into a multi-res pyramid of tiles.
        We use the file name convention suitable for PanoJS (http://www.dimin.net/software/panojs/):
        The zoom level (z) is an integer between 0 and n, where 0 is fully zoomed in and n is zoomed out.
        E.g., z=n is for 1 tile covering the whole world, z=n-1 is for 2x2=4 tiles, ... z=0 is the original resolution.
        """
        sx,sy = self.montage.size
        divs = int(numpy.ceil(numpy.log2(max(sx,sy)/self.tile_size)))
        if not os.path.exists(outdir): os.makedirs(outdir)
        for iz in range(divs+1):
            z = divs - iz
            ysize = int(round(float(sy)/pow(2,iz)))
            xsize = int(round(float(ysize)/sy*sx))
            xpieces = int(math.ceil(float(xsize)/self.tile_size))
            ypieces = int(math.ceil(float(ysize)/self.tile_size))
            self.log or print('level %s, size %dx%d, splits %d,%d' % (z, xsize, ysize, xpieces, ypieces))
            # TODO: we don't need to use 'thumbnail' here. This function always returns a square
            # image of the requested size, padding and scaling as needed. Instead, we should resize
            # and chop the image up, with no padding, ever. panojs can handle non-square images
            # at the edges, so the padding is unnecessary and, in fact, a little wrong.
            im = self.montage.copy()
            im.thumbnail([xsize,ysize], Image.ANTIALIAS)
            # Convert the image to grayscale
            im = im.convert("L")
            for x in range(xpieces):
                for y in range(ypieces):
                    tile = im.copy().crop((x*self.tile_size, y*self.tile_size, min((x+1)*self.tile_size,xsize), min((y+1)*self.tile_size,ysize)))
                    tile.save(os.path.join(outdir, ('%03d_%03d_%03d.jpg' % (iz,x,y))), "JPEG", quality=85)

    def generate_viewer(self, outfile, panojs_url):
        """
        Creates a baisc html file for viewing the image pyramid with panojs.
        """
        (x_size,y_size) = self.montage.size
        with open(outfile, 'w') as f:
            f.write('<head>\n<meta http-equiv="imagetoolbar" content="no"/>\n')
            f.write('<style type="text/css">@import url(' + panojs_url + 'styles/panojs.css);</style>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'extjs/ext-core.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'panojs/utils.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'panojs/PanoJS.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'panojs/controls.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'panojs/pyramid_imgcnv.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'panojs/control_thumbnail.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'panojs/control_info.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'panojs/control_svg.js"></script>\n')
            f.write('<script type="text/javascript" src="' + panojs_url + 'viewer.js"></script>\n')
            f.write('<style type="text/css">body { font-family: sans-serif; margin: 0; padding: 10px; color: #000000; background-color: #FFFFFF; font-size: 0.7em; } </style>\n')
            f.write('<script type="text/javascript">\nvar viewer = null;Ext.onReady(function () { createViewer( viewer, "viewer", ".", "", '+str(self.tile_size)+', '+str(x_size)+', '+str(y_size)+' ) } );\n</script>\n')
            f.write('</head>\n<body>\n')
            f.write('<div style="width: 100%; height: 100%;"><div id="viewer" class="viewer" style="width: 100%; height: 100%;" ></div></div>\n')
            f.write('</body>\n</html>\n')

    def generate_montage(self):
        """Full-sized montage of the entire numpy data array."""
        # Figure out the image dimensions and make an appropriate montage.
        # NIfTI images can have up to 7 dimensions. The fourth dimension is
        # by convention always supposed to be time, so some images (RGB, vector, tensor)
        # will have 5 dimensions with a single 4th dimension. For our purposes, we
        # can usually just collapse all dimensions above the 3rd.
        # TODO: we should handle data_type = RGB as a special case.
        # TODO: should we use the scaled data (getScaledData())? (We do some auto-windowing below)

        # This transpose (usually) makes the resulting images come out in a more standard orientation.
        # TODO: we could look at the qto_xyz to infer the optimal transpose for any dataset.
        self.data = self.data.transpose(numpy.concatenate(([1,0],range(2,self.data.ndim))))
        num_images = numpy.prod(self.data.shape[2:])

        self.data = self.data.squeeze()

        if self.data.ndim < 2:
            raise Exception('NIfTI file must have at least 2 dimensions')
        elif self.data.ndim == 2:
            # a single slice: no need to do anything
            num_cols = 1;
            self.data = numpy.atleast_3d(self.data)
        elif self.data.ndim == 3:
            # a simple (x, y, z) volume- set num_cols to produce a square(ish) montage.
            rows_to_cols_ratio = float(self.data.shape[0])/float(self.data.shape[1])
            self.num_cols = int(math.ceil(math.sqrt(float(num_images)) * math.sqrt(rows_to_cols_ratio)))
        elif self.data.ndim >= 4:
            # timeseries (x, y, z, t) or more
            self.num_cols = self.data.shape[2]
            self.data = self.data.transpose(numpy.concatenate(([0,1,3,2],range(4,self.data.ndim)))).reshape(self.data.shape[0], self.data.shape[1], num_images)

        r, c, count = numpy.shape(self.data)
        self.num_rows = int(numpy.ceil(float(count)/float(self.num_cols)))
        montage_array = numpy.zeros((r * self.num_rows, c * self.num_cols))
        image_id = 0
        for k in range(self.num_rows):
            for j in range(self.num_cols):
                if image_id >= count:
                    break
                slice_c, slice_r = j * c, k * r
                montage_array[slice_r:slice_r + r, slice_c:slice_c + c] = self.data[:, :, image_id]
                image_id += 1

        # Auto-window the data by clipping values above and below the following thresholds, then scale to unit8.
        clip_vals = numpy.percentile(montage_array, (20.0, 99.0))
        montage_array = montage_array.clip(clip_vals[0], clip_vals[1])
        montage_array = montage_array-clip_vals[0]
        montage_array = numpy.cast['uint8'](numpy.round(montage_array/(clip_vals[1]-clip_vals[0])*255.0))
        self.montage = Image.fromarray(montage_array)
        # NOTE: the following will crop away edges that contain only zeros. Not sure if we want this.
        self.montage = self.montage.crop(self.montage.getbbox())


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self):
        super(ArgumentParser, self).__init__()
        self.description = """Create a panojs-style image pyramid from a NIfTI file."""
        self.add_argument('-p', '--panojs_url', metavar='URL', help='URL for the panojs javascript.')
        self.add_argument('filename', help='path to NIfTI file')
        self.add_argument('outdir', nargs='?', help='output directory')


if __name__ == '__main__':
    args = ArgumentParser().parse_args()
    outdir = args.outdir or os.path.basename(os.path.splitext(os.path.splitext(args.filename)[0])[0]) + '.pyr'

    pyr = ImagePyramid(args.filename)
    pyr.generate(outdir, args.panojs_url) if args.panojs_url else pyr.generate(outdir)
