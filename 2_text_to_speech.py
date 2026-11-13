#!/usr/bin/env python3
"""Convert a text file into speech using the local OmniVoice model.

Usage
-----
    python 2_text_to_speech.py <input.txt> [<output>] [--max-chars N | --all-chars] [--split N]

Examples
--------
    # Whole book as ONE .wav (written to 2_output_book_audio/<book>/):
    python 2_text_to_speech.py "1_output_book_txt/Book/Book_clean.txt" -all-chars

    # Split the book into ~5000-character parts, one .wav per part:
    python 2_text_to_speech.py "1_output_book_txt/Book/Book_clean.txt" --split 5000

    # First 1000 characters (sample / performance check):
    python 2_text_to_speech.py "1_output_book_txt/Book/Book_clean.txt" -max-chars 1000

    # Explicit output directory, or a full .wav path:
    python 2_text_to_speech.py book.txt "somewhere/else" -all-chars

Notes
-----
* <output> is optional and defaults to the 2_output_book_audio/ folder.
  It may be a directory or a full path ending in .wav (single-file mode only).
* --split N writes one file per part named <stem>_part_001.wav,
  <stem>_part_002.wav, ... Parts already on disk are skipped, so a cancelled
  run can be resumed simply by re-running the same command.
* Default voice: female, young adult, moderate pitch, British accent,
  language auto-detected. Override with --instruct / --language.
* Default is --num-step 16 (fast); pass --num-step 32 for maximum quality.
* With neither --max-chars nor --all-chars, the WHOLE file is converted.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import soundfile as sf
import torch

DEFAULT_INSTRUCT = "female, young adult, moderate pitch, british accent"
DEFAULT_AUDIO_DIR = "2_output_book_audio"
DEFAULT_NUM_STEP = 16


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert a text file into speech with OmniVoice.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("input", help="Path to the input .txt file.")
    p.add_argument(
        "output",
        nargs="?",
        default=None,
        help="Output directory or .wav path (default: 2_output_book_audio/).",
    )

    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--max-chars",
        "-max-chars",
        type=int,
        default=0,
        help="Synthesize only the first N characters.",
    )
    g.add_argument(
        "--all-chars",
        "-all-chars",
        action="store_true",
        help="Synthesize the entire file.",
    )

    p.add_argument(
        "--split",
        type=int,
        default=0,
        help="Split text into N-character parts; write one .wav per part "
        "(<stem>_part_001.wav, ...). Existing parts are skipped (resumable).",
    )
    p.add_argument(
        "--model", default="k2-fsa/OmniVoice",
        help="Model checkpoint path or HuggingFace repo id.",
    )
    p.add_argument(
        "--device", default=None,
        help="Device (e.g. cuda:0, cpu). Auto-detected when omitted.",
    )
    p.add_argument(
        "--num-step", type=int, default=DEFAULT_NUM_STEP,
        help=f"Diffusion steps ({DEFAULT_NUM_STEP} default; 32 = higher quality, slower).",
    )
    p.add_argument("--speed", type=float, default=1.0,
                   help="Speaking speed factor.")
    p.add_argument("--language", default="auto",
                   help="Language code/name, or 'auto' to auto-detect.")
    p.add_argument("--instruct", default=DEFAULT_INSTRUCT,
                   help="Voice design instruction (comma-separated attributes).")
    p.add_argument("--auto-voice", action="store_true",
                   help="Use a random voice (ignore --instruct).")
    p.add_argument("--offset", type=int, default=0,
                   help="Character offset to start reading from.")
    p.add_argument("--ref-audio", default=None,
                   help="Reference audio for voice cloning (path to a short .wav).")
    p.add_argument("--ref-text", default=None,
                   help="Transcript of the reference audio (voice cloning).")
    return p.parse_args()


def read_text_slice(path: str, offset: int, max_chars: int) -> str:
    """Read the requested slice of a UTF-8 text file and collapse whitespace.

    max_chars <= 0 means "the whole file".
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    if offset:
        raw = raw[offset:]
    if max_chars and max_chars > 0:
        raw = raw[:max_chars]

    text = " ".join(raw.split()).strip()
    if not text:
        sys.exit(f"ERROR: no text extracted from {path!r}")
    return text


def split_text(text: str, chunk_size: int) -> list[str]:
    """Split text into ~chunk_size-character chunks at word boundaries."""
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            cut = text.rfind(" ", start, end)
            if cut > start:
                end = cut
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end + 1
    return chunks


def resolve_output(output: str, input_path: str) -> str:
    """Turn the <output> argument into a concrete .wav path (single-file mode)."""
    if output.lower().endswith(".wav"):
        out_path = output
    else:
        stem = os.path.splitext(os.path.basename(input_path))[0]
        out_path = os.path.join(output, f"{stem}.wav")

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return out_path


