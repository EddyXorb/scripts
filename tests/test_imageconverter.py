import time
from pathlib import Path
import shutil
from os.path import join, exists
from exiftool import ExifToolHelper
import os

import yaml

from ..modules.general.mediatransitioner import TransitionerInput
from ..modules.image.imagefile import ImageFile
from ..modules.image.imageconverter import ImageConverter, convertImage
from ..modules.general.mediatransitioner import DELETE_FOLDER_NAME
from ..modules.mow.mowtags import MowTag

testfolder = (Path(__file__).parent.parent / "tests").absolute().__str__()
tempsrcfolder = "filestotreat"
src = os.path.abspath(join(testfolder, tempsrcfolder))
dst = os.path.abspath("./tests/test_converted")
imagename = "test.jpg"
srcfile = join(src, "subsubfolder", imagename)
targetDir = join(dst, "subsubfolder")
expectedConvertedImageFile = Path(targetDir) / imagename


def executeConversionWith(
    maintainFolderStructure=True, filterstring="", jpg_quality=100
):
    with open(Path(__file__).parent.parent / ".mow_test_settings.yml") as f:
        settings = yaml.safe_load(f)

    ImageConverter(
        TransitionerInput(
            src=src,
            dst=dst,
            maintainFolderStructure=maintainFolderStructure,
            settings=settings,
            filter=filterstring,
            writeMetaTagsToSidecar=True,
        ),
        jpg_quality=jpg_quality,
    )()


def prepareTest(n: int = 1, copy_raw=True, copy_jpg=True):
    shutil.rmtree(src, ignore_errors=True)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.dirname(srcfile))
    for i in range(0, n):
        if copy_jpg:
            shutil.copy(
                join(testfolder, "test.jpg"),
                os.path.join(os.path.dirname(srcfile), f"test{i if n > 1 else ''}.jpg"),
            )
        if copy_raw:
            shutil.copy(
                join(testfolder, "test.ORF"),
                os.path.join(os.path.dirname(srcfile), f"test{i if n > 1 else ''}.ORF"),
            )


def test_moveworks():
    prepareTest()

    executeConversionWith()

    assert not exists(srcfile)
    assert exists(expectedConvertedImageFile)


def test_disablemaintainfolderstructureworks():
    prepareTest()

    executeConversionWith(maintainFolderStructure=False)

    assert not exists(srcfile)
    assert exists(join(dst, imagename))


def test_dng_conversion_works():
    prepareTest()

    executeConversionWith()

    assert not exists(srcfile)
    assert exists(join(dst, "subsubfolder", imagename))
    assert exists(join(dst, "subsubfolder", os.path.splitext(imagename)[0] + ".dng"))
    assert exists(join(src, DELETE_FOLDER_NAME, "subsubfolder", "test.ORF"))


def test_dng_conversion_does_not_convert_dng_again():
    shutil.rmtree(src, ignore_errors=True)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.dirname(srcfile))
    shutil.copy(
        join(testfolder, "test.jpg"),
        os.path.dirname(srcfile),
    )
    shutil.copy(
        join(testfolder, "test.dng"),
        os.path.dirname(srcfile),
    )

    executeConversionWith()

    assert not exists(srcfile)
    assert exists(join(dst, "subsubfolder", imagename))
    assert exists(join(dst, "subsubfolder", os.path.splitext(imagename)[0] + ".dng"))
    assert not exists(join(src, DELETE_FOLDER_NAME, "subsubfolder", "test.dng"))


def test_dng_conversion_is_multithreaded():
    n = 5
    prepareTest(n)

    start = time.time()
    for i in range(0, n):
        executeConversionWith(filterstring=f"test{i}")
    duration_singlethreaded = time.time() - start

    for i in range(0, n):
        assert not exists(join(src, "subsubfolder", f"test{i}.jpg"))
        assert exists(join(dst, "subsubfolder", f"test{i}.jpg"))
        assert exists(join(dst, "subsubfolder", f"test{i}.dng"))
        assert exists(join(src, DELETE_FOLDER_NAME, "subsubfolder", f"test{i}.ORF"))

    prepareTest(n)

    start = time.time()
    executeConversionWith()
    duration_multithreaded = time.time() - start

    for i in range(0, n):
        assert not exists(join(src, "subsubfolder", f"test{i}.jpg"))
        assert exists(join(dst, "subsubfolder", f"test{i}.jpg"))
        assert exists(join(dst, "subsubfolder", f"test{i}.dng"))
        assert exists(join(src, DELETE_FOLDER_NAME, "subsubfolder", f"test{i}.ORF"))

    print(
        f"Singlethreaded: {duration_singlethreaded}, Multithreaded: {duration_multithreaded}"
    )

    assert duration_singlethreaded / n > duration_multithreaded / 2


