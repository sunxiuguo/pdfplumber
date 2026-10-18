import io

import pytest

import pdfplumber


def fixture(rect, rotation):
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 400] "
            f"/Rotate {rotation} /Resources << >> /Annots [4 0 R] >>"
        ).encode(),
        (
            f'<< /Type /Annot /Subtype /Link /Rect [{" ".join(map(str, rect))}] '
            "/A << /S /URI /URI (https://example.invalid/synthetic) >> >>"
        ).encode(),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(out)
    out.extend(b"xref\n0 5\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize(
    "rect",
    [
        (50, 100, 150, 130),
        (150, 100, 50, 130),
        (50, 130, 150, 100),
        (150, 130, 50, 100),
    ],
)
def test_rotated_cropped_hyperlinks(rotation, rect):
    with pdfplumber.open(io.BytesIO(fixture(rect, rotation))) as pdf:
        page = pdf.pages[0]
        original = page.hyperlinks[0]
        bbox = pdfplumber.utils.obj_to_bbox(original)
        assert original["width"] > 0
        assert original["height"] > 0
        assert original["data"]["Rect"] == list(rect)
        for parent in [page, page.crop(page.bbox)]:
            for cropped in [parent.crop(bbox), parent.within_bbox(bbox)]:
                assert len(cropped.hyperlinks) == 1
                actual = cropped.hyperlinks[0]
                assert pdfplumber.utils.obj_to_bbox(actual) == bbox
                assert actual["uri"] == original["uri"]
                nested = cropped.crop(cropped.bbox)
                assert len(nested.hyperlinks) == 1
                assert pdfplumber.utils.obj_to_bbox(nested.hyperlinks[0]) == bbox
        assert page.outside_bbox(bbox).hyperlinks == []
