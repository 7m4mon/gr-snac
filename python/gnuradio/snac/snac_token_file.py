"""Save tokens before forwarding them to the decoder (including EOS ordering)."""
import logging
import pmt
from gnuradio import gr
from gr_snac_core.codec import MODEL
from gr_snac_core.token_file import TokenWriter
from .messages import unpack

LOG = logging.getLogger(__name__)


class snac_token_file(gr.sync_block):
    def __init__(self, filename, model=MODEL):
        gr.sync_block.__init__(self, name="SNAC Token File 12-bit", in_sig=None, out_sig=None)
        self.writer = TokenWriter(filename, model)
        self.error = None
        self.port = pmt.intern("codes")
        self.message_port_register_in(self.port)
        self.message_port_register_out(self.port)
        self.set_msg_handler(self.port, self._handle)

    def _handle(self, message):
        try:
            meta, levels = unpack(message, self.writer.model)
            if self.writer.closed:
                raise ValueError("message after token file EOS")
            if levels is None:
                if meta["chunk_index"] != self.writer.chunks:
                    raise ValueError("out-of-order EOS")
                report = self.writer.finish(complete=True)
                LOG.warning("SNAC FILE %s: %.3fs, %d bytes, tokens=%.1f bit/s, file=%.1f bit/s",
                            self.writer.path, report["duration_seconds"], report["file_bytes"],
                            report["token_bitrate_bps"], report["file_bitrate_bps"])
                if "steady_token_bitrate_bps" in report:
                    LOG.warning("SNAC FILE steady payload=%.3f bit/s (84 bits/frame; finite-file rate includes tail padding)",
                                report["steady_token_bitrate_bps"])
            else:
                self.writer.write(meta, levels)
            self.message_port_pub(self.port, message)
        except Exception as exc:
            self.error = exc
            LOG.exception("SNAC token recording failed")
            self.writer.finish(complete=False)
            # Let the decoder surface the error and terminate rather than hang.
            self.message_port_pub(self.port, pmt.PMT_NIL)

    def stop(self):
        self.writer.finish(complete=False)
        return True

    def work(self, input_items, output_items):
        return 0