def test_jpg_quality_10_reduces_filessize_notably():
    prepareTest()

    filesize_before = os.path.getsize(srcfile)

    executeConversionWith(jpg_quality=10)

    filesize_after = os.path.getsize(expectedConvertedImageFile)

    assert filesize_after < filesize_before / 2


def test_jpg_quality_100_lets_jpg_unchanged():
    prepareTest()

    filesize_before = os.path.getsize(srcfile)

    executeConversionWith(jpg_quality=100)

    filesize_after = os.path.getsize(expectedConvertedImageFile)

    assert abs(filesize_after - filesize_before) < 1000  # bytes


def test_jpg_quality_10_moves_jpg_into_deleted_folder():
    prepareTest()

    executeConversionWith(jpg_quality=10)

    assert not exists(srcfile)
    assert exists(join(src, DELETE_FOLDER_NAME, "subsubfolder", imagename))


def test_jpg_conversion_preserves_xmp_and_jpg_metadata():
    prepareTest()

    with ExifToolHelper() as et:
        et.set_tags(
            srcfile,
            {MowTag.rating.value: 3, "EXIF:Model": "Test"},
            params=["-P", "-overwrite_original", "-v2"],
        )

    executeConversionWith(jpg_quality=10)

    with ExifToolHelper() as et:
        rating = et.get_tags(
            expectedConvertedImageFile.with_suffix(".xmp"), [MowTag.rating.value]
        )[0]

        assert MowTag.rating.value in rating
        assert rating[MowTag.rating.value] == 3

        tags = et.get_tags(expectedConvertedImageFile, [])[0]
        print(tags)
        assert tags["EXIF:Model"] == "Test"


def test_convertImage_jpg():
    prepareTest(copy_raw=False, copy_jpg=True)
    os.makedirs(targetDir, exist_ok=True)
    imagefile = convertImage(
        ImageFile(Path(srcfile).with_suffix(".jpg")),
        targetDir,
        {
            "dng_converter_exe": "C:/Program Files/Adobe/Adobe DNG Converter/Adobe DNG Converter.exe"
        },
    )

    assert not exists(srcfile)
    assert exists(expectedConvertedImageFile)
    assert len(imagefile.getAllFileNames()) == 1
    assert imagefile.getAllFileNames()[0] == expectedConvertedImageFile


def test_convertImage_raw():
    prepareTest(copy_raw=True, copy_jpg=False)
    os.makedirs(targetDir, exist_ok=True)

    imagefile = convertImage(
        ImageFile(Path(srcfile).with_suffix(".ORF")),
        targetDir,
        {
            "dng_converter_exe": "C:/Program Files/Adobe/Adobe DNG Converter/Adobe DNG Converter.exe"
        },
    )

    assert not exists(srcfile)
    assert exists(expectedConvertedImageFile.with_suffix(".dng"))
    assert len(imagefile.getAllFileNames()) == 1
    assert imagefile.getAllFileNames()[0] == expectedConvertedImageFile.with_suffix(
        ".dng"
    )


def test_convertImage_both():
    prepareTest(copy_raw=True, copy_jpg=True)
    os.makedirs(targetDir, exist_ok=True)

    imagefile = convertImage(
        ImageFile(srcfile),
        targetDir,
        {
            "dng_converter_exe": "C:/Program Files/Adobe/Adobe DNG Converter/Adobe DNG Converter.exe"
        },
    )

    assert not exists(srcfile)
    assert exists(expectedConvertedImageFile.with_suffix(".jpg"))
    assert exists(expectedConvertedImageFile.with_suffix(".dng"))
    assert len(imagefile.getAllFileNames()) == 2
