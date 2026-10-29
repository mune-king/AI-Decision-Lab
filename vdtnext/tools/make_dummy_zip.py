"""Create a ~10MB dummy ZIP for upload testing: python3 make_dummy_zip.py out.zip"""
import os, sys, zipfile
out = sys.argv[1] if len(sys.argv) > 1 else 'vdtnext-dummy-10MB.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
    z.writestr('README.txt', 'vdtNext upload test data (dummy, not a real measurement).\n')
    z.writestr('dummy_measurement.bin', os.urandom(10 * 1024 * 1024 - 300))
print(out, os.path.getsize(out), 'bytes')
