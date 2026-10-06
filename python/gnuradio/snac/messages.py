"""Native PMT dictionary wire contract; no pickle and no bit packing."""
import math
import pmt
from gr_snac_core.codec import RATE, validate_levels
from gr_snac_core.frames import FRAME_MODE, validate_frame


def pack(metadata, levels=None):
    result = pmt.make_dict()
    result = pmt.dict_add(result, pmt.intern("metadata"), pmt.to_pmt(metadata))
    if levels is not None:
        for i, level in enumerate(validate_levels(levels)):
            result = pmt.dict_add(result, pmt.intern(f"level{i}"),
                                  pmt.init_u16vector(len(level), level.tolist()))
    return result


def unpack(message, model):
    if not pmt.is_dict(message):
        raise ValueError("expected PMT dictionary")
    meta_pmt = pmt.dict_ref(message, pmt.intern("metadata"), pmt.PMT_NIL)
    if not pmt.is_dict(meta_pmt):
        raise ValueError("missing metadata dictionary")
    meta = pmt.to_python(meta_pmt)
    if (meta.get("codec") != "snac" or meta.get("model") != model
            or meta.get("sample_rate") != RATE or meta.get("num_levels") != 3):
        raise ValueError("incompatible codec/model/sample rate/levels")
    index = meta.get("chunk_index")
    if type(index) is not int or index < 0:
        raise ValueError("invalid chunk_index")
    if meta.get("stream_mode") not in (None, FRAME_MODE):
        raise ValueError("unsupported stream_mode")
    if meta.get("eos") is True:
        return meta, None
    samples = meta.get("audio_samples")
    if type(samples) is not int or samples <= 0:
        raise ValueError("invalid audio_samples")
    encoded = meta.get("encoded_samples", samples)
    crop = meta.get("crop_start", 0)
    if (type(encoded) is not int or type(crop) is not int
            or crop < 0 or encoded < crop + samples):
        raise ValueError("invalid encoded_samples/crop_start")
    duration = meta.get("chunk_duration_ms")
    if (type(duration) not in (int, float) or not math.isfinite(duration)
            or abs(duration - samples / RATE * 1000) > 1e-6):
        raise ValueError("invalid chunk_duration_ms")
    levels = []
    for i in range(3):
        level = pmt.dict_ref(message, pmt.intern(f"level{i}"), pmt.PMT_NIL)
        if not pmt.is_u16vector(level):
            raise ValueError(f"level{i} must be u16vector")
        levels.append(pmt.u16vector_elements(level))
    levels = validate_levels(levels)
    if meta.get("stream_mode") == FRAME_MODE:
        validate_frame(meta, levels)
    return meta, levels