def resolve_output_dir(output: str | None) -> str:
    d = output or DEFAULT_AUDIO_DIR
    os.makedirs(d, exist_ok=True)
    return d


def pick_device(explicit: str | None) -> str:
    if explicit:
        return explicit
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


def load_model(args: argparse.Namespace, device: str):
    from omnivoice import OmniVoice  # imported here so --help stays fast

    dtype = torch.float16 if device.startswith("cuda") else torch.float32
    t0 = time.time()
    model = OmniVoice.from_pretrained(args.model, device_map=device, dtype=dtype)
    return model, time.time() - t0


def build_gen_kwargs(args: argparse.Namespace, text: str, language: str | None) -> dict:
    kw = dict(text=text, language=language, num_step=args.num_step, speed=args.speed)
    if args.ref_audio:
        kw["ref_audio"] = args.ref_audio
        if args.ref_text:
            kw["ref_text"] = args.ref_text
    elif not args.auto_voice and args.instruct:
        kw["instruct"] = args.instruct
    return kw


def main() -> None:
    args = parse_args()

    max_chars = 0 if (args.all_chars or args.max_chars <= 0) else args.max_chars
    text = read_text_slice(args.input, args.offset, max_chars)

    device = pick_device(args.device)
    print(f"[1/3] Extracted {len(text)} characters from {args.input!r}")
    print(f"[2/3] Loading model {args.model!r} on {device} ...")
    model, load_secs = load_model(args, device)
    print(f"      Model loaded in {load_secs:.1f}s (sampling rate {model.sampling_rate} Hz)\n")

    language = args.language if args.language and args.language.lower() != "auto" else None
    stem = os.path.splitext(os.path.basename(args.input))[0]

    # ------------------------------------------------------------------
    # Split mode: one .wav per ~N-character part, generated sequentially.
    # ------------------------------------------------------------------
    if args.split and args.split > 0:
        chunks = split_text(text, args.split)
        out_dir = resolve_output_dir(args.output)
        print(f"[3/3] Splitting {len(text)} chars into {len(chunks)} parts "
              f"(~{args.split} chars each) -> {out_dir}")

        t_start = time.time()
        done = 0
        skipped = 0
        total_audio = 0.0
        total_gen = 0.0

        for i, chunk in enumerate(chunks, 1):
            part_path = os.path.join(out_dir, f"{stem}_part_{i:03d}.wav")
            if os.path.exists(part_path):
                print(f"  [{i:>3}/{len(chunks)}] SKIP (already exists): {part_path}")
                skipped += 1
                continue

            t = time.time()
            audio = model.generate(**build_gen_kwargs(args, chunk, language))[0]
            gen = time.time() - t
            sf.write(part_path, audio, model.sampling_rate)
            dur = len(audio) / model.sampling_rate
            total_audio += dur
            total_gen += gen
            done += 1
            print(f"  [{i:>3}/{len(chunks)}] saved {part_path}  "
                  f"({len(chunk)} chars -> {dur:.1f}s audio, {gen:.1f}s gen)")

        wall = time.time() - t_start
        print("\n" + "=" * 62)
        print("DONE (split)")
        print(f"  Parts        : {done} new + {skipped} skipped (of {len(chunks)})")
        print(f"  Output dir   : {out_dir}")
        print(f"  Total audio  : {total_audio / 60:.1f} min")
        print(f"  Generation   : {total_gen / 60:.1f} min  (avg RTF "
              f"{total_gen / total_audio:.2f})" if total_audio else "  Generation: n/a")
        print(f"  Wall time    : {wall / 60:.1f} min")
        print("=" * 62)
        return

    # ------------------------------------------------------------------
    # Single-file mode (existing behaviour).
    # ------------------------------------------------------------------
    print("[3/3] Generating speech ...")
    t = time.time()
    audio = model.generate(**build_gen_kwargs(args, text, language))[0]
    gen = time.time() - t
    duration = len(audio) / model.sampling_rate

    out_path = resolve_output(args.output or DEFAULT_AUDIO_DIR, args.input)
    sf.write(out_path, audio, model.sampling_rate)

    print("\n" + "=" * 60)
    print("DONE")
    print(f"  Output        : {out_path}")
    print(f"  Audio length  : {duration:.2f}s")
    print(f"  Model load    : {load_secs:.1f}s")
    print(f"  Generation    : {gen:.1f}s")
    print(f"  Real-time x   : {duration / gen:.2f}x (RTF {gen / duration:.3f})")
    print("=" * 60)


if __name__ == "__main__":
    main()
