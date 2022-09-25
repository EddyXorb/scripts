from exiftool import ExifToolHelper

with ExifToolHelper() as et:
    for d in et.get_metadata("../test/test.ORF"):
        for k, v in d.items():
            print(f"Dict: {k} = {v}")