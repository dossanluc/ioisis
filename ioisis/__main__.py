from functools import reduce
from io import BytesIO
import signal
import sys

import click
import ujson

from . import iso, mst


DEFAULT_JSONL_ENCODING = "utf-8"
INPUT_PATH = object()


def apply_decorators(*decorators):
    """Decorator that applies the decorators in reversed order."""
    return lambda func: reduce(lambda f, d: d(f), decorators[::-1], func)


def encoding_option(file_ext, default, **kwargs):
    return click.option(
        file_ext + "_encoding",
        f"--{file_ext[0]}enc",
        default=default,
        show_default=True,
        help=f"{file_ext.upper()} file encoding.",
        **kwargs,
    )


def file_arg_enc_option(file_ext, mode, default_encoding):
    arg_name = file_ext + "_input"
    arg_kwargs = {}
    enc_kwargs = {}
    if mode is INPUT_PATH:
        arg_kwargs["type"] = click.Path(
            dir_okay=False,
            resolve_path=True,
            allow_dash=False,
        )
    else:
        arg_kwargs["default"] = "-"
        if "w" in mode:
            arg_name = file_ext + "_output"
        if "b" in mode:
            arg_kwargs["type"] = click.File(mode)
        else:
            ctx_attr = file_ext + "_encoding"
            arg_kwargs["callback"] = lambda ctx, param, value: \
                click.File(mode, encoding=getattr(ctx, ctx_attr))(value)
            enc_kwargs = {
                "callback": lambda ctx, param, value:
                    setattr(ctx, ctx_attr, value),
                "is_eager": True,
            }

    return apply_decorators(
        encoding_option(file_ext, default=default_encoding, **enc_kwargs),
        click.argument(arg_name, **arg_kwargs)
    )


@click.group()
def main():
    """ISIS data converter using the ioisis Python library."""
    try:  # Fix BrokenPipeError by opening a new fake standard output
        signal.signal(signal.SIGPIPE,
                      lambda signum, frame: setattr(sys, "stdout", BytesIO()))
    except (AttributeError, ValueError):
        pass  # No SIGPIPE in this OS


@main.command()
@file_arg_enc_option("mst", INPUT_PATH, mst.DEFAULT_MST_ENCODING)
@file_arg_enc_option("jsonl", "w", DEFAULT_JSONL_ENCODING)
def mst2jsonl(mst_input, jsonl_output, jsonl_encoding, mst_encoding):
    """MST+XRF to JSON Lines."""
    ensure_ascii = jsonl_output.encoding.lower() == "ascii"
    for record in mst.iter_records(mst_input, encoding=mst_encoding):
        ujson.dump(
            record, jsonl_output,
            ensure_ascii=ensure_ascii,
            escape_forward_slashes=False,
        )
        jsonl_output.write("\n")
        jsonl_output.flush()


@main.command()
@file_arg_enc_option("iso", "rb", iso.DEFAULT_ISO_ENCODING)
@file_arg_enc_option("jsonl", "w", DEFAULT_JSONL_ENCODING)
def iso2jsonl(iso_input, jsonl_output, iso_encoding, jsonl_encoding):
    """ISO2709 to JSON Lines."""
    ensure_ascii = jsonl_output.encoding.lower() == "ascii"
    for record in iso.iter_records(iso_input, encoding=iso_encoding):
        ujson.dump(
            record, jsonl_output,
            ensure_ascii=ensure_ascii,
            escape_forward_slashes=False,
        )
        jsonl_output.write("\n")
        jsonl_output.flush()


@main.command()
@file_arg_enc_option("jsonl", "r", DEFAULT_JSONL_ENCODING)
@file_arg_enc_option("iso", "wb", iso.DEFAULT_ISO_ENCODING)
def jsonl2iso(jsonl_input, iso_output, iso_encoding, jsonl_encoding):
    """JSON Lines to ISO2709."""
    for line in jsonl_input:
        record_dict = ujson.loads(line)
        iso_output.write(iso.dict2bytes(record_dict, encoding=iso_encoding))
        iso_output.flush()


if __name__ == "__main__":
    main()
